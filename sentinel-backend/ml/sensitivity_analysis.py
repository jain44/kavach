"""
Kavach -- Sensitivity Analysis on Synthetic Data assumptions
Re-runs the data generation, feature engineering, and model training pipeline under three different generator configurations:
a) Baseline
b) 50% Reduced Industry Risk Deltas
c) 15% Increased Background Noise Rate
"""

import sys
import os
import shutil
import re
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score

# Add parent directory to system path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from run_pipeline import step_generate_data, step_feature_engineering
from ml.feature_engineering import FEATURE_COLS, LABEL_COL
from ml.train_model import train_segment_model, tune_threshold, time_based_split, LOAN_TYPES

GEN_PATH = BASE_DIR / "data" / "generate_msme_data.py"
BACKUP_PATH = BASE_DIR / "data" / "generate_msme_data.py.bak"

def backup_generator():
    shutil.copy(GEN_PATH, BACKUP_PATH)

def restore_generator():
    if BACKUP_PATH.exists():
        shutil.copy(BACKUP_PATH, GEN_PATH)
        os.remove(BACKUP_PATH)

def modify_generator(reduced_industry_risk=False, noise_rate=0.08, n_borrowers=1000):
    """Modify generate_msme_data.py contents programmatically."""
    with open(BACKUP_PATH, "r") as f:
        content = f.read()

    # Modify N_BORROWERS
    content = content.replace("N_BORROWERS = 5000", f"N_BORROWERS = {n_borrowers}")

    # Modify industry risk deltas
    if reduced_industry_risk:
        # We replace the industry risk dictionary values with 50% reduced ones
        industry_risk_block = """    industry_risk = {
        "Manufacturing":     0.00,
        "Trading":           0.025,
        "Services":         -0.01,
        "Construction":      0.04,
        "Food Processing":   0.015,
        "Textiles":          0.03,
        "Auto Ancillary":    0.01,
        "Pharma":           -0.025,
        "IT/ITES":          -0.035,
        "Agriculture Allied":0.02,
    }"""
        content = re.sub(r"    industry_risk = \{.*?\}", industry_risk_block, content, flags=re.DOTALL)

    # Modify background noise rate
    if noise_rate != 0.08:
        # Replace: p_stress = (0.35 + 0.50 * depth) if in_window else 0.08
        old_line = "p_stress = (0.35 + 0.50 * depth) if in_window else 0.08"
        new_line = f"p_stress = (0.35 + 0.50 * depth) if in_window else {noise_rate}"
        content = content.replace(old_line, new_line)

    with open(GEN_PATH, "w") as f:
        f.write(content)

def run_experiment_metrics():
    # 1. Run Data Generation
    print("  Running data generation...")
    step_generate_data()

    # 2. Run Feature Engineering
    print("  Running feature engineering...")
    feat_df = step_feature_engineering()

    # 3. Time based split
    train_df, val_df, test_df = time_based_split(feat_df)

    # Evaluate Unified Model
    print("  Training Unified Model...")
    unified_model, _ = train_segment_model(train_df, val_df, "Unified")
    
    # Tune Threshold
    threshold = tune_threshold(unified_model, val_df[FEATURE_COLS], val_df[LABEL_COL], max_fpr=0.15)
    
    # Test set predictions
    test_probs = unified_model.predict_proba(test_df[FEATURE_COLS])[:, 1]
    unified_auc = roc_auc_score(test_df[LABEL_COL], test_probs)

    # Evaluate Segmented Models
    print("  Training Segmented Models...")
    seg_aucs = {}
    test_n_total = 0
    seg_weighted_auc_sum = 0.0

    for lt in LOAN_TYPES:
        tr_lt = train_df[train_df["loan_type"] == lt]
        val_lt = val_df[val_df["loan_type"] == lt]
        te_lt = test_df[test_df["loan_type"] == lt]

        if len(tr_lt) == 0 or len(val_lt) == 0 or len(te_lt) == 0:
            continue

        model_lt, _ = train_segment_model(tr_lt, val_lt, f"Segment_{lt}")
        probs_lt = model_lt.predict_proba(te_lt[FEATURE_COLS])[:, 1]
        auc_lt = roc_auc_score(te_lt[LABEL_COL], probs_lt)
        
        seg_aucs[lt] = auc_lt
        test_n_total += len(te_lt)
        seg_weighted_auc_sum += auc_lt * len(te_lt)

    segmented_weighted_auc = seg_weighted_auc_sum / test_n_total if test_n_total > 0 else 0.0

    return {
        "unified_auc": float(unified_auc),
        "segmented_weighted_auc": float(segmented_weighted_auc),
        "gap": float(unified_auc - segmented_weighted_auc),
        "threshold": float(threshold),
        "segment_aucs": seg_aucs
    }

def main():
    print("=" * 60)
    print("  Kavach -- Data Generator Sensitivity Analysis")
    print("=" * 60)

    backup_generator()
    results = {}

    try:
        # Run A: Baseline Configuration
        print("\n>>> Run A: Baseline (Current settings, N_BORROWERS=1000) <<<")
        modify_generator(reduced_industry_risk=False, noise_rate=0.08, n_borrowers=1000)
        results["Baseline"] = run_experiment_metrics()
        print(f"  Baseline Results: {results['Baseline']}")

        # Run B: 50% Reduced Industry Risk Deltas
        print("\n>>> Run B: 50% Reduced Industry Risk Deltas <<<")
        restore_generator()
        backup_generator()
        modify_generator(reduced_industry_risk=True, noise_rate=0.08, n_borrowers=1000)
        results["Reduced Risk Deltas"] = run_experiment_metrics()
        print(f"  Reduced Risk Deltas Results: {results['Reduced Risk Deltas']}")

        # Run C: Increased background noise rate (15%)
        print("\n>>> Run C: 15% Background Noise Rate <<<")
        restore_generator()
        backup_generator()
        modify_generator(reduced_industry_risk=False, noise_rate=0.15, n_borrowers=1000)
        results["High Background Noise"] = run_experiment_metrics()
        print(f"  High Background Noise Results: {results['High Background Noise']}")

    finally:
        restore_generator()

    # Re-run seeder on baseline dataset to restore app state
    print("\nRestoring database state to baseline...")
    step_generate_data()
    step_feature_engineering()
    
    import subprocess
    subprocess.run([sys.executable, "-m", "db.seed"], cwd=str(BASE_DIR))

    # Print Final Sensitivity Summary Table
    print("\n" + "=" * 80)
    print("  SENSITIVITY ANALYSIS EXPERIMENTAL RESULTS")
    print("=" * 80)
    print(f"{'Configuration':<25} | {'Unified AUC':<12} | {'Segmented AUC':<14} | {'Gap (U-S)':<10} | {'Threshold':<9}")
    print("-" * 80)
    for name, r in results.items():
        print(f"{name:<25} | {r['unified_auc']:<12.4f} | {r['segmented_weighted_auc']:<14.4f} | {r['gap']:<10.4f} | {r['threshold']:<9.2f}")
    print("=" * 80)

if __name__ == "__main__":
    main()
