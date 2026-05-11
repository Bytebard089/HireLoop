import pickle
import os
import numpy as np
from sqlalchemy import select
from ml.features import compute_features
from rag.retriever import retrieve_for_jd
from db.models import Candidate, Feedback, get_session
from agents.state import HireLoopState

MODELS_DIR    = os.getenv("MODELS_DIR", "./ml/models")
LEGACY_MODEL  = os.getenv("MODEL_PATH", "./ml/model.pkl")  # backward-compat fallback


def _load_model(jd_id: str):
    """Load per-JD model, falling back to legacy global model.pkl."""
    per_jd = os.path.join(MODELS_DIR, f"{jd_id}.pkl")
    if os.path.exists(per_jd):
        with open(per_jd, "rb") as f:
            return pickle.load(f)
    if os.path.exists(LEGACY_MODEL):
        with open(LEGACY_MODEL, "rb") as f:
            return pickle.load(f)
            
    # Proactively train the fallback model if it's completely missing
    try:
        from ml.trainer import train_initial_model
        return train_initial_model()
    except Exception as e:
        print(f"Fallback training failed: {e}")
        return None


def resume_scorer_node(state: HireLoopState) -> HireLoopState:
    """
    For each candidate in state['resumes']:
    1. Retrieve semantic similarity via RAG
    2. Compute 4 features
    3. XGBoost predict_proba → fit_score (uses per-JD model)
    4. Rank by score, track rank change vs prev_rank
    """
    model = _load_model(state["jd_id"])
    criteria = state["criteria"]
    jd_id    = state["jd_id"]
    jd_skills = criteria.get("skills", []) or []
    jd_keywords = criteria.get("keywords", []) or []
    criteria_term_count = len(jd_skills) + len(jd_keywords)

    # Get semantic similarity scores from RAG for all candidates at once
    sem_scores = retrieve_for_jd(
        jd_text=state["jd_text"],
        jd_id=jd_id,
    )  # {candidate_id: float}

    new_scored = {}
    for resume in state["resumes"]:
        cid = str(resume["id"])
        sem_sim = sem_scores.get(cid, 0.0)

        features = compute_features(
            resume_text=resume["resume_text"],
            criteria=criteria,
            semantic_sim=sem_sim,
        )

        # If JD is too sparse (e.g. only "3+ years"), the ML model tends to
        # overconfident predictions. Use a conservative heuristic instead.
        if criteria_term_count < 2:
            fit_score = (
                (1 - features["exp_gap"]) * 0.8 +
                features["semantic_sim"] * 0.2
            )
        elif model is not None:
            X = np.array([[
                features["skill_overlap"],
                features["semantic_sim"],
                features["exp_gap"],
                features["keyword_density"],
            ]])
            fit_score = float(model.predict_proba(X)[0][1])

            # When RAG is disabled, semantic_sim is always 0.0 for every candidate.
            # The XGBoost model was trained on synthetic data where semantic_sim
            # varied, so it learns to give high scores when other features are
            # decent — regardless of semantic_sim being 0. This leads to
            # inflated scores (e.g. 98% when skill_overlap is only 67%).
            #
            # Fix: blend the model prediction with a transparent heuristic
            # when semantic_sim is 0, so scores better reflect the actual
            # feature values the user can see on the "Why this score?" panel.
            if features["semantic_sim"] < 0.01:
                heuristic = (
                    features["skill_overlap"]   * 0.40 +
                    (1 - features["exp_gap"])    * 0.35 +
                    features["keyword_density"]  * 0.25
                )
                # Blend: 40% model + 60% heuristic when RAG is off
                fit_score = fit_score * 0.4 + heuristic * 0.6
        else:
            # Fallback: weighted average before first model is trained
            fit_score = (
                features["skill_overlap"]   * 0.4 +
                features["semantic_sim"]    * 0.3 +
                (1 - features["exp_gap"])   * 0.2 +
                features["keyword_density"] * 0.1
            )

        new_scored[cid] = {
            "fit_score":    round(fit_score, 4),
            "features":     features,
        }

    # Assign rank by combining existing candidates with newly scored ones
    with get_session() as session:
        # Load all candidates for this JD
        all_cands = session.execute(
            select(Candidate).where(Candidate.jd_id == jd_id)
        ).scalars().all()

        # Load all feedbacks to remember state
        feedbacks = session.execute(
            select(Feedback).where(Feedback.jd_id == jd_id)
        ).scalars().all()
        decision_map = {fb.candidate_id: fb.decision for fb in feedbacks}

        combined = []
        for cand in all_cands:
            cid = str(cand.id)
            if cid in new_scored:
                cand.fit_score = new_scored[cid]["fit_score"]
                cand.features  = new_scored[cid]["features"]
            
            combined.append({
                "candidate_id": cid,
                "name":         cand.name,
                "fit_score":    cand.fit_score or 0.0,
                "features":     cand.features or {},
                "decision":     decision_map.get(cid),
            })

        # Sort descending by fit_score
        combined.sort(key=lambda x: x["fit_score"], reverse=True)

        ranked = []
        for new_rank, item in enumerate(combined, start=1):
            cand = session.get(Candidate, item["candidate_id"])
            if cand:
                prev_rank = cand.rank if cand.rank is not None else new_rank
                cand.prev_rank = cand.rank
                cand.rank      = new_rank
            else:
                prev_rank = new_rank

            ranked.append({
                **item,
                "rank":        new_rank,
                "prev_rank":   prev_rank,
                "rank_change": prev_rank - new_rank,
            })
        session.commit()

    return {**state, "ranked": ranked}