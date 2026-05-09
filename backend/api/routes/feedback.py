import csv
import io
from flask import Blueprint, request, jsonify, Response
from sqlalchemy import select, func
from db.models import Feedback, Candidate, ModelVersion, get_session
from agents.graph import feedback_graph

feedback_bp = Blueprint("feedback", __name__)
model_bp    = Blueprint("model",    __name__)


# ── POST /api/feedback/ ───────────────────────────────────────────────────
@feedback_bp.route("/", methods=["POST"])
def submit_feedback():
    data         = request.get_json()
    jd_id        = data.get("jd_id")
    candidate_id = data.get("candidate_id")
    decision     = data.get("decision")

    if not all([jd_id, candidate_id, decision]):
        return jsonify({"error": "jd_id, candidate_id, decision required"}), 400
    if decision not in ("approve", "reject"):
        return jsonify({"error": "decision must be 'approve' or 'reject'"}), 400

    with get_session() as session:
        fb = Feedback(jd_id=jd_id, candidate_id=candidate_id, decision=decision)
        session.add(fb)
        session.commit()
        count = session.execute(
            select(func.count()).select_from(Feedback).where(Feedback.jd_id == jd_id)
        ).scalar()

    # All required HireLoopState keys — prevents KeyError in graph nodes
    state = feedback_graph.invoke({
        "jd_id":             jd_id,
        "jd_text":           "",
        "criteria":          {},
        "resumes":           [],
        "ranked":            [],
        "questions":         {},
        "feedback_buf":      [],
        "retrain_triggered": False,
        "importances":       {},
        "new_ranked":        [],
    })

    response: dict = {
        "feedback_count":    count,
        "retrain_triggered": state.get("retrain_triggered", False),
    }
    if state.get("retrain_triggered"):
        response["importances"]  = state.get("importances", {})
        response["new_ranking"]  = state.get("new_ranked", [])

    return jsonify(response)


# ── POST /api/model/retrain ───────────────────────────────────────────────
@model_bp.route("/retrain", methods=["POST"])
def force_retrain():
    data  = request.get_json()
    jd_id = data.get("jd_id")
    if not jd_id:
        return jsonify({"error": "jd_id required"}), 400

    from agents.nodes.retrainer import retrainer_node
    state = retrainer_node({
        "jd_id": jd_id, "jd_text": "", "criteria": {},
        "resumes": [], "ranked": [], "questions": {},
        "feedback_buf": [], "retrain_triggered": True,
        "importances": {}, "new_ranked": [],
    })
    return jsonify({
        "importances":  state.get("importances", {}),
        "new_ranking":  state.get("new_ranked", []),
    })


# ── GET /api/model/importances/<jd_id> ────────────────────────────────────
@model_bp.route("/importances/<jd_id>", methods=["GET"])
def get_importances(jd_id: str):
    with get_session() as session:
        versions = session.execute(
            select(ModelVersion)
            .where(ModelVersion.jd_id == jd_id)
            .order_by(ModelVersion.version.asc())
        ).scalars().all()

        if not versions:
            return jsonify({
                "importances":    {"skill_overlap": 0.40, "semantic_sim": 0.30, "exp_gap": 0.20, "keyword_density": 0.10},
                "version":        0,
                "feedback_count": 0,
                "val_auc":        None,
                "history":        [],
            })

        latest  = versions[-1]
        history = [
            {
                "version":        v.version,
                "importances":    v.importances,
                "feedback_count": v.feedback_count,
                "val_auc":        getattr(v, "val_auc", None),
                "created_at":     v.created_at.isoformat(),
            }
            for v in versions
        ]

    return jsonify({
        "importances":    latest.importances,
        "version":        latest.version,
        "feedback_count": latest.feedback_count,
        "val_auc":        getattr(latest, "val_auc", None),
        "history":        history,
    })
