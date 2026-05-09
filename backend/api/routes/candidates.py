"""
Candidate and JD API routes.
"""
import uuid
import io
from flask import Blueprint, request, jsonify
from sqlalchemy import select
from db.models import JobDescription, Candidate, Feedback, get_session
from rag.embedder import embed_resume
from ml.features import compute_features

candidates_bp = Blueprint("candidates", __name__)
jd_bp         = Blueprint("jd",         __name__)

_scoring_graph = None


def get_scoring_graph():
    global _scoring_graph
    if _scoring_graph is None:
        from agents.graph import scoring_graph
        _scoring_graph = scoring_graph
    return _scoring_graph


# ── POST /api/jd/parse ────────────────────────────────────────────────────────

@jd_bp.route("/parse", methods=["POST"])
def parse_jd():
    """
    Body: { "jd_text": "..." }
    Creates a JobDescription row, runs jd_parser_node, returns criteria + jd_id.
    """
    data    = request.get_json()
    jd_text = (data or {}).get("jd_text", "").strip()

    if not jd_text:
        return jsonify({"error": "jd_text is required"}), 400

    jd_id = str(uuid.uuid4())

    # Persist raw JD first
    with get_session() as session:
        jd = JobDescription(id=jd_id, raw_text=jd_text)
        session.add(jd)
        session.commit()

    # Run only jd_parser_node (not full scoring graph — no resumes yet)
    from agents.nodes.jd_parser import jd_parser_node
    state = jd_parser_node({
        "jd_text": jd_text,
        "jd_id":   jd_id,
        "criteria": {},
        "resumes": [],
        "ranked":  [],
        "questions": {},
        "feedback_buf": [],
        "retrain_triggered": False,
        "importances": {},
        "new_ranked": [],
    })

    return jsonify({
        "jd_id":    jd_id,
        "criteria": state["criteria"],
    })


# ── POST /api/candidates/upload ───────────────────────────────────────────────

@candidates_bp.route("/upload", methods=["POST"])
def upload_resumes():
    """
    Accepts multipart/form-data with:
      - jd_id  (form field)
      - files  (one or more resume files: .txt or .pdf)
    OR JSON with:
      - jd_id, resumes: [{name, text}]

    Embeds resumes, scores them, returns ranked list.
    """
    # ── Parse input ───────────────────────────────────────────────────────────
    max_bytes = 2 * 1024 * 1024
    if request.is_json:
        data    = request.get_json()
        jd_id   = data.get("jd_id")
        raw_list = data.get("resumes", [])   # [{name, text}]
        resume_objects = [
            {"name": r.get("name", f"Candidate {i+1}"), "text": r.get("text", "")}
            for i, r in enumerate(raw_list)
        ]
    else:
        jd_id = request.form.get("jd_id")
        files = request.files.getlist("files")
        resume_objects = []
        for f in files:
            if f.content_length and f.content_length > max_bytes:
                return jsonify({"error": f"File too large (max {max_bytes} bytes)."}), 413
            filename = f.filename or "Unknown"
            name = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
            raw_bytes = f.read()
            if len(raw_bytes) > max_bytes:
                return jsonify({"error": f"File too large (max {max_bytes} bytes)."}), 413
            if filename.endswith(".pdf"):
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(io.BytesIO(raw_bytes))
                    text = "\n".join(page.extract_text() or "" for page in reader.pages)
                except Exception:
                    text = raw_bytes.decode("utf-8", errors="ignore")
            else:
                text = raw_bytes.decode("utf-8", errors="ignore")
            resume_objects.append({"name": name, "text": text})

    if not jd_id:
        return jsonify({"error": "jd_id is required"}), 400
    if not resume_objects:
        return jsonify({"error": "No resumes provided"}), 400
    for r in resume_objects:
        if not r.get("text") or not str(r.get("text")).strip():
            return jsonify({"error": "Resume text cannot be empty"}), 400

    # ── Load JD ───────────────────────────────────────────────────────────────
    with get_session() as session:
        jd = session.get(JobDescription, jd_id)
        if not jd:
            return jsonify({"error": f"JD {jd_id} not found"}), 404
        jd_text  = jd.raw_text
        criteria = jd.criteria or {}

    # ── Persist candidates + embed ────────────────────────────────────────────
    with get_session() as session:
        db_resumes = []
        for r in resume_objects:
            existing = session.execute(
                select(Candidate)
                .where(Candidate.jd_id == jd_id)
                .where(Candidate.name == r["name"])
                .where(Candidate.resume_text == r["text"])
            ).scalars().first()
            if existing:
                db_resumes.append({
                    "id":          str(existing.id),
                    "name":        existing.name,
                    "resume_text": existing.resume_text,
                })
                continue
            cand = Candidate(
                jd_id=jd_id,
                name=r["name"],
                resume_text=r["text"],
                features=compute_features(r["text"], criteria, semantic_sim=0.0),
            )
            session.add(cand)
            session.flush()
            try:
                embed_resume(str(cand.id), cand.resume_text, jd_id)
            except Exception as e:
                # Keep upload/scoring functional even if embedding infra is unavailable.
                print(f"[upload] embed skipped for candidate {cand.id}: {e}")
            db_resumes.append({
                "id":          str(cand.id),
                "name":        cand.name,
                "resume_text": cand.resume_text,
            })
        session.commit()

    # ── Run scoring graph ─────────────────────────────────────────────────────
    state = get_scoring_graph().invoke({
        "jd_text":  jd_text,
        "jd_id":    jd_id,
        "criteria": criteria,
        "resumes":  db_resumes,
        "ranked":   [],
        "questions": {},
        "feedback_buf": [],
        "retrain_triggered": False,
        "importances": {},
        "new_ranked": [],
    })

    return jsonify({
        "ranked":    state["ranked"],
        "questions": state["questions"],
        "criteria":  criteria,
    })


