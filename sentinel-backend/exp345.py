"""
Experiment 3: Reliability diagram (calibration curve)
Experiment 4: Hyperparameter search (20-iter RandomizedSearchCV)
Experiment 5: Live inference latency timing
"""
import pandas as pd
import numpy as np
import warnings
import time
import json
warnings.filterwarnings('ignore')
np.random.seed(42)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.calibration import calibration_curve
from sklearn.model_selection import RandomizedSearchCV, GroupShuffleSplit
from sklearn.metrics import roc_auc_score, make_scorer
from sklearn.isotonic import IsotonicRegression
import xgboost as xgb

from ml.feature_engineering import FEATURE_COLS
from ml.train_model import time_based_split, LOAN_TYPES, XGB_PARAMS, IsotonicCalibratedXGB, calculate_percentile_anchors
import joblib
from pathlib import Path

LABEL_COL = 'label_default_12m'
MODELS_DIR = Path('models')
feat_df = pd.read_csv('data/generated/features.csv')
train_df, val_df, test_df = time_based_split(feat_df)

# ─────────────────────────────────────────────
# EXPERIMENT 3: Reliability Diagram
# ─────────────────────────────────────────────
print("=" * 55)
print("EXPERIMENT 3: Calibration Reliability Diagrams")
print("=" * 55)

fig, axes = plt.subplots(1, 3, figsize=(15, 5))
fig.suptitle('Calibration Reliability Diagrams — Kavach Models', fontsize=13, fontweight='bold')

