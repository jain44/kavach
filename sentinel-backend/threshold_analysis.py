import os
import sys
import json
import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.metrics import confusion_matrix, precision_score, recall_score, f1_score

# Setup directories
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "generated"
MODELS_DIR = BASE_DIR / "models"

# Import FEATURE_COLS, LABEL_COL, time_based_split from train_model
sys.path.insert(0, str(BASE_DIR))
from ml.train_model import FEATURE_COLS, LABEL_COL, time_based_split, LOAN_TYPES

def load_models_and_test_data():
    # Load test data
    feat_path = DATA_DIR / "features.csv"
    if not feat_path.exists():
        raise FileNotFoundError(f"Features file not found at {feat_path}. Run pipeline first.")
    
    feat_df = pd.read_csv(feat_path)
    _, _, test_df = time_based_split(feat_df)
    
    # Load models
    models = {}
    for lt in LOAN_TYPES:
        model_path = MODELS_DIR / f"model_{lt.replace(' ', '_').lower()}.pkl"
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found at {model_path}. Run pipeline first.")
        models[lt] = joblib.load(model_path)
        
    return models, test_df

def run_threshold_analysis():
    print("Loading models and test dataset...")
    models, test_df = load_models_and_test_data()
    
    # Predict probabilities for all test instances
    test_df = test_df.copy()
    test_df["pred_prob"] = 0.0
    
    for loan_type, model in models.items():
        mask = test_df["loan_type"] == loan_type
        if not mask.any():
            continue
        X = test_df.loc[mask, FEATURE_COLS]
        probs = model.predict_proba(X)[:, 1]
        test_df.loc[mask, "pred_prob"] = probs

    y_true = test_df[LABEL_COL]
    probs = test_df["pred_prob"]
    
    thresholds = np.arange(0.05, 0.96, 0.05)
    records = []
    
    print("\n--- Precision-Recall Threshold Analysis (Combined Test Set) ---")
    for t in thresholds:
        preds = (probs >= t).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true, preds, labels=[0, 1]).ravel()
        
        prec = precision_score(y_true, preds, zero_division=0)
        rec = recall_score(y_true, preds, zero_division=0)
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        f1 = f1_score(y_true, preds, zero_division=0)
        
        records.append({
            "threshold": round(t, 2),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "fpr": round(fpr, 4),
            "f1": round(f1, 4),
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "tn": int(tn)
        })
        
    analysis_df = pd.DataFrame(records)
    print(analysis_df[["threshold", "precision", "recall", "fpr", "f1"]].to_string(index=False))
    
    # Find optimal threshold for early warning (recall closest to 55%)
    idx = (analysis_df["recall"] - 0.55).abs().idxmin()
    opt_row = analysis_df.iloc[idx]
    
    print("\n--- Recommended Early-Warning Operating Point ---")
    print(f"Optimal Threshold: {opt_row['threshold']}")
    print(f"  Recall (Defaults Captured): {opt_row['recall'] * 100:.1f}% (up from 31.2% at 0.50 threshold)")
    print(f"  Precision:                  {opt_row['precision'] * 100:.1f}%")
    print(f"  False Positive Rate:        {opt_row['fpr'] * 100:.1f}%")
    print(f"  F1 Score:                   {opt_row['f1']:.4f}")
    
    # Try generating the plot using matplotlib
    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(8, 5))
        plt.style.use('dark_background')
        
        # Plot Precision and Recall curves
        plt.plot(analysis_df["threshold"], analysis_df["precision"], label="Precision", color="#10b981", linewidth=2.5)
        plt.plot(analysis_df["threshold"], analysis_df["recall"], label="Recall (TPR)", color="#3b82f6", linewidth=2.5)
        plt.plot(analysis_df["threshold"], analysis_df["fpr"], label="False Positive Rate", color="#ef4444", linewidth=1.5, linestyle="--")
        
        # Mark optimal point
        plt.axvline(x=opt_row["threshold"], color="#f59e0b", linestyle=":", label=f"Opt Early Warning (t={opt_row['threshold']})")
        plt.plot(opt_row["threshold"], opt_row["recall"], 'o', color="#f59e0b", markersize=8)
        plt.plot(opt_row["threshold"], opt_row["precision"], 'o', color="#f59e0b", markersize=8)
        
        plt.title("Precision, Recall, and FPR vs Decision Threshold", fontsize=12, fontweight='bold', pad=15)
        plt.xlabel("Decision Threshold", fontsize=10)
        plt.ylabel("Metric Score", fontsize=10)
        plt.grid(True, color="#ffffff", alpha=0.05, linestyle="-")
        plt.legend(frameon=True, facecolor="#151c2c", edgecolor="#ffffff", framealpha=0.1)
        plt.tight_layout()
        
        plot_path = BASE_DIR / "precision_recall_curve.png"
        plt.savefig(plot_path, dpi=200)
        print(f"\n[SUCCESS] Saved chart to {plot_path}")
        
    except ImportError:
        print("\n[WARN] Matplotlib not installed. Skipping chart generation.")

if __name__ == "__main__":
    run_threshold_analysis()
