"""Experiment 2: Unified vs Segment XGBoost model AUC comparison."""
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')
np.random.seed(42)

from ml.feature_engineering import FEATURE_COLS
from ml.train_model import time_based_split, LOAN_TYPES, XGB_PARAMS
from sklearn.metrics import roc_auc_score
from sklearn.isotonic import IsotonicRegression
import xgboost as xgb

feat_df = pd.read_csv('data/generated/features.csv')
LABEL_COL = 'label_default_12m'
train_df, val_df, test_df = time_based_split(feat_df)

print('=== Segment Models AUC (existing approach) ===')
seg_aucs = {}
for lt in LOAN_TYPES:
    lt_train = train_df[train_df['loan_type'] == lt]
    lt_val   = val_df[val_df['loan_type'] == lt]
    lt_test  = test_df[test_df['loan_type'] == lt]
    n_neg = int((lt_train[LABEL_COL]==0).sum())
    n_pos = int((lt_train[LABEL_COL]==1).sum())
    spw = round(n_neg / max(n_pos, 1), 2)
    m = xgb.XGBClassifier(**XGB_PARAMS, scale_pos_weight=spw, early_stopping_rounds=30)
    m.fit(lt_train[FEATURE_COLS], lt_train[LABEL_COL],
          eval_set=[(lt_val[FEATURE_COLS], lt_val[LABEL_COL])], verbose=False)
    cal = IsotonicRegression(out_of_bounds='clip')
    raw_val = m.predict_proba(lt_val[FEATURE_COLS])[:,1]
    cal.fit(raw_val, lt_val[LABEL_COL])
    try:
        probs = np.clip(cal.predict(m.predict_proba(lt_test[FEATURE_COLS])[:,1]), 0, 1)
        auc = roc_auc_score(lt_test[LABEL_COL], probs)
    except Exception:
        probs_v = np.clip(cal.predict(raw_val), 0, 1)
        auc = roc_auc_score(lt_val[LABEL_COL], probs_v)
    seg_aucs[lt] = round(auc, 4)
    print(f'  {lt}: AUC={auc:.4f}  (train={len(lt_train)}, test={len(lt_test)})')

print()
print('=== Unified Model AUC (all segments together) ===')
n_neg = int((train_df[LABEL_COL]==0).sum())
n_pos = int((train_df[LABEL_COL]==1).sum())
spw = round(n_neg / max(n_pos, 1), 2)
um = xgb.XGBClassifier(**XGB_PARAMS, scale_pos_weight=spw, early_stopping_rounds=30)
um.fit(train_df[FEATURE_COLS], train_df[LABEL_COL],
       eval_set=[(val_df[FEATURE_COLS], val_df[LABEL_COL])], verbose=False)
ucal = IsotonicRegression(out_of_bounds='clip')
ucal.fit(um.predict_proba(val_df[FEATURE_COLS])[:,1], val_df[LABEL_COL])

unified_aucs = {}
for lt in LOAN_TYPES:
    lt_test = test_df[test_df['loan_type'] == lt]
    lt_val  = val_df[val_df['loan_type'] == lt]
    try:
        probs = np.clip(ucal.predict(um.predict_proba(lt_test[FEATURE_COLS])[:,1]), 0, 1)
        auc = roc_auc_score(lt_test[LABEL_COL], probs)
    except Exception:
        probs_v = np.clip(ucal.predict(um.predict_proba(lt_val[FEATURE_COLS])[:,1]), 0, 1)
        auc = roc_auc_score(lt_val[LABEL_COL], probs_v)
    unified_aucs[lt] = round(auc, 4)
    diff = unified_aucs[lt] - seg_aucs[lt]
    sign = '+' if diff >= 0 else ''
    print(f'  {lt}: AUC={auc:.4f}  (vs segment {seg_aucs[lt]:.4f}, diff={sign}{diff:.4f})')

print()
overall_seg = round(np.mean(list(seg_aucs.values())), 4)
overall_uni = round(np.mean(list(unified_aucs.values())), 4)
diff_overall = overall_uni - overall_seg
sign = '+' if diff_overall >= 0 else ''
print(f'  Average segment AUC : {overall_seg:.4f}')
print(f'  Average unified AUC : {overall_uni:.4f}')
print(f'  Overall diff        : {sign}{diff_overall:.4f}')
if overall_uni > overall_seg:
    print('  VERDICT: UNIFIED MODEL WINS -- consider switching')
elif overall_uni < overall_seg:
    print('  VERDICT: SEGMENT MODELS WIN -- keep current approach')
else:
    print('  VERDICT: TIE')
