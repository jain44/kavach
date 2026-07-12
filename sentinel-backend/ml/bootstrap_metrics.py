"""
Kavach -- Bootstrap Confidence Intervals
Computes 95% Confidence Intervals (CI) via 1,000-iteration bootstrap resampling
on the final model's test predictions. Updates `model_metrics.json` with results.
"""

import sys
import json
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import roc_auc_score, precision_score, recall_score, confusion_matrix

# Add parent directory to system path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from ml.feature_engineering import FEATURE_COLS, LABEL_COL
from ml.train_model import time_based_split

def run_bootstrap_metrics(y_true, probs, threshold, num_iterations=1000):
    """Run bootstrap resampling on y_true and probs to compute 95% CIs for metrics."""
    n = len(y_true)
    indices = np.arange(n)
    
    boot_auc = []
    boot_recall = []
    boot_precision = []
    boot_fpr = []
    boot_p10 = []
    
    np.random.seed(42)
    for _ in range(num_iterations):
        boot_idx = np.random.choice(indices, size=n, replace=True)
        y_b = y_true[boot_idx]
        probs_b = probs[boot_idx]
        
        # Binary predictions at threshold
        preds_b = (probs_b >= threshold).astype(int)
        
        # Precision @ Top 10%
        p10_thresh = np.percentile(probs_b, 90)
        preds_p10 = (probs_b >= p10_thresh).astype(int)
        p10 = precision_score(y_b, preds_p10, zero_division=0)
        
        # Metrics
        auc = roc_auc_score(y_b, probs_b)
        rec = recall_score(y_b, preds_b, zero_division=0)
        prec = precision_score(y_b, preds_b, zero_division=0)
        
        tn, fp, fn, tp = confusion_matrix(y_b, preds_b).ravel()
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        
        boot_auc.append(auc)
        boot_recall.append(rec)
        boot_precision.append(prec)
        boot_fpr.append(fpr)
        boot_p10.append(p10)
        
    def get_ci(vals):
        return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))
        
    return {
        "auc_roc": get_ci(boot_auc),
        "recall": get_ci(boot_recall),
        "precision": get_ci(boot_precision),
        "false_positive_rate": get_ci(boot_fpr),
        "precision_at_top10pct": get_ci(boot_p10)
    }

def main():
    print("=" * 60)
    print("  Kavach -- Bootstrap Confidence Intervals")
    print("=" * 60)

    # 1. Resolve current active version
    models_dir = BASE_DIR / "models"
    current_txt = models_dir / "current_version.txt"
    if not current_txt.exists():
        print(f"Error: current_version.txt not found at {current_txt}. Run pipeline first.")
        sys.exit(1)
        
    with open(current_txt, "r") as f:
        curr_version = f.read().strip()
    versioned_dir = models_dir / curr_version
    print(f"Active model version: {curr_version}")
    
    # 2. Load model
    model_path = versioned_dir / "model_unified.pkl"
    if not model_path.exists():
        print(f"Error: Unified model not found at {model_path}")
        sys.exit(1)
        
    # Standard classes injection for joblib load
    import sys
    import ml.train_model
    sys.modules["__main__"].IsotonicCalibratedXGB = ml.train_model.IsotonicCalibratedXGB
    sys.modules["__main__"]._SHAPEstimatorWrapper = ml.train_model._SHAPEstimatorWrapper
    
    model = joblib.load(model_path)
    print("Unified model loaded successfully.")

    # 3. Load feature matrix and slice test set
    feat_path = BASE_DIR / "data" / "generated" / "features.csv"
    df = pd.read_csv(feat_path)
    _, _, test_df = time_based_split(df)
    print(f"Loaded test set: {len(test_df):,} rows")

    # Load current metrics JSON
    metrics_json_path = versioned_dir / "model_metrics.json"
    with open(metrics_json_path, "r") as f:
        metrics = json.load(f)
        
    threshold = metrics["classification_threshold"]
    print(f"Classification threshold: {threshold}")

    # 4. Run bootstrap for overall test metrics
    print("\nRunning bootstrap for overall metrics...")
    y_test_all = test_df[LABEL_COL].values
    probs_all = model.predict_proba(test_df[FEATURE_COLS])[:, 1]
    overall_ci = run_bootstrap_metrics(y_test_all, probs_all, threshold)
    
    # Update overall metrics in JSON
    for metric, ci in overall_ci.items():
        metrics["overall_test_metrics"][f"{metric}_ci_2p5"] = round(ci[0], 4)
        metrics["overall_test_metrics"][f"{metric}_ci_97p5"] = round(ci[1], 4)

    # 5. Run bootstrap per segment
    print("\nRunning bootstrap per loan type segment...")
    from ml.train_model import LOAN_TYPES
    
    segment_ci_dict = {}
    for lt in LOAN_TYPES:
        print(f"  Segment: {lt}...")
        lt_df = test_df[test_df["loan_type"] == lt]
        y_test_lt = lt_df[LABEL_COL].values
        probs_lt = model.predict_proba(lt_df[FEATURE_COLS])[:, 1]
        
        ci_res = run_bootstrap_metrics(y_test_lt, probs_lt, threshold)
        segment_ci_dict[lt] = ci_res

    # Update per segment metrics in JSON
    for seg_m in metrics["per_segment_metrics"]:
        lt = seg_m["loan_type"]
        if lt in segment_ci_dict:
            for metric, ci in segment_ci_dict[lt].items():
                seg_m[f"{metric}_ci_2p5"] = round(ci[0], 4)
                seg_m[f"{metric}_ci_97p5"] = round(ci[1], 4)

    # 6. Compute Average Metrics CIs (mean across segments)
    print("\nComputing Average Metrics CIs...")
    avg_ci = {}
    for metric in ["auc_roc", "precision_at_top10pct", "recall", "false_positive_rate"]:
        seg_cis_2p5 = [segment_ci_dict[lt][metric][0] for lt in LOAN_TYPES]
        seg_cis_97p5 = [segment_ci_dict[lt][metric][1] for lt in LOAN_TYPES]
        avg_ci[metric] = (float(np.mean(seg_cis_2p5)), float(np.mean(seg_cis_97p5)))
        
    metrics["avg_auc_roc_ci_2p5"] = round(avg_ci["auc_roc"][0], 4)
    metrics["avg_auc_roc_ci_97p5"] = round(avg_ci["auc_roc"][1], 4)
    
    metrics["avg_precision_at_top10_ci_2p5"] = round(avg_ci["precision_at_top10pct"][0], 4)
    metrics["avg_precision_at_top10_ci_97p5"] = round(avg_ci["precision_at_top10pct"][1], 4)
    
    metrics["avg_recall_ci_2p5"] = round(avg_ci["recall"][0], 4)
    metrics["avg_recall_ci_97p5"] = round(avg_ci["recall"][1], 4)
    
    metrics["avg_false_positive_rate_ci_2p5"] = round(avg_ci["false_positive_rate"][0], 4)
    metrics["avg_false_positive_rate_ci_97p5"] = round(avg_ci["false_positive_rate"][1], 4)

    # Save metrics back to JSON
    with open(metrics_json_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nSuccessfully computed and saved bootstrap CIs to: {metrics_json_path}")

if __name__ == "__main__":
    main()