for idx, lt in enumerate(LOAN_TYPES):
    model_path = MODELS_DIR / f"model_{lt.replace(' ', '_').lower()}.pkl"
    if not model_path.exists():
        print(f"  SKIP {lt}: model file not found")
        continue

    model = joblib.load(model_path)
    lt_val = val_df[val_df['loan_type'] == lt]
    lt_test = test_df[test_df['loan_type'] == lt]

    # Use val+test combined for more points in the diagram
    eval_df = pd.concat([lt_val, lt_test])
    if len(eval_df) < 20:
        print(f"  SKIP {lt}: insufficient eval data")
        continue

    X_eval = eval_df[FEATURE_COLS]
    y_eval = eval_df[LABEL_COL]
    probs = model.predict_proba(X_eval)[:, 1]

    # Calibration curve
    n_bins = 8
    fraction_of_positives, mean_predicted = calibration_curve(y_eval, probs, n_bins=n_bins, strategy='quantile')

    ax = axes[idx]
    ax.plot([0, 1], [0, 1], 'k--', linewidth=1, label='Perfect calibration')
    ax.plot(mean_predicted, fraction_of_positives, 's-', color='#d8ab57',
            linewidth=2, markersize=6, label='Model calibration')
    ax.fill_between(mean_predicted, fraction_of_positives, mean_predicted,
                    alpha=0.15, color='#d8ab57')
    ax.set_xlabel('Mean Predicted Probability', fontsize=10)
    ax.set_ylabel('Fraction of Positives', fontsize=10)
    ax.set_title(f'{lt}', fontsize=11, fontweight='bold')
    ax.legend(fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.3)
    ax.set_facecolor('#0d0e11')
    fig.patch.set_facecolor('#1a1b1f')
    ax.tick_params(colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    ax.title.set_color('white')
    for spine in ax.spines.values():
        spine.set_edgecolor('#444')

    # Compute calibration error
    cal_error = np.mean(np.abs(fraction_of_positives - mean_predicted))
    print(f"  {lt}: Mean Absolute Calibration Error = {cal_error:.4f}")
    # Over/under confidence assessment
    overconf_bins = np.sum(mean_predicted > fraction_of_positives)
    underconf_bins = np.sum(mean_predicted < fraction_of_positives)
    print(f"    Over-confident bins: {overconf_bins}/{n_bins}  |  Under-confident bins: {underconf_bins}/{n_bins}")

plt.tight_layout()
plt.savefig('data/generated/calibration_reliability_diagram.png', dpi=120, bbox_inches='tight',
            facecolor='#1a1b1f')
plt.close()
print("  Saved: data/generated/calibration_reliability_diagram.png")
print()

# ─────────────────────────────────────────────
# EXPERIMENT 4: Hyperparameter Search
# ─────────────────────────────────────────────
print("=" * 55)
print("EXPERIMENT 4: Hyperparameter Search (20-iter RandomizedSearchCV)")
print("=" * 55)

# Use Working Capital (largest segment) for search
lt = 'Working Capital'
lt_train = train_df[train_df['loan_type'] == lt]
lt_val   = val_df[val_df['loan_type'] == lt]
combined = pd.concat([lt_train, lt_val])
X_comb = combined[FEATURE_COLS]
y_comb = combined[LABEL_COL]

n_neg = int((y_comb == 0).sum())
n_pos = int((y_comb == 1).sum())
base_spw = round(n_neg / max(n_pos, 1), 2)

param_dist = {
    'n_estimators':    [200, 300, 400, 500, 600],
    'max_depth':       [3, 4, 5, 6, 7],
    'learning_rate':   [0.01, 0.03, 0.05, 0.08, 0.10],
    'subsample':       [0.6, 0.7, 0.8, 0.9],
    'colsample_bytree':[0.6, 0.7, 0.8, 0.9],
    'min_child_weight':[3, 5, 8, 10, 15],
    'gamma':           [0.0, 0.05, 0.1, 0.2],
    'reg_alpha':       [0.0, 0.05, 0.1, 0.5],
    'reg_lambda':      [0.5, 1.0, 2.0, 5.0],
}

base_xgb = xgb.XGBClassifier(
    scale_pos_weight=base_spw,
    eval_metric='auc',
    random_state=42,
    n_jobs=-1,
    verbosity=0,
    early_stopping_rounds=30,
)

# Time-respecting cross-val: train on first 18 months, validate on 18-20
train_mask = combined['month_index'] <= 17
val_mask   = combined['month_index'].between(18, 20)
train_pos  = np.where(train_mask.values)[0].tolist()
val_pos    = np.where(val_mask.values)[0].tolist()
cv_split   = [(train_pos, val_pos)]

print(f"  Search: 20 iterations, time-split CV on {lt} segment")
print(f"  Base AUC (current params): ", end='', flush=True)

# Current params baseline
curr_params = dict(XGB_PARAMS)
curr_params['early_stopping_rounds'] = 30
curr_model = xgb.XGBClassifier(**curr_params, scale_pos_weight=base_spw)
curr_model.fit(lt_train[FEATURE_COLS], lt_train[LABEL_COL],
               eval_set=[(lt_val[FEATURE_COLS], lt_val[LABEL_COL])],
               verbose=False)
curr_probs = curr_model.predict_proba(lt_val[FEATURE_COLS])[:, 1]
curr_auc = roc_auc_score(lt_val[LABEL_COL], curr_probs)
print(f"{curr_auc:.4f}")

search = RandomizedSearchCV(
    base_xgb, param_dist, n_iter=20, scoring='roc_auc',
    cv=cv_split, refit=False, random_state=42, n_jobs=1, verbose=0
)
search.fit(X_comb, y_comb)

best_params = search.best_params_
best_cv_auc = search.best_score_

# Retrain with best params on train, eval on val
best_model = xgb.XGBClassifier(
    **best_params,
    scale_pos_weight=base_spw,
    eval_metric='auc',
    early_stopping_rounds=30,
    random_state=42, n_jobs=-1, verbosity=0,
)
best_model.fit(lt_train[FEATURE_COLS], lt_train[LABEL_COL],
               eval_set=[(lt_val[FEATURE_COLS], lt_val[LABEL_COL])],
               verbose=False)
best_val_probs = best_model.predict_proba(lt_val[FEATURE_COLS])[:, 1]
best_val_auc = roc_auc_score(lt_val[LABEL_COL], best_val_probs)

print(f"  Best AUC found (search): {best_cv_auc:.4f}")
print(f"  Best AUC (retrained on val): {best_val_auc:.4f}")
print(f"  Improvement over baseline: {best_val_auc - curr_auc:+.4f}")
print(f"  Best params found:")
for k, v in sorted(best_params.items()):
    curr_v = XGB_PARAMS.get(k, 'N/A')
    changed = ' <-- CHANGED' if str(v) != str(curr_v) else ''
    print(f"    {k}: {v}  (current: {curr_v}){changed}")
print()

# ─────────────────────────────────────────────
# EXPERIMENT 5: Live Inference Latency
# ─────────────────────────────────────────────
print("=" * 55)
print("EXPERIMENT 5: Live Inference Latency Measurement")
print("=" * 55)

# Load models
models = {}
for lt in LOAN_TYPES:
    mp = MODELS_DIR / f"model_{lt.replace(' ', '_').lower()}.pkl"
    if mp.exists():
        models[lt] = joblib.load(mp)

# Load snapshots
import sys
sys.path.insert(0, '.')
import ml.train_model as tm
sys.modules['__main__'].IsotonicCalibratedXGB = tm.IsotonicCalibratedXGB
sys.modules['__main__']._SHAPEstimatorWrapper = tm._SHAPEstimatorWrapper

snapshots_df = pd.read_csv('data/generated/monthly_snapshots.csv')
profiles_df  = pd.read_csv('data/generated/borrower_profiles.csv')

from ml.feature_engineering import engineer_features, encode_categoricals
from ml.train_model import pd_to_stress_score, stress_score_to_grade, compute_shap_explanations
import shap

# Pick 5 different borrowers for timing
test_bids = profiles_df['borrower_id'].iloc[:5].tolist()

latencies_fe   = []  # feature engineering only
latencies_shap_nocache = []  # SHAP with new explainer per call (current)
latencies_shap_cached  = []  # SHAP with cached explainer (proposed)

# Pre-cache explainers (proposed fix)
cached_explainers = {}
for lt, model in models.items():
    try:
        base = model.calibrated_classifiers_[0].estimator
        cached_explainers[lt] = shap.TreeExplainer(base)
    except Exception as e:
        print(f"  WARN: Could not cache explainer for {lt}: {e}")

print(f"  Timing 5 borrowers, 3 runs each (p50/p95 reported)...")
print()

for bid in test_bids:
    history = snapshots_df[snapshots_df['borrower_id'] == bid].copy()
    profile_row = profiles_df[profiles_df['borrower_id'] == bid].iloc[0]
    for col in ['loan_amount_lakhs', 'vintage_years']:
        history[col] = profile_row[col]
    lt = profile_row['loan_type']
    model = models.get(lt, list(models.values())[0])

    runs_fe, runs_noc, runs_cac = [], [], []
    for _ in range(3):
        # Feature engineering timing
        t0 = time.perf_counter()
        fd = engineer_features(history)
        fd = encode_categoricals(fd)
        X = fd.iloc[[-1]][FEATURE_COLS]
        t1 = time.perf_counter()
        runs_fe.append((t1 - t0) * 1000)

        # SHAP NO cache (current behaviour)
        t0 = time.perf_counter()
        _ = compute_shap_explanations(model, X, top_n=5)
        t1 = time.perf_counter()
        runs_noc.append((t1 - t0) * 1000)

        # SHAP with cached explainer
        t0 = time.perf_counter()
        if lt in cached_explainers:
            sv = cached_explainers[lt].shap_values(X)
        t1 = time.perf_counter()
        runs_cac.append((t1 - t0) * 1000)

    latencies_fe.append(np.median(runs_fe))
    latencies_shap_nocache.append(np.median(runs_noc))
    latencies_shap_cached.append(np.median(runs_cac))

all_total_current  = np.array(latencies_fe) + np.array(latencies_shap_nocache)
all_total_proposed = np.array(latencies_fe) + np.array(latencies_shap_cached)

print(f"  Feature Engineering (per-borrower, 24 months history):")
print(f"    p50: {np.percentile(latencies_fe, 50):.1f}ms")
print(f"    p95: {np.percentile(latencies_fe, 95):.1f}ms")
print()
print(f"  SHAP — NO cache (current, new TreeExplainer per call):")
print(f"    p50: {np.percentile(latencies_shap_nocache, 50):.1f}ms")
print(f"    p95: {np.percentile(latencies_shap_nocache, 95):.1f}ms")
print()
print(f"  SHAP — WITH cache (proposed fix):")
print(f"    p50: {np.percentile(latencies_shap_cached, 50):.1f}ms")
print(f"    p95: {np.percentile(latencies_shap_cached, 95):.1f}ms")
print()
print(f"  Total /predict/live latency CURRENT  (FE + SHAP no-cache):")
print(f"    p50: {np.percentile(all_total_current, 50):.1f}ms")
print(f"    p95: {np.percentile(all_total_current, 95):.1f}ms")
print()
print(f"  Total /predict/live latency PROPOSED (FE + SHAP cached):")
print(f"    p50: {np.percentile(all_total_proposed, 50):.1f}ms")
print(f"    p95: {np.percentile(all_total_proposed, 95):.1f}ms")
speedup = np.median(all_total_current) / max(np.median(all_total_proposed), 0.1)
print(f"  Speedup from SHAP caching: {speedup:.1f}x")
print()
print("ALL EXPERIMENTS COMPLETE.")
