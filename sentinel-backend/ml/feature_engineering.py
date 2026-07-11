"""
Kavach -- Feature Engineering Module
Transforms raw monthly snapshots into rich predictive features for the XGBoost model.
All features are computed from the borrower's historical window ending at as_of_month.
"""

import numpy as np
import pandas as pd
from typing import List


# ─── Feature Engineering Pipeline ────────────────────────────────────────────

def compute_trailing_slopes(series: pd.Series, windows: List[int]) -> dict:
    """Compute linear trend slope over multiple trailing windows.

    NaN-safe: drops missing values from each window before fitting.
    Returns np.nan (not 0.0) when fewer than 2 valid points exist so that
    XGBoost can apply its learned default split direction for missing features.
    """
    result = {}
    for w in windows:
        key = f"slope_{w}m"
        # Slice the trailing window, then drop NaNs
        window_data = series.iloc[-w:].dropna() if len(series) >= w else series.dropna()
        valid_n = len(window_data)
        if valid_n >= 2:
            # Re-index time steps to [0, 1, 2, ...] using positional order
            y = window_data.values.astype(float)
            x = np.arange(valid_n, dtype=float)
            if np.std(y) > 0:
                slope = float(np.polyfit(x, y, 1)[0])
            else:
                slope = 0.0  # Truly flat (no variance), 0 is correct
            result[key] = round(slope, 6)
        else:
            # Insufficient data — return NaN so XGBoost handles via default split
            result[key] = np.nan
    return result


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Main feature engineering function. Takes the full dataset with all monthly rows
    and produces one feature row per (borrower_id, as_of_month) with rich engineered features.
    
    The label column is 'label_default_12m' -- predict default in next 12 months.
    """
    print("  Engineering features...")
    
    df = df.sort_values(["borrower_id", "month_index"]).reset_index(drop=True)
    feature_rows = []
    
    for bid, group in df.groupby("borrower_id"):
        group = group.sort_values("month_index").reset_index(drop=True)
        n = len(group)
        
        for i in range(n):
            row = group.iloc[i]
            hist = group.iloc[: i + 1]  # history up to and including this month
            
            feats = {
                "borrower_id": bid,
                "as_of_month": row["as_of_month"],
                "month_index": int(row["month_index"]),
                "loan_type": row["loan_type"],
                "industry": row["industry"],
            }
            
            # ── Raw snapshot features ─────────────────────────────────────────
            feats["dscr"] = row["dscr"]
            feats["bureau_score"] = row["bureau_score"]
            feats["bureau_enquiries_6m"] = row["bureau_enquiries_6m"]
            feats["gst_turnover_lakhs"] = row["gst_turnover_lakhs"]
            feats["gst_filing_delay_days"] = row["gst_filing_delay_days"]
            feats["gst_filing_missed"] = row["gst_filing_missed"]
            feats["bank_avg_balance_lakhs"] = row["bank_avg_balance_lakhs"]
            feats["bank_balance_volatility"] = row["bank_balance_volatility"]
            feats["overdraft_utilization_pct"] = row["overdraft_utilization_pct"]
            feats["epfo_employee_count"] = row["epfo_employee_count"]
            feats["dpd_current"] = row["dpd_current"]
            feats["dpd_max_12m"] = row["dpd_max_12m"]
            
            # ── Loan/profile features ─────────────────────────────────────────
            feats["loan_amount_lakhs"] = row.get("loan_amount_lakhs", 0)
            feats["vintage_years"] = row.get("vintage_years", 0)
            feats["is_ntc"] = int(len(hist) < 3)
            
            # ── DSCR trend features ───────────────────────────────────────────
            dscr_hist = hist["dscr"]
            slopes = compute_trailing_slopes(dscr_hist, [3, 6, 12])
            feats["dscr_slope_3m"] = slopes["slope_3m"]
            feats["dscr_slope_6m"] = slopes["slope_6m"]
            feats["dscr_slope_12m"] = slopes["slope_12m"]
            feats["dscr_min_3m"] = float(dscr_hist.iloc[-3:].min()) if len(dscr_hist) >= 3 else float(dscr_hist.min())
            feats["dscr_below_1_flag"] = int(row["dscr"] < 1.0)
            feats["dscr_below_1_count_6m"] = int((hist["dscr"].iloc[-6:] < 1.0).sum()) if len(hist) >= 6 else int((hist["dscr"] < 1.0).sum())
            
            # ── Bureau score trend ────────────────────────────────────────────
            bureau_hist = hist["bureau_score"]
            bslopes = compute_trailing_slopes(bureau_hist, [3, 6])
            feats["bureau_slope_3m"] = bslopes["slope_3m"]
            feats["bureau_slope_6m"] = bslopes["slope_6m"]
            feats["bureau_score_change_6m"] = float(bureau_hist.iloc[-1] - bureau_hist.iloc[-6]) if len(bureau_hist) >= 6 else 0.0
            
            # ── GST filing regularity ─────────────────────────────────────────
            gst_delay_hist = hist["gst_filing_delay_days"]
            feats["gst_delay_avg_6m"] = float(gst_delay_hist.iloc[-6:].mean()) if len(gst_delay_hist) >= 6 else float(gst_delay_hist.mean())
            feats["gst_delay_max_6m"] = float(gst_delay_hist.iloc[-6:].max()) if len(gst_delay_hist) >= 6 else float(gst_delay_hist.max())
            feats["gst_delayed_count_6m"] = int((hist["gst_filing_delay_days"].iloc[-6:] > 15).sum()) if len(hist) >= 6 else int((hist["gst_filing_delay_days"] > 15).sum())
            feats["gst_missed_count_6m"] = int(hist["gst_filing_missed"].iloc[-6:].sum()) if len(hist) >= 6 else int(hist["gst_filing_missed"].sum())
            
            # ── GST turnover trend ────────────────────────────────────────────
            gst_hist = hist["gst_turnover_lakhs"]
            gst_slopes = compute_trailing_slopes(gst_hist, [3, 6, 12])
            feats["gst_turnover_slope_3m"] = gst_slopes["slope_3m"]
            feats["gst_turnover_slope_6m"] = gst_slopes["slope_6m"]
            feats["gst_turnover_yoy_growth"] = float((gst_hist.iloc[-1] - gst_hist.iloc[-12]) / (gst_hist.iloc[-12] + 1e-6)) if len(gst_hist) >= 12 else 0.0
            
            # ── Bank balance features ─────────────────────────────────────────
            bal_hist = hist["bank_avg_balance_lakhs"]
            feats["balance_slope_3m"] = compute_trailing_slopes(bal_hist, [3])["slope_3m"]
            feats["balance_volatility_trend"] = float(hist["bank_balance_volatility"].iloc[-3:].mean()) if len(hist) >= 3 else float(hist["bank_balance_volatility"].mean())
            feats["loan_to_balance_ratio"] = float(row.get("loan_amount_lakhs", 0) / (row["bank_avg_balance_lakhs"] + 1e-6))
            
            # ── Overdraft features ────────────────────────────────────────────
            od_hist = hist["overdraft_utilization_pct"]
            feats["od_util_avg_3m"] = float(od_hist.iloc[-3:].mean()) if len(od_hist) >= 3 else float(od_hist.mean())
            feats["od_util_slope_3m"] = compute_trailing_slopes(od_hist, [3])["slope_3m"]
            feats["od_util_above_80_flag"] = int(row["overdraft_utilization_pct"] > 0.80)
            feats["od_util_above_80_count_6m"] = int((od_hist.iloc[-6:] > 0.80).sum()) if len(od_hist) >= 6 else int((od_hist > 0.80).sum())
            
            # ── EPFO employee trend ───────────────────────────────────────────
            epfo_hist = hist["epfo_employee_count"]
            feats["epfo_slope_6m"] = compute_trailing_slopes(epfo_hist, [6])["slope_6m"]
            feats["epfo_pct_change_6m"] = float((epfo_hist.iloc[-1] - epfo_hist.iloc[-6]) / (epfo_hist.iloc[-6] + 1e-6)) if len(epfo_hist) >= 6 else 0.0
            
            # ── DPD escalation ────────────────────────────────────────────────
            dpd_hist = hist["dpd_current"]
            feats["dpd_count_30plus_6m"] = int((dpd_hist.iloc[-6:] >= 30).sum()) if len(dpd_hist) >= 6 else int((dpd_hist >= 30).sum())
            feats["dpd_count_60plus_6m"] = int((dpd_hist.iloc[-6:] >= 60).sum()) if len(dpd_hist) >= 6 else int((dpd_hist >= 60).sum())
            feats["dpd_escalating"] = int(
                len(dpd_hist) >= 3 and
                dpd_hist.iloc[-1] > dpd_hist.iloc[-2] > dpd_hist.iloc[-3]
            )
            
            # ── Unstructured / NLP features ───────────────────────────────────
            feats["gst_sentiment"] = row["gst_remark_sentiment_score"]
            feats["txn_anomaly_score"] = row["transaction_anomaly_score"]
            feats["litigation_flag"] = row["litigation_flag"]
            feats["litigation_severity"] = row["litigation_severity"]
            feats["news_sentiment"] = row["news_sentiment_score"]
            
            # Trailing NLP aggregates
            feats["gst_sentiment_avg_3m"] = float(hist["gst_remark_sentiment_score"].iloc[-3:].mean()) if len(hist) >= 3 else float(hist["gst_remark_sentiment_score"].mean())
            feats["txn_anomaly_avg_3m"] = float(hist["transaction_anomaly_score"].iloc[-3:].mean()) if len(hist) >= 3 else float(hist["transaction_anomaly_score"].mean())
            feats["litigation_ever"] = int(hist["litigation_flag"].any())
            
            # ── Label ─────────────────────────────────────────────────────────
            feats["label_default_12m"] = int(row["label_default_12m"])
            
            feature_rows.append(feats)
    
    feat_df = pd.DataFrame(feature_rows)
    print(f"  -> Feature matrix: {feat_df.shape[0]:,} rows × {feat_df.shape[1]} columns")
    return feat_df


# ─── Categorical Encoding ─────────────────────────────────────────────────────

LOAN_TYPE_MAP = {
    "Working Capital": 0,
    "Term Loan": 1,
    "Trade Finance": 2,
}

INDUSTRY_MAP = {
    "Manufacturing": 0, "Trading": 1, "Services": 2, "Construction": 3,
    "Food Processing": 4, "Textiles": 5, "Auto Ancillary": 6, "Pharma": 7,
    "IT/ITES": 8, "Agriculture Allied": 9,
}


def encode_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["loan_type_enc"] = df["loan_type"].map(LOAN_TYPE_MAP).fillna(-1).astype(int)
    df["industry_enc"] = df["industry"].map(INDUSTRY_MAP).fillna(-1).astype(int)
    return df


# ─── Feature column lists ─────────────────────────────────────────────────────

FEATURE_COLS = [
    # Raw snapshot
    "dscr", "bureau_score", "bureau_enquiries_6m", "gst_turnover_lakhs",
    "gst_filing_delay_days", "gst_filing_missed", "bank_avg_balance_lakhs",
    "bank_balance_volatility", "overdraft_utilization_pct", "epfo_employee_count",
    "dpd_current", "dpd_max_12m", "loan_amount_lakhs", "vintage_years",
    # DSCR trend
    "dscr_slope_3m", "dscr_slope_6m", "dscr_slope_12m", "dscr_min_3m",
    "dscr_below_1_flag", "dscr_below_1_count_6m",
    # Bureau trend
    "bureau_slope_3m", "bureau_slope_6m", "bureau_score_change_6m",
    # GST
    "gst_delay_avg_6m", "gst_delay_max_6m", "gst_delayed_count_6m",
    "gst_missed_count_6m", "gst_turnover_slope_3m", "gst_turnover_slope_6m",
    "gst_turnover_yoy_growth",
    # Bank
    "balance_slope_3m", "balance_volatility_trend", "loan_to_balance_ratio",
    # OD
    "od_util_avg_3m", "od_util_slope_3m", "od_util_above_80_flag",
    "od_util_above_80_count_6m",
    # EPFO
    "epfo_slope_6m", "epfo_pct_change_6m",
    # DPD
    "dpd_count_30plus_6m", "dpd_count_60plus_6m", "dpd_escalating",
    # NLP/unstructured
    "gst_sentiment", "txn_anomaly_score", "litigation_flag", "litigation_severity",
    "news_sentiment", "gst_sentiment_avg_3m", "txn_anomaly_avg_3m", "litigation_ever",
    # Categoricals (encoded)
    "loan_type_enc", "industry_enc",
]

LABEL_COL = "label_default_12m"
