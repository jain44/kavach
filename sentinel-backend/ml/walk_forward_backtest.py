"""
Kavach -- Walk-Forward Backtesting
Implement rolling-window backtesting across three training/validation/testing windows.
Generates `models/model_decay_curve.png` to trace performance stability.
"""

import sys
import os
import time
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import roc_auc_score, precision_score, recall_score, confusion_matrix

# Add parent directory to system path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from ml.feature_engineering import FEATURE_COLS, LABEL_COL
from ml.train_model import train_segment_model, tune_threshold

WINDOWS = [
    {
        "name": "Window 1 (Months 15-17)",
        "train_end": 11,
        "val_start": 12, "val_end": 14,
        "test_start": 15, "test_end": 17
    },
    {
        "name": "Window 2 (Months 18-20)",
        "train_end": 14,
        "val_start": 15, "val_end": 17,
        "test_start": 18, "test_end": 20
    },
    {
        "name": "Window 3 (Months 21-23)",
        "train_end": 17,
        "val_start": 18, "val_end": 20,
        "test_start": 21, "test_end": 23
    }
]

def main():
    print("=" * 60)
    print("  Kavach -- Walk-Forward Backtesting")
    print("=" * 60)

    # Load feature engineered data
    feat_path = BASE_DIR / "data" / "generated" / "features.csv"
    if not feat_path.exists():
        print(f"Error: Feature matrix not found at {feat_path}. Run pipeline first.")
        sys.exit(1)

    print(f"Loading features from {feat_path}...")
    df = pd.read_csv(feat_path)

    # Exclude post-default rows (dpd_current >= 90) as per compliance rules
    df_active = df[df["dpd_current"] < 90].copy() if "dpd_current" in df.columns else df.copy()

    results = []
    aucs = []

    for idx, w in enumerate(WINDOWS):
        print(f"\nEvaluating {w['name']}...")
        
        train_df = df_active[df_active["month_index"] <= w["train_end"]].copy()
        val_df = df_active[(df_active["month_index"] >= w["val_start"]) & (df_active["month_index"] <= w["val_end"])].copy()
        test_df = df_active[(df_active["month_index"] >= w["test_start"]) & (df_active["month_index"] <= w["test_end"])].copy()

        # Train model
        model, _ = train_segment_model(train_df, val_df, f"W{idx+1}_Unified")

        # Tune threshold
        threshold = tune_threshold(model, val_df[FEATURE_COLS], val_df[LABEL_COL], max_fpr=0.15)
        print(f"    Tuned Threshold: {threshold:.2f}")

        # Predict
        test_probs = model.predict_proba(test_df[FEATURE_COLS])[:, 1]
        test_preds = (test_probs >= threshold).astype(int)
        y_test = test_df[LABEL_COL]

        # Calculate metrics
        auc = float(roc_auc_score(y_test, test_probs))
        prec = float(precision_score(y_test, test_preds, zero_division=0))
        rec = float(recall_score(y_test, test_preds, zero_division=0))
        
        tn, fp, fn, tp = confusion_matrix(y_test, test_preds).ravel()
        fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

        print(f"    Test AUC-ROC: {auc:.4f} | Precision: {prec:.4f} | Recall: {rec:.4f} | FPR: {fpr:.4f}")
        
        results.append({
            "window": w["name"],
            "auc": auc,
            "precision": prec,
            "recall": rec,
            "fpr": fpr
        })
        aucs.append(auc)

    # Compute summary stats
    res_df = pd.DataFrame(results)
    print("\n" + "=" * 60)
    print("  WALK-FORWARD BACKTEST SUMMARY")
    print("=" * 60)
    print(res_df.to_string(index=False))
    print("-" * 60)

    means = res_df.mean(numeric_only=True)
    stds = res_df.std(numeric_only=True)

    for col in ["auc", "precision", "recall", "fpr"]:
        print(f"Mean {col.upper():<9}: {means[col]:.4f} ± {stds[col]:.4f}")

    # Plot AUC per window
    plt.figure(figsize=(8, 5))
    plt.plot([1, 2, 3], aucs, marker='o', linewidth=2, color='#b45309', label='Test AUC')
    plt.xticks([1, 2, 3], ["Window 1\n(M15-17)", "Window 2\n(M18-20)", "Window 3\n(M21-23)"])
    plt.ylim(0.70, 0.85)
    plt.ylabel('AUC-ROC')
    plt.title('Sentinel Walk-Forward Backtesting (Model Decay / Growth Curve)')
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend()
    
    # Ensure models dir exists
    models_dir = BASE_DIR / "models"
    models_dir.mkdir(exist_ok=True)
    
    import json
    backtest_results_path = models_dir / "model_backtest_results.json"
    with open(backtest_results_path, "w") as f:
        json.dump(results, f, indent=4)
    print(f"Backtest results JSON saved to: {backtest_results_path}")

    plot_path = models_dir / "model_decay_curve.png"
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\nDecay curve plotted successfully to: {plot_path}")

if __name__ == "__main__":
    main()
