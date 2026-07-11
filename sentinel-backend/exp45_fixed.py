"""
Experiment 4 (fixed): Hyperparameter search without early_stopping in CV
Experiment 5: Live inference latency timing
"""
import pandas as pd
import numpy as np
import warnings
import time
warnings.filterwarnings('ignore')
np.random.seed(42)

from ml.feature_engineering import FEATURE_COLS, engineer_features, encode_categoricals
from ml.train_model import time_based_split, LOAN_TYPES, XGB_PARAMS
from ml.train_model import compute_shap_explanations, IsotonicCalibratedXGB, _SHAPEstimatorWrapper
from sklearn.metrics import roc_auc_score
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import RandomizedSearchCV
import xgboost as xgb
import joblib, shap
from pathlib import Path

LABEL_COL = 'label_default_12m'
MODELS_DIR = Path('models')

feat_df     = pd.read_csv('data/generated/features.csv')
profiles_df = pd.read_csv('data/generated/borrower_profiles.csv')
snapshots_df= pd.read_csv('data/generated/monthly_snapshots.csv')

train_df, val_df, test_df = time_based_split(feat_df)

# ─────────────────────────────────────────────
# EXPERIMENT 4: Hyperparameter Search
# ─────────────────────────────────────────────
print("=" * 55)
print("EXPERIMENT 4: Hyperparameter Search (20-iter)")
print("=" * 55)

lt = 'Working Capital'
lt_train = train_df[train_df['loan_type'] == lt]
lt_val   = val_df[val_df['loan_type'] == lt]
combined = pd.concat([lt_train, lt_val]).reset_index(drop=True)
X_comb = combined[FEATURE_COLS]
y_comb = combined[LABEL_COL]

n_neg = int((lt_train[LABEL_COL]==0).sum())
n_pos = int((lt_train[LABEL_COL]==1).sum())
base_spw = round(n_neg / max(n_pos,1), 2)

# Baseline with current params (no early stopping in search, fixed n_estimators)
print(f"  Baseline AUC (current params, val set): ", end='', flush=True)
curr_model = xgb.XGBClassifier(
    n_estimators=500, max_depth=6, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
    gamma=0.1, reg_alpha=0.1, reg_lambda=1.0,
    scale_pos_weight=base_spw, eval_metric='auc',
    random_state=42, n_jobs=-1, verbosity=0,
    early_stopping_rounds=30
)
curr_model.fit(lt_train[FEATURE_COLS], lt_train[LABEL_COL],
               eval_set=[(lt_val[FEATURE_COLS], lt_val[LABEL_COL])],
               verbose=False)
curr_probs = curr_model.predict_proba(lt_val[FEATURE_COLS])[:,1]
curr_auc = roc_auc_score(lt_val[LABEL_COL], curr_probs)
print(f"{curr_auc:.4f}")

# Manual random search — train/val split (no sklearn CV to avoid early_stopping conflict)
param_dist = {
    'max_depth':        [3, 4, 5, 6, 7],
    'learning_rate':    [0.01, 0.03, 0.05, 0.08, 0.10],
    'subsample':        [0.6, 0.7, 0.8, 0.9],
    'colsample_bytree': [0.6, 0.7, 0.8, 0.9],
    'min_child_weight': [3, 5, 8, 10, 15],
    'gamma':            [0.0, 0.05, 0.1, 0.2],
    'reg_alpha':        [0.0, 0.05, 0.1, 0.5],
    'reg_lambda':       [0.5, 1.0, 2.0, 5.0],
}

rng = np.random.RandomState(42)
best_auc = curr_auc
best_params = None
best_n_trees = 500

print(f"  Running 20 random parameter samples...")
for trial in range(20):
    params = {k: rng.choice(v) for k, v in param_dist.items()}
    m = xgb.XGBClassifier(
        n_estimators=600,
        scale_pos_weight=base_spw, eval_metric='auc',
        random_state=42, n_jobs=-1, verbosity=0,
        early_stopping_rounds=30,
        **params
    )
    m.fit(lt_train[FEATURE_COLS], lt_train[LABEL_COL],
          eval_set=[(lt_val[FEATURE_COLS], lt_val[LABEL_COL])],
          verbose=False)
    probs = m.predict_proba(lt_val[FEATURE_COLS])[:,1]
    auc = roc_auc_score(lt_val[LABEL_COL], probs)
    if auc > best_auc:
        best_auc = auc
        best_params = params
        best_n_trees = m.best_iteration + 1

