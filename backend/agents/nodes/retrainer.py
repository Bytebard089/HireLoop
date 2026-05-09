import os
import pickle
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
from sqlalchemy import select
from db.models import Feedback, Candidate, ModelVersion, get_session
from agents.state import HireLoopState

SEED_PATH  = os.getenv("SEED_DATASET_PATH", "./ml/seed_dataset.csv")
MODELS_DIR = os.getenv("MODELS_DIR", "./ml/models")
FEATURES   = ["skill_overlap", "semantic_sim", "exp_gap", "keyword_density"]


def _model_path(jd_id: str) -> str:
    os.makedirs(MODELS_DIR, exist_ok=True)
    return os.path.join(MODELS_DIR, f"{jd_id}.pkl")


def retrainer_node(state: HireLoopState) -> HireLoopState:
    jd_id      = state["jd_id"]
    model_path = _model_path(jd_id)

    # ── 1. Build training set ──────────────────────────────────────────────
    seed_df = pd.read_csv(SEED_PATH)

    with get_session() as session:
        feedbacks = session.execute(
            select(Feedback, Candidate)
            .join(Candidate, Feedback.candidate_id == Candidate.id)
            .where(Feedback.jd_id == jd_id)
        ).all()

        feedback_rows = []
        decision_map  = {}   # candidate_id → latest decision
        for fb, cand in feedbacks:
            feats = cand.features or {}
            feedback_rows.append({
                "skill_overlap":   feats.get("skill_overlap", 0),
                "semantic_sim":    feats.get("semantic_sim", 0),
                "exp_gap":         feats.get("exp_gap", 0),
                "keyword_density": feats.get("keyword_density", 0),
                "label": 1 if fb.decision == "approve" else 0,
            })
            decision_map[str(cand.id)] = fb.decision   # ← capture for new_ranked

    if feedback_rows:
        combined = pd.concat([seed_df, pd.DataFrame(feedback_rows)], ignore_index=True)
    else:
        combined = seed_df

    X = combined[FEATURES].values
    y = combined["label"].values

    # ── 2. Class imbalance ────────────────────────────────────────────────
    n_neg = int((y == 0).sum())
    n_pos = int((y == 1).sum())
    scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

    # ── 3. Val AUC ────────────────────────────────────────────────────────
    val_auc: float | None = None
    if len(y) >= 20:
        X_tr, X_val, y_tr, y_val = train_test_split(
            X, y, test_size=0.2, stratify=y, random_state=42
        )
        _eval = xgb.XGBClassifier(
            n_estimators=100, max_depth=3, learning_rate=0.1,
            subsample=0.8, scale_pos_weight=scale_pos_weight,
            eval_metric="logloss", random_state=42,
        )
        _eval.fit(X_tr, y_tr)
        val_auc = float(roc_auc_score(y_val, _eval.predict_proba(X_val)[:, 1]))
        print(f"[retrainer] val AUC: {val_auc:.4f}")

    # ── 4. Final model ────────────────────────────────────────────────────
    model = xgb.XGBClassifier(
        n_estimators=100, max_depth=3, learning_rate=0.1,
        subsample=0.8, scale_pos_weight=scale_pos_weight,
        eval_metric="logloss", random_state=42,
    )
    model.fit(X, y)
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    importances = dict(zip(FEATURES, model.feature_importances_.tolist()))

    # ── 5. Persist model version ──────────────────────────────────────────
    with get_session() as session:
        from sqlalchemy import func, select as sel
        version_count = session.execute(
            sel(func.count()).select_from(ModelVersion).where(ModelVersion.jd_id == jd_id)
        ).scalar()
        mv = ModelVersion(
            jd_id=jd_id, version=version_count + 1,
            importances=importances, feedback_count=len(feedback_rows),
            model_path=model_path, val_auc=val_auc,
        )
        session.add(mv)
        session.commit()

    # ── 6. Re-score — capture old_rank BEFORE changing anything ───────────
    with get_session() as session:
        candidates = session.execute(
            select(Candidate).where(Candidate.jd_id == jd_id)
        ).scalars().all()

        # Step A: snapshot current ranks
        old_rank_map = {str(c.id): (c.rank or 99) for c in candidates}

        # Step B: score everyone
        scored = []
        for cand in candidates:
            feats  = cand.features or {}
            X_pred = np.array([[
                feats.get("skill_overlap", 0),
                feats.get("semantic_sim", 0),
                feats.get("exp_gap", 0),
                feats.get("keyword_density", 0),
            ]])
            scored.append({
                "candidate_id": str(cand.id),
                "name":         cand.name,
                "fit_score":    round(float(model.predict_proba(X_pred)[0][1]), 4),
                "features":     feats,
                "decision":     decision_map.get(str(cand.id)),  # ← preserved
            })

        # Step C: sort by new score
        scored.sort(key=lambda x: x["fit_score"], reverse=True)

        # Step D: assign new ranks and compute rank_change from snapshotted old rank
        new_ranked = []
        for new_rank, item in enumerate(scored, start=1):
            old_rank    = old_rank_map[item["candidate_id"]]
            rank_change = old_rank - new_rank   # positive = moved UP ← FIXED

            cand = session.get(Candidate, item["candidate_id"])
            if cand:
                cand.prev_rank = old_rank
                cand.rank      = new_rank
                cand.fit_score = item["fit_score"]

            new_ranked.append({
                **item,
                "rank":        new_rank,
                "prev_rank":   old_rank,
                "rank_change": rank_change,
            })

        session.commit()

    return {**state, "importances": importances, "new_ranked": new_ranked}
