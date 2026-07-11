"""
Sentinel -- Master Pipeline Orchestrator
Runs the full pipeline: data generation -> feature engineering -> model training.
Run this script once to set up all data and model artifacts.
"""

import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent

# Add parent to path
sys.path.insert(0, str(BASE_DIR))

# FIX 4: Startup integrity assertion — FEATURE_COLS must be identical in both modules.
# If a developer adds a feature to feature_engineering.py but forgets to update
# train_model.py, this assert fires immediately at pipeline start instead of
# silently scoring on the wrong feature set.
from ml.feature_engineering import FEATURE_COLS as _FE_COLS
from ml.train_model import FEATURE_COLS as _TRAIN_COLS
assert _FE_COLS == _TRAIN_COLS, (
    f"FEATURE_COLS MISMATCH between feature_engineering.py and train_model.py!\n"
    f"Symmetric difference: {set(_FE_COLS) ^ set(_TRAIN_COLS)}\n"
    f"Fix: ensure train_model.py imports FEATURE_COLS from ml.feature_engineering."
)
print("  [OK] FEATURE_COLS integrity check passed — single source of truth confirmed.")

def run_step(name: str, fn):
    print(f"\n{'='*60}")
    print(f"  STEP: {name}")
    print(f"{'='*60}")
    start = time.time()
    result = fn()
    elapsed = time.time() - start
    print(f"\n  OK Completed in {elapsed:.1f}s")
    return result


def step_generate_data():
    from data.generate_msme_data import (
        generate_borrower_profiles,
        assign_default_labels,
        generate_monthly_snapshots,
        validate_and_save,
        N_BORROWERS,
    )
    from pathlib import Path

    out_dir = BASE_DIR / "data" / "generated"
    profiles = generate_borrower_profiles(N_BORROWERS)
    profiles = assign_default_labels(profiles)
    snapshots = generate_monthly_snapshots(profiles)
    full_df = validate_and_save(profiles, snapshots, out_dir)
    return full_df


def step_feature_engineering():
    import pandas as pd
    from ml.feature_engineering import engineer_features, encode_categoricals

    data_dir = BASE_DIR / "data" / "generated"
    full_df = pd.read_csv(data_dir / "full_dataset.csv")

    feat_df = engineer_features(full_df)
    feat_df = encode_categoricals(feat_df)

    feat_path = data_dir / "features.csv"
    feat_df.to_csv(feat_path, index=False)
    print(f"  Features saved: {feat_path}")
    print(f"  Shape: {feat_df.shape}")
    return feat_df


def step_train_models():
    from ml.train_model import main as train_main
    return train_main()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  SENTINEL -- Full Pipeline Run")
    print("=" * 60)

    start_total = time.time()

    run_step("1. Synthetic Data Generation", step_generate_data)
    run_step("2. Feature Engineering", step_feature_engineering)
    run_step("3. Model Training + SHAP", step_train_models)

    total = time.time() - start_total
    print(f"\n{'='*60}")
    print(f"  DONE  PIPELINE COMPLETE in {total:.0f}s")
    print(f"{'='*60}")
    print("\nNext step: start the FastAPI server with:")
    print("  python -m uvicorn api.main:app --reload --port 8000")