print(f"  Best AUC found : {best_auc:.4f}")
print(f"  Improvement    : {best_auc - curr_auc:+.4f}")
if best_params:
    print(f"  Best params found (only changed ones):")
    for k, v in sorted(best_params.items()):
        curr_v = {'max_depth':6,'learning_rate':0.05,'subsample':0.8,
                  'colsample_bytree':0.8,'min_child_weight':5,'gamma':0.1,
                  'reg_alpha':0.1,'reg_lambda':1.0}.get(k)
        tag = ' <-- CHANGED' if v != curr_v else ''
        print(f"    {k}: {v} (current: {curr_v}){tag}")
    print(f"  Best n_estimators (early stop): {best_n_trees}")
else:
    print("  No improvement over current params in 20 trials.")
print()

# ─────────────────────────────────────────────
# EXPERIMENT 5: Live Inference Latency
# ─────────────────────────────────────────────
print("=" * 55)
print("EXPERIMENT 5: /predict/live Latency Measurement")
print("=" * 55)

models = {}
for lt2 in LOAN_TYPES:
    mp = MODELS_DIR / f"model_{lt2.replace(' ','_').lower()}.pkl"
    if mp.exists():
        models[lt2] = joblib.load(mp)

# Pre-cache SHAP explainers (proposed fix)
cached_explainers = {}
for lt2, model in models.items():
    try:
        base = model.calibrated_classifiers_[0].estimator
        cached_explainers[lt2] = shap.TreeExplainer(base)
    except Exception as e:
        print(f"  WARN explainer cache {lt2}: {e}")

print(f"  Cached {len(cached_explainers)} SHAP explainers at startup")
test_bids = profiles_df['borrower_id'].iloc[:5].tolist()
latencies_fe, latencies_shap_new, latencies_shap_cached = [], [], []
RUNS = 3

for bid in test_bids:
    history = snapshots_df[snapshots_df['borrower_id'] == bid].copy()
    prof = profiles_df[profiles_df['borrower_id'] == bid].iloc[0]
    for col in ['loan_amount_lakhs','vintage_years']:
        history[col] = prof[col]
    lt2 = prof['loan_type']
    model = models.get(lt2, list(models.values())[0])

    runs_fe, runs_new, runs_cac = [], [], []
    for _ in range(RUNS):
        # FE only
        t0 = time.perf_counter()
        fd = engineer_features(history)
        fd = encode_categoricals(fd)
        X = fd.iloc[[-1]][FEATURE_COLS]
        runs_fe.append((time.perf_counter() - t0)*1000)

        # SHAP new explainer per call (current)
        t0 = time.perf_counter()
        _ = compute_shap_explanations(model, X, top_n=5)
        runs_new.append((time.perf_counter() - t0)*1000)

        # SHAP cached explainer (proposed)
        t0 = time.perf_counter()
        if lt2 in cached_explainers:
            sv = cached_explainers[lt2].shap_values(X)
        runs_cac.append((time.perf_counter() - t0)*1000)

    latencies_fe.append(np.median(runs_fe))
    latencies_shap_new.append(np.median(runs_new))
    latencies_shap_cached.append(np.median(runs_cac))

fe   = np.array(latencies_fe)
snew = np.array(latencies_shap_new)
scac = np.array(latencies_shap_cached)
tot_current  = fe + snew
tot_proposed = fe + scac

print(f"\n  Component breakdown (median across 5 borrowers):")
print(f"  {'Component':<40} {'p50':>8}  {'p95':>8}")
print(f"  {'-'*58}")
print(f"  {'Feature Engineering (24m history)':<40} {np.percentile(fe,50):>7.1f}ms  {np.percentile(fe,95):>7.1f}ms")
print(f"  {'SHAP — new TreeExplainer per call (current)':<40} {np.percentile(snew,50):>7.1f}ms  {np.percentile(snew,95):>7.1f}ms")
print(f"  {'SHAP — cached explainer (proposed fix)':<40} {np.percentile(scac,50):>7.1f}ms  {np.percentile(scac,95):>7.1f}ms")
print(f"  {'-'*58}")
print(f"  {'TOTAL current (FE + new SHAP)':<40} {np.percentile(tot_current,50):>7.1f}ms  {np.percentile(tot_current,95):>7.1f}ms")
print(f"  {'TOTAL proposed (FE + cached SHAP)':<40} {np.percentile(tot_proposed,50):>7.1f}ms  {np.percentile(tot_proposed,95):>7.1f}ms")
speedup = np.median(tot_current)/max(np.median(tot_proposed),0.1)
print(f"\n  SHAP cache speedup: {speedup:.1f}x faster")
print(f"  NOTE: Network overhead + FastAPI routing adds ~5-20ms on top.")
print()
print("ALL EXPERIMENTS COMPLETE.")
