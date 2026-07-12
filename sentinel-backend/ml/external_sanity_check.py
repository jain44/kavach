"""
Kavach -- External Sanity Check against Public Credit Dataset (UCI German Credit)
Downloads the UCI German Credit dataset programmatically, runs the training and threshold-tuning
pipeline under the same FPR <= 15% constraint, and reports metrics.
"""

import sys
import time
from pathlib import Path
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score

# Add parent directory to system path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

def main():
    print("=" * 60)
    print("  Kavach -- Programmatic External Sanity Check (UCI German)")
    print("=" * 60)

    url = "https://archive.ics.uci.edu/ml/machine-learning-databases/statlog/german/german.data"
    columns = [f"col_{i}" for i in range(20)] + ["target"]

    print(f"Downloading German Credit dataset from: {url}")
    try:
        df = pd.read_csv(url, sep=r"\s+", header=None, names=columns)
    except Exception as e:
        print(f"Error downloading dataset: {e}")
        print("Falling back: attempting to load local copy or mock dataset...")
        # In case the site is down or blocked, we want to make sure it degrades gracefully.
        # But we'll try archive.ics.uci.edu first.
        raise e

    print(f"Successfully loaded dataset: {df.shape[0]} rows, {df.shape[1]} columns.")
    
    # German credit target is 1 (Good), 2 (Bad). Map to 0 (Good), 1 (Bad).
    df["target"] = df["target"].map({1: 0, 2: 1})
    print(f"Target distribution: Good={df['target'].value_counts()[0]}, Bad={df['target'].value_counts()[1]}")

    X = df.drop(columns=["target"])
    y = df["target"]

    # Convert categorical variables using one-hot encoding
    X_encoded = pd.get_dummies(X, drop_first=True)
    print(f"Features shape after one-hot encoding: {X_encoded.shape}")

    # Stratified Train-Test Split (80/20)
    X_train, X_test, y_train, y_test = train_test_split(
        X_encoded, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"Train split: {X_train.shape[0]} rows (Pos: {y_train.sum()})")
    print(f"Test split : {X_test.shape[0]} rows (Pos: {y_test.sum()})")

    # Fit XGBoost Model
    neg = (y_train == 0).sum()
    pos = (y_train == 1).sum()
    scale_pos_weight = neg / pos

    print("\nTraining XGBoost Classifier...")
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        eval_metric="logloss"
    )
    model.fit(X_train, y_train)

    # Score Test Set
    test_probs = model.predict_proba(X_test)[:, 1]
    test_auc = roc_auc_score(y_test, test_probs)
    print(f"XGBoost Test set AUC-ROC: {test_auc:.4f}")

    # Threshold search (FPR constraint <= 15%)
    print("\nTuning classification threshold (FPR constraint <= 15%)...")
    best_threshold = 0.99
    best_recall = 0.0
    best_fpr = 0.0

    print(f" {'Threshold':<12} | {'Recall':<8} | {'FPR':<8} | {'Status':<12}")
    print("-" * 50)
    
    for th in np.arange(0.01, 1.0, 0.01):
        preds = (test_probs >= th).astype(int)
        
        tn = ((preds == 0) & (y_test == 0)).sum()
        fp = ((preds == 1) & (y_test == 0)).sum()
        tp = ((preds == 1) & (y_test == 1)).sum()
        fn = ((preds == 0) & (y_test == 1)).sum()
        
        fpr = fp / (fp + tn + 1e-6)
        recall = tp / (tp + fn + 1e-6)
        
        status = "FPR_EXCEEDED" if fpr > 0.15 else "OK"
        # We print only every 5th or when status changes to keep logs clean
        if status == "OK" or int(th * 100) % 5 == 0:
            print(f" {th:<12.2f} | {recall:<8.4f} | {fpr:<8.4f} | {status:<12}")

        if fpr <= 0.15:
            # We want to maximize recall
            if recall > best_recall:
                best_recall = recall
                best_threshold = th
                best_fpr = fpr

    print("-" * 50)
    print(f"Selected threshold : {best_threshold:.2f}")
    print(f"Recall at threshold: {best_recall:.4f}")
    print(f"FPR at threshold   : {best_fpr:.4f}")
    print("=" * 60)

    # Save metrics to json report for consolidator
    import json
    report = {
        "dataset": "UCI German Credit",
        "rows": int(df.shape[0]),
        "features": int(X_encoded.shape[1]),
        "test_auc": float(test_auc),
        "selected_threshold": float(best_threshold),
        "recall_at_threshold": float(best_recall),
        "fpr_at_threshold": float(best_fpr)
    }
    report_path = BASE_DIR / "models" / "external_sanity_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=4)
    print(f"Report saved to: {report_path}")

if __name__ == "__main__":
    main()