# ── GET /api/candidates/?jd_id= ───────────────────────────────────────────────

@candidates_bp.route("/", methods=["GET"])
def list_candidates():
    """Returns all candidates for a JD, ordered by rank."""
    jd_id = request.args.get("jd_id")
    if not jd_id:
        return jsonify({"error": "jd_id query param required"}), 400

    with get_session() as session:
        jd = session.get(JobDescription, jd_id)
        criteria = (jd.criteria if jd else {}) or {}

        rows = session.execute(
            select(Candidate)
            .where(Candidate.jd_id == jd_id)
            .order_by(Candidate.rank.asc().nulls_last())
        ).scalars().all()

        ranks = [c.rank for c in rows]
        present_ranks = [r for r in ranks if r is not None]
        needs_repair = any(r is None for r in ranks) or len(set(present_ranks)) != len(present_ranks)
        if rows and needs_repair:
            rows = sorted(rows, key=lambda c: c.fit_score or 0.0, reverse=True)
            for idx, cand in enumerate(rows, start=1):
                cand.prev_rank = cand.rank
                cand.rank = idx
            session.commit()

        feedbacks = session.execute(
            select(Feedback).where(Feedback.jd_id == jd_id)
        ).scalars().all()
        decision_map = {fb.candidate_id: fb.decision for fb in feedbacks}

        candidates = [
            {
                "candidate_id": str(c.id),
                "name":         c.name,
                "fit_score":    c.fit_score,
                "rank":         c.rank,
                "prev_rank":    c.prev_rank,
                "rank_change":  (c.prev_rank or c.rank or 0) - (c.rank or 0),
                "features":     c.features or {},
                "decision":     decision_map.get(str(c.id)),
            }
            for c in rows
        ]

    return jsonify({"candidates": candidates})


# ── GET /api/candidates/<id>/questions ───────────────────────────────────────

@candidates_bp.route("/<candidate_id>/questions", methods=["GET"])
def get_questions(candidate_id: str):
    """Generates (or returns cached) adaptive questions for a candidate."""
    jd_id = request.args.get("jd_id")
    if not jd_id:
        return jsonify({"error": "jd_id query param required"}), 400

    with get_session() as session:
        cand = session.get(Candidate, candidate_id)
        jd   = session.get(JobDescription, jd_id)
        if not cand or not jd:
            return jsonify({"error": "candidate or JD not found"}), 404

        features = cand.features or {}
        criteria = jd.criteria   or {}

    from agents.nodes.question_gen import question_gen_node
    state = question_gen_node({
        "jd_text":  jd.raw_text if jd else "",
        "jd_id":    jd_id,
        "criteria": criteria,
        "resumes":  [],
        "ranked":   [{"candidate_id": candidate_id, "features": features}],
        "questions": {},
        "feedback_buf": [],
        "retrain_triggered": False,
        "importances": {},
        "new_ranked": [],
    })

    return jsonify({"questions": state["questions"].get(candidate_id, [])})


# ── GET /api/candidates/export?jd_id=<id> ────────────────────────────────
@candidates_bp.route("/export", methods=["GET"])
def export_shortlist():
    """Export ranked candidates as CSV for a given JD."""
    import csv, io
    from flask import Response

    jd_id = request.args.get("jd_id")
    if not jd_id:
        return jsonify({"error": "jd_id required"}), 400

    with get_session() as session:
        from sqlalchemy import select as sel, asc
        rows = session.execute(
            sel(Candidate)
            .where(Candidate.jd_id == jd_id)
            .order_by(asc(Candidate.rank))
        ).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Rank", "Name", "Fit Score", "Decision",
        "Skill Overlap", "Semantic Match", "Exp Gap", "Keyword Density",
        "Experience Years", "Found Skills", "Missing Skills",
    ])
    for r in rows:
        feats = r.features or {}
        writer.writerow([
            r.rank,
            r.name,
            f"{round((r.fit_score or 0) * 100)}%",
            r.decision or "pending",
            f"{round((feats.get('skill_overlap', 0)) * 100)}%",
            f"{round((feats.get('semantic_sim',  0)) * 100)}%",
            f"{round((feats.get('exp_gap',        0)) * 100)}%",
            f"{round((feats.get('keyword_density',0)) * 100)}%",
            feats.get("resume_years", "?"),
            ", ".join(feats.get("found_skills",   []) or []),
            ", ".join(feats.get("missing_skills", []) or []),
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=hireloop-shortlist.csv"},
    )
