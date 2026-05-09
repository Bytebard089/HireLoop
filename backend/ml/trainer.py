"""
Initial XGBoost model training with proper evaluation.
Run: python ml/trainer.py
"""
import os
import pickle
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import roc_auc_score, classification_report

# Support both module execution (`python -m ml.trainer`) and script execution
# (`python ml/trainer.py`).
try:
    from ml.dataset import generate, SEED_PATH
except ModuleNotFoundError:
    from dataset import generate, SEED_PATH

MODEL_PATH = os.getenv("MODEL_PATH", "./ml/model.pkl")
FEATURES   = ["skill_overlap", "semantic_sim", "exp_gap", "keyword_density"]


def train_initial_model(
    seed_path: str = SEED_PATH,
    model_path: str = MODEL_PATH,
) -> xgb.XGBClassifier:
    if not os.path.exists(seed_path):
        generate(seed_path)

    df = pd.read_csv(seed_path)
    X  = df[FEATURES].values
    y  = df["label"].values

    # ── Class imbalance weight ────────────────────────────────────────────────
    n_neg = int((y == 0).sum())
    n_pos = int((y == 1).sum())
    scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

    # ── Train / validation split (stratified) ────────────────────────────────
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    # ── Model (max_depth=3 avoids over-fitting on 4 features / ~160 rows) ───
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train)

    # ── Evaluation metrics ────────────────────────────────────────────────────
    y_prob = model.predict_proba(X_val)[:, 1]
    y_pred = model.predict(X_val)
    auc    = roc_auc_score(y_val, y_prob)

    # 5-fold cross-validated AUC on full dataset for a more stable estimate
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_aucs = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")

    print(f"[trainer] Val AUC:      {auc:.4f}")
    print(f"[trainer] CV AUC:       {np.mean(cv_aucs):.4f} ± {np.std(cv_aucs):.4f}")
    print(f"[trainer] Val report:")
    print(classification_report(y_val, y_pred, target_names=["reject", "approve"]))

    # ── Refit on full dataset for deployment ─────────────────────────────────
    model.fit(X, y)

    os.makedirs(os.path.dirname(model_path) if os.path.dirname(model_path) else ".", exist_ok=True)
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    importances = dict(zip(FEATURES, model.feature_importances_.tolist()))
    print(f"[trainer] Model saved to {model_path}")
    print(f"[trainer] Feature importances: {importances}")
    return model


if __name__ == "__main__":
    train_initial_model()
