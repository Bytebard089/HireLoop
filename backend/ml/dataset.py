"""
Generates 200-row synthetic labelled dataset for initial XGBoost training.
Run: python ml/dataset.py
"""
import os
import random
import pandas as pd
import numpy as np

SEED_PATH = os.getenv("SEED_DATASET_PATH", "./ml/seed_dataset.csv")
FEATURES  = ["skill_overlap", "semantic_sim", "exp_gap", "keyword_density"]
N         = 200
RANDOM_SEED = 42


def _add_noise(val: float, sigma: float = 0.05) -> float:
    return float(np.clip(val + random.gauss(0, sigma), 0.0, 1.0))


def generate(path: str = SEED_PATH, n: int = N) -> pd.DataFrame:
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    rows = []

    # 90 clear positives
    for _ in range(90):
        rows.append({
            "skill_overlap":   _add_noise(random.uniform(0.65, 1.0)),
            "semantic_sim":    _add_noise(random.uniform(0.55, 1.0)),
            "exp_gap":         _add_noise(random.uniform(0.0,  0.25)),
            "keyword_density": _add_noise(random.uniform(0.55, 1.0)),
            "label": 1,
        })

    # 90 clear negatives
    for _ in range(90):
        rows.append({
            "skill_overlap":   _add_noise(random.uniform(0.0,  0.35)),
            "semantic_sim":    _add_noise(random.uniform(0.0,  0.40)),
            "exp_gap":         _add_noise(random.uniform(0.4,  1.0)),
            "keyword_density": _add_noise(random.uniform(0.0,  0.35)),
            "label": 0,
        })

    # 20 ambiguous (borderline) — makes model non-trivially separable
    for _ in range(20):
        label = random.choice([0, 1])
        base  = 0.45 + random.uniform(-0.1, 0.1)
        rows.append({
            "skill_overlap":   _add_noise(base, 0.1),
            "semantic_sim":    _add_noise(base, 0.1),
            "exp_gap":         _add_noise(1 - base, 0.1),
            "keyword_density": _add_noise(base, 0.1),
            "label": label,
        })

    df = pd.DataFrame(rows)
    df = df.clip(0.0, 1.0)

    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    df.to_csv(path, index=False)
    print(f"[dataset] Wrote {len(df)} rows to {path}")
    return df


if __name__ == "__main__":
    generate()
