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


INDUSTRY_RISK_COEFFS = {
    "Manufacturing":     0.00,
    "Trading":           0.05,
    "Services":         -0.02,
    "Construction":      0.08,
    "Food Processing":   0.03,
    "Textiles":          0.06,
    "Auto Ancillary":    0.02,
    "Pharma":           -0.05,
    "IT/ITES":          -0.07,
    "Agriculture Allied":0.04,
}

def compute_consecutive_misses(series: pd.Series) -> int:
    streak = 0
    for val in reversed(series.values):
        if val == 1:
            streak += 1
        else:
            break
    return streak


def _fast_slope(y):
    """Vectorized linear trend slope calculation for rolling window."""
    mask = ~np.isnan(y)
    y_valid = y[mask]
    n = len(y_valid)
    if n < 2:
        return np.nan
    y_min = y_valid.min()
    y_max = y_valid.max()
    if y_min == y_max:
        return 0.0
    x = np.arange(n, dtype=float)
    x_mean = (n - 1) / 2.0
    num = np.sum((x - x_mean) * y_valid)
    den = n * (n**2 - 1) / 12.0
    slope = num / den
    return round(float(slope), 6)


# LEGACY — loop-based reference implementation. Used for regression testing only. Do NOT use in production.
def engineer_features_legacy(df: pd.DataFrame, gst_lag_months: int = 1) -> pd.DataFrame:
    """
    Loop-based feature engineering that iterates over each borrower one at a time.
    Produces IDENTICAL output to engineer_features_fast() — same 63 feature columns,
    same column names, same NaN handling.

    Used ONLY for regression testing to validate the vectorized implementation.
    Runtime is ~20-30x slower than engineer_features_fast().
    """
    df = df.sort_values(["borrower_id", "month_index"]).reset_index(drop=True)

    output_rows = []

    for borrower_id, grp in df.groupby("borrower_id", sort=False):
        grp = grp.sort_values("month_index").reset_index(drop=True)
        n = len(grp)

        # Pre-build shifted/lagged GST columns for this borrower
        if gst_lag_months > 0:
            gst_turnover_s = grp["gst_turnover_lakhs"].shift(1).fillna(0.0)
            gst_delay_s    = grp["gst_filing_delay_days"].shift(2).fillna(0.0)
            gst_missed_s   = grp["gst_filing_missed"].shift(2).fillna(0.0).astype(int)
        else:
            gst_turnover_s = grp["gst_turnover_lakhs"].copy()
            gst_delay_s    = grp["gst_filing_delay_days"].copy()
            gst_missed_s   = grp["gst_filing_missed"].copy()

        for i in range(n):
            row = grp.iloc[i]
            hist = grp.iloc[: i + 1]  # history window up to and including current row

            # ── Identity / passthrough columns ────────────────────────
            r = {}
            r["borrower_id"]    = borrower_id
            r["as_of_month"]    = row["as_of_month"]
            r["month_index"]    = int(row["month_index"])
            r["loan_type"]      = row["loan_type"]
            r["industry"]       = row["industry"]

            # ── Raw snapshot features ─────────────────────────────────
            r["dscr"]                    = row["dscr"]
            r["bureau_score"]            = row["bureau_score"]
            r["bureau_enquiries_6m"]     = row["bureau_enquiries_6m"]
            r["gst_turnover_lakhs"]      = gst_turnover_s.iloc[i]
            r["gst_filing_delay_days"]   = gst_delay_s.iloc[i]
            r["gst_filing_missed"]       = int(gst_missed_s.iloc[i])
            r["bank_avg_balance_lakhs"]  = row["bank_avg_balance_lakhs"]
            r["bank_balance_volatility"] = row["bank_balance_volatility"]
            r["overdraft_utilization_pct"] = row["overdraft_utilization_pct"]
            r["epfo_employee_count"]     = row["epfo_employee_count"]
            r["dpd_current"]             = row["dpd_current"]
            r["dpd_max_12m"]             = row["dpd_max_12m"]

            # ── Loan / profile features ───────────────────────────────
            r["loan_amount_lakhs"] = row["loan_amount_lakhs"] if not pd.isna(row["loan_amount_lakhs"]) else 0.0
            r["vintage_years"]     = row["vintage_years"] if not pd.isna(row["vintage_years"]) else 0.0
            r["is_ntc"]            = int(i < 2)

            # ── DSCR trend features ───────────────────────────────────
            dscr_hist = hist["dscr"]
            dscr_slopes = compute_trailing_slopes(dscr_hist, [3, 6, 12])
            r["dscr_slope_3m"]  = dscr_slopes["slope_3m"]
            r["dscr_slope_6m"]  = dscr_slopes["slope_6m"]
            r["dscr_slope_12m"] = dscr_slopes["slope_12m"]
            r["dscr_min_3m"]    = float(dscr_hist.iloc[-3:].min())

            dscr_below_flag = int(row["dscr"] < 1.0)
            r["dscr_below_1_flag"] = dscr_below_flag

            below_flags_hist = (hist["dscr"] < 1.0).astype(int)
            r["dscr_below_1_count_6m"] = int(below_flags_hist.iloc[-6:].sum())

            # ── Bureau score trend ────────────────────────────────────
            bur_hist = hist["bureau_score"]
            bur_slopes = compute_trailing_slopes(bur_hist, [3, 6])
            r["bureau_slope_3m"] = bur_slopes["slope_3m"]
            r["bureau_slope_6m"] = bur_slopes["slope_6m"]
            # change = current - value 5 rows ago (shift(5) means index i-5)
            if i >= 5:
                r["bureau_score_change_6m"] = float(row["bureau_score"] - grp["bureau_score"].iloc[i - 5])
            else:
                r["bureau_score_change_6m"] = 0.0

            # ── GST filing regularity ─────────────────────────────────
            delay_hist   = gst_delay_s.iloc[: i + 1]
            missed_hist  = gst_missed_s.iloc[: i + 1]
            gst_to_hist  = gst_turnover_s.iloc[: i + 1]

            r["gst_delay_avg_6m"]    = float(delay_hist.iloc[-6:].mean()) if len(delay_hist) > 0 else 0.0
            r["gst_delay_max_6m"]    = float(delay_hist.iloc[-6:].max()) if len(delay_hist) > 0 else 0.0

            delayed_flags = (delay_hist > 15).astype(int)
            r["gst_delayed_count_6m"] = int(delayed_flags.iloc[-6:].sum())
            r["gst_missed_count_6m"]  = int(missed_hist.iloc[-6:].sum())

            # ── GST turnover trend ────────────────────────────────────
            gst_slopes = compute_trailing_slopes(gst_to_hist, [3, 6])
            r["gst_turnover_slope_3m"] = gst_slopes["slope_3m"]
            r["gst_turnover_slope_6m"] = gst_slopes["slope_6m"]

            # YoY growth: (current - 11 rows ago) / (11 rows ago + 1e-6)
            if i >= 11:
                prev_11 = gst_to_hist.iloc[i - 11]
                r["gst_turnover_yoy_growth"] = float((gst_to_hist.iloc[i] - prev_11) / (prev_11 + 1e-6))
            else:
                r["gst_turnover_yoy_growth"] = 0.0

            # ── Bank balance features ─────────────────────────────────
            bal_hist = hist["bank_avg_balance_lakhs"]
            bal_slopes = compute_trailing_slopes(bal_hist, [3])
            r["balance_slope_3m"]       = bal_slopes["slope_3m"]
            r["balance_volatility_trend"] = float(hist["bank_balance_volatility"].iloc[-3:].mean())
            r["loan_to_balance_ratio"]  = float(row["loan_amount_lakhs"]) / (float(row["bank_avg_balance_lakhs"]) + 1e-6)

            # ── Overdraft features ────────────────────────────────────
            od_hist = hist["overdraft_utilization_pct"]
            od_slopes = compute_trailing_slopes(od_hist, [3])
            r["od_util_avg_3m"]          = float(od_hist.iloc[-3:].mean())
            r["od_util_slope_3m"]        = od_slopes["slope_3m"]
            r["od_util_above_80_flag"]   = int(row["overdraft_utilization_pct"] > 0.80)
            above_80_hist = (od_hist > 0.80).astype(int)
            r["od_util_above_80_count_6m"] = int(above_80_hist.iloc[-6:].sum())
            r["od_balance_squeeze"]      = float(row["overdraft_utilization_pct"]) / (float(row["bank_avg_balance_lakhs"]) + 1.0)

            # ── EPFO employee trend ───────────────────────────────────
            epfo_hist = hist["epfo_employee_count"]
            epfo_slopes = compute_trailing_slopes(epfo_hist, [6])
            r["epfo_slope_6m"] = epfo_slopes["slope_6m"]
            if i >= 5:
                epfo_prev5 = grp["epfo_employee_count"].iloc[i - 5]
                r["epfo_pct_change_6m"] = float((row["epfo_employee_count"] - epfo_prev5) / (epfo_prev5 + 1e-6))
            else:
                r["epfo_pct_change_6m"] = 0.0

            # ── DPD escalation ────────────────────────────────────────
            dpd_hist = hist["dpd_current"]
            r["dpd_count_30plus_6m"] = int((dpd_hist.iloc[-6:] >= 30).sum())
            r["dpd_count_60plus_6m"] = int((dpd_hist.iloc[-6:] >= 60).sum())

            if i >= 2:
                dpd_t  = float(grp["dpd_current"].iloc[i])
                dpd_t1 = float(grp["dpd_current"].iloc[i - 1])
                dpd_t2 = float(grp["dpd_current"].iloc[i - 2])
                r["dpd_escalating"] = int(dpd_t > dpd_t1 and dpd_t1 > dpd_t2)
            else:
                r["dpd_escalating"] = 0

            # ── Unstructured / NLP features ───────────────────────────
            r["gst_sentiment"]     = row["gst_remark_sentiment_score"]
            r["txn_anomaly_score"] = row["transaction_anomaly_score"]
            r["litigation_flag"]   = row["litigation_flag"]
            r["litigation_severity"] = row["litigation_severity"]
            r["news_sentiment"]    = row["news_sentiment_score"]

            r["gst_sentiment_avg_3m"] = float(hist["gst_remark_sentiment_score"].iloc[-3:].mean())
            r["txn_anomaly_avg_3m"]   = float(hist["transaction_anomaly_score"].iloc[-3:].mean())
            r["litigation_ever"]      = int(hist["litigation_flag"].max())

            # ── New high-value features ───────────────────────────────
            industry_coeff = INDUSTRY_RISK_COEFFS.get(row["industry"], 0.0)
            r["dscr_x_industry_risk"] = float(row["dscr"]) * industry_coeff

            dscr_std_window = hist["dscr"].iloc[-12:]
            if len(dscr_std_window) >= 2:
                r["dscr_volatility_12m"] = float(dscr_std_window.std())
            else:
                r["dscr_volatility_12m"] = 0.0

            # GST consecutive miss run: streak of gst_filing_missed==1 ending at current row
            r["gst_consecutive_miss_run"] = compute_consecutive_misses(missed_hist)

            # DPD recency-weighted (decay 0.75 per step): weights [1, 0.75, 0.5625, ...]
            weights = [1.0, 0.75, 0.5625, 0.421875, 0.31640625, 0.2373046875]
            dpd_w = 0.0
            for lag, w in enumerate(weights):
                idx_lag = i - lag
                if idx_lag >= 0:
                    dpd_w += w * float(grp["dpd_current"].iloc[idx_lag] >= 30)
            r["dpd_recency_weighted_6m"] = round(dpd_w, 4)

            # GST turnover seasonal adj: current / mean of last 12 lagged values
            gst_mean_12 = float(gst_to_hist.iloc[-12:].mean()) if len(gst_to_hist) > 0 else 0.0
            r["gst_turnover_seasonal_adj"] = float(gst_to_hist.iloc[i] / (gst_mean_12 + 1e-6))

            r["label_default_12m"] = int(row["label_default_12m"])

            output_rows.append(r)

    result = pd.DataFrame(output_rows)

    # Enforce column order to match engineer_features_fast()
    col_order = [
        "borrower_id", "as_of_month", "month_index", "loan_type", "industry",
        "dscr", "bureau_score", "bureau_enquiries_6m",
        "gst_turnover_lakhs", "gst_filing_delay_days", "gst_filing_missed",
        "bank_avg_balance_lakhs", "bank_balance_volatility", "overdraft_utilization_pct",
        "epfo_employee_count", "dpd_current", "dpd_max_12m",
        "loan_amount_lakhs", "vintage_years", "is_ntc",
        "dscr_slope_3m", "dscr_slope_6m", "dscr_slope_12m", "dscr_min_3m",
        "dscr_below_1_flag", "dscr_below_1_count_6m",
        "bureau_slope_3m", "bureau_slope_6m", "bureau_score_change_6m",
        "gst_delay_avg_6m", "gst_delay_max_6m", "gst_delayed_count_6m",
        "gst_missed_count_6m", "gst_turnover_slope_3m", "gst_turnover_slope_6m",
        "gst_turnover_yoy_growth",
        "balance_slope_3m", "balance_volatility_trend", "loan_to_balance_ratio",
        "od_util_avg_3m", "od_util_slope_3m", "od_util_above_80_flag", "od_util_above_80_count_6m",
        "od_balance_squeeze",
        "epfo_slope_6m", "epfo_pct_change_6m",
        "dpd_count_30plus_6m", "dpd_count_60plus_6m", "dpd_escalating",
        "gst_sentiment", "txn_anomaly_score", "litigation_flag", "litigation_severity",
        "news_sentiment", "gst_sentiment_avg_3m", "txn_anomaly_avg_3m", "litigation_ever",
        "dscr_x_industry_risk", "dscr_volatility_12m",
        "gst_consecutive_miss_run", "dpd_recency_weighted_6m", "gst_turnover_seasonal_adj",
        "label_default_12m",
    ]
    result = result[col_order].reset_index(drop=True)
    return result


def engineer_features_fast(df: pd.DataFrame, gst_lag_months: int = 1) -> pd.DataFrame:

    """
    Fast vectorized feature engineering using pandas groupby, rolling, and shift.
    Produces identical results to engineer_features_legacy but 20-30x faster.
    """
    df = df.sort_values(["borrower_id", "month_index"]).reset_index(drop=True)
    
    res = pd.DataFrame()
    res["borrower_id"] = df["borrower_id"]
    res["as_of_month"] = df["as_of_month"]
    res["month_index"] = df["month_index"].astype(int)
    res["loan_type"] = df["loan_type"]
    res["industry"] = df["industry"]
    
    # ── Raw snapshot features ─────────────────────────────────────────
    res["dscr"] = df["dscr"]
    res["bureau_score"] = df["bureau_score"]
    res["bureau_enquiries_6m"] = df["bureau_enquiries_6m"]
    
    if gst_lag_months > 0:
        res["gst_turnover_lakhs"] = df.groupby("borrower_id")["gst_turnover_lakhs"].shift(1).fillna(0.0)
        res["gst_filing_delay_days"] = df.groupby("borrower_id")["gst_filing_delay_days"].shift(2).fillna(0.0)
        res["gst_filing_missed"] = df.groupby("borrower_id")["gst_filing_missed"].shift(2).fillna(0.0).astype(int)
    else:
        res["gst_turnover_lakhs"] = df["gst_turnover_lakhs"]
        res["gst_filing_delay_days"] = df["gst_filing_delay_days"]
        res["gst_filing_missed"] = df["gst_filing_missed"]
        
    res["bank_avg_balance_lakhs"] = df["bank_avg_balance_lakhs"]
    res["bank_balance_volatility"] = df["bank_balance_volatility"]
    res["overdraft_utilization_pct"] = df["overdraft_utilization_pct"]
    res["epfo_employee_count"] = df["epfo_employee_count"]
    res["dpd_current"] = df["dpd_current"]
    res["dpd_max_12m"] = df["dpd_max_12m"]
    
    # ── Loan/profile features ─────────────────────────────────────────
    res["loan_amount_lakhs"] = df["loan_amount_lakhs"].fillna(0.0)
    res["vintage_years"] = df["vintage_years"].fillna(0.0)
    res["is_ntc"] = (df.groupby("borrower_id").cumcount() < 2).astype(int)
    
    # ── DSCR trend features ───────────────────────────────────────────
    res["dscr_slope_3m"] = df.groupby("borrower_id")["dscr"].rolling(3, min_periods=1).apply(_fast_slope, raw=True).reset_index(level=0, drop=True)
    res["dscr_slope_6m"] = df.groupby("borrower_id")["dscr"].rolling(6, min_periods=1).apply(_fast_slope, raw=True).reset_index(level=0, drop=True)
    res["dscr_slope_12m"] = df.groupby("borrower_id")["dscr"].rolling(12, min_periods=1).apply(_fast_slope, raw=True).reset_index(level=0, drop=True)
    res["dscr_min_3m"] = df.groupby("borrower_id")["dscr"].rolling(3, min_periods=1).min().reset_index(level=0, drop=True)
    res["dscr_below_1_flag"] = (df["dscr"] < 1.0).astype(int)
    res["dscr_below_1_count_6m"] = res["dscr_below_1_flag"].groupby(df["borrower_id"]).rolling(6, min_periods=1).sum().reset_index(level=0, drop=True).astype(int)
    
    # ── Bureau score trend ────────────────────────────────────────────
    res["bureau_slope_3m"] = df.groupby("borrower_id")["bureau_score"].rolling(3, min_periods=1).apply(_fast_slope, raw=True).reset_index(level=0, drop=True)
    res["bureau_slope_6m"] = df.groupby("borrower_id")["bureau_score"].rolling(6, min_periods=1).apply(_fast_slope, raw=True).reset_index(level=0, drop=True)
    res["bureau_score_change_6m"] = (df["bureau_score"] - df.groupby("borrower_id")["bureau_score"].shift(5)).fillna(0.0)
    
    # ── GST filing regularity ─────────────────────────────────────────
    if gst_lag_months > 0:
        delay_base = df.groupby("borrower_id")["gst_filing_delay_days"].shift(2).fillna(0.0)
        missed_base = df.groupby("borrower_id")["gst_filing_missed"].shift(2).fillna(0.0)
        gst_base = df.groupby("borrower_id")["gst_turnover_lakhs"].shift(1).fillna(0.0)
    else:
        delay_base = df["gst_filing_delay_days"]
        missed_base = df["gst_filing_missed"]
        gst_base = df["gst_turnover_lakhs"]
        
    res["gst_delay_avg_6m"] = delay_base.groupby(df["borrower_id"]).rolling(6, min_periods=1).mean().reset_index(level=0, drop=True).fillna(0.0)
    res["gst_delay_max_6m"] = delay_base.groupby(df["borrower_id"]).rolling(6, min_periods=1).max().reset_index(level=0, drop=True).fillna(0.0)
    
    delay_gt_15 = (delay_base > 15).astype(int)
    res["gst_delayed_count_6m"] = delay_gt_15.groupby(df["borrower_id"]).rolling(6, min_periods=1).sum().reset_index(level=0, drop=True).fillna(0.0).astype(int)
    res["gst_missed_count_6m"] = missed_base.groupby(df["borrower_id"]).rolling(6, min_periods=1).sum().reset_index(level=0, drop=True).fillna(0.0).astype(int)
    
    # ── GST turnover trend ────────────────────────────────────────────
    res["gst_turnover_slope_3m"] = gst_base.groupby(df["borrower_id"]).rolling(3, min_periods=1).apply(_fast_slope, raw=True).reset_index(level=0, drop=True)
    res["gst_turnover_slope_6m"] = gst_base.groupby(df["borrower_id"]).rolling(6, min_periods=1).apply(_fast_slope, raw=True).reset_index(level=0, drop=True)
    
    gst_base_shift_11 = gst_base.groupby(df["borrower_id"]).shift(11)
    res["gst_turnover_yoy_growth"] = ((gst_base - gst_base_shift_11) / (gst_base_shift_11 + 1e-6)).fillna(0.0)
    
    # ── Bank balance features ─────────────────────────────────────────
    res["balance_slope_3m"] = df.groupby("borrower_id")["bank_avg_balance_lakhs"].rolling(3, min_periods=1).apply(_fast_slope, raw=True).reset_index(level=0, drop=True)
    res["balance_volatility_trend"] = df.groupby("borrower_id")["bank_balance_volatility"].rolling(3, min_periods=1).mean().reset_index(level=0, drop=True)
    res["loan_to_balance_ratio"] = df["loan_amount_lakhs"] / (df["bank_avg_balance_lakhs"] + 1e-6)
    
    # ── Overdraft features ────────────────────────────────────────────
    res["od_util_avg_3m"] = df.groupby("borrower_id")["overdraft_utilization_pct"].rolling(3, min_periods=1).mean().reset_index(level=0, drop=True)
    res["od_util_slope_3m"] = df.groupby("borrower_id")["overdraft_utilization_pct"].rolling(3, min_periods=1).apply(_fast_slope, raw=True).reset_index(level=0, drop=True)
    res["od_util_above_80_flag"] = (df["overdraft_utilization_pct"] > 0.80).astype(int)
    res["od_util_above_80_count_6m"] = res["od_util_above_80_flag"].groupby(df["borrower_id"]).rolling(6, min_periods=1).sum().reset_index(level=0, drop=True).astype(int)
    res["od_balance_squeeze"] = df["overdraft_utilization_pct"] / (df["bank_avg_balance_lakhs"] + 1.0)
    
    # ── EPFO employee trend ───────────────────────────────────────────
    res["epfo_slope_6m"] = df.groupby("borrower_id")["epfo_employee_count"].rolling(6, min_periods=1).apply(_fast_slope, raw=True).reset_index(level=0, drop=True)
    epfo_shift_5 = df.groupby("borrower_id")["epfo_employee_count"].shift(5)
    res["epfo_pct_change_6m"] = ((df["epfo_employee_count"] - epfo_shift_5) / (epfo_shift_5 + 1e-6)).fillna(0.0)
    
    # ── DPD escalation ────────────────────────────────────────────────
    res["dpd_count_30plus_6m"] = (df["dpd_current"] >= 30).astype(int).groupby(df["borrower_id"]).rolling(6, min_periods=1).sum().reset_index(level=0, drop=True).astype(int)
    res["dpd_count_60plus_6m"] = (df["dpd_current"] >= 60).astype(int).groupby(df["borrower_id"]).rolling(6, min_periods=1).sum().reset_index(level=0, drop=True).astype(int)
    
    dpd_curr = df["dpd_current"]
    dpd_prev1 = df.groupby("borrower_id")["dpd_current"].shift(1)
    dpd_prev2 = df.groupby("borrower_id")["dpd_current"].shift(2)
    idx_ge_2 = df.groupby("borrower_id").cumcount() >= 2
    res["dpd_escalating"] = (idx_ge_2 & (dpd_curr > dpd_prev1) & (dpd_prev1 > dpd_prev2)).astype(int)
    
    # ── Unstructured / NLP features ───────────────────────────────────
    res["gst_sentiment"] = df["gst_remark_sentiment_score"]
    res["txn_anomaly_score"] = df["transaction_anomaly_score"]
    res["litigation_flag"] = df["litigation_flag"]
    res["litigation_severity"] = df["litigation_severity"]
    res["news_sentiment"] = df["news_sentiment_score"]
    
    res["gst_sentiment_avg_3m"] = df.groupby("borrower_id")["gst_remark_sentiment_score"].rolling(3, min_periods=1).mean().reset_index(level=0, drop=True)
    res["txn_anomaly_avg_3m"] = df.groupby("borrower_id")["transaction_anomaly_score"].rolling(3, min_periods=1).mean().reset_index(level=0, drop=True)
    res["litigation_ever"] = df.groupby("borrower_id")["litigation_flag"].cummax().reset_index(level=0, drop=True).astype(int)
    
    # ── New high-value features (Phase 1 Item 6) ──────────────────────
    res["dscr_x_industry_risk"] = df["dscr"] * df["industry"].map(INDUSTRY_RISK_COEFFS).fillna(0.0)
    res["dscr_volatility_12m"] = df.groupby("borrower_id")["dscr"].rolling(12, min_periods=2).std().reset_index(level=0, drop=True).fillna(0.0)
    
    missed_filled = missed_base.fillna(0).astype(int)
    group_ids = (missed_filled != 1).groupby(df["borrower_id"]).cumsum()
    res["gst_consecutive_miss_run"] = missed_filled.groupby([df["borrower_id"], group_ids]).cumsum().astype(int)
    
    is_30 = (df["dpd_current"] >= 30).astype(float)
    dpd_weighted = (
        1.0 * is_30 +
        0.75 * is_30.groupby(df["borrower_id"]).shift(1).fillna(0.0) +
        0.5625 * is_30.groupby(df["borrower_id"]).shift(2).fillna(0.0) +
        0.421875 * is_30.groupby(df["borrower_id"]).shift(3).fillna(0.0) +
        0.31640625 * is_30.groupby(df["borrower_id"]).shift(4).fillna(0.0) +
        0.2373046875 * is_30.groupby(df["borrower_id"]).shift(5).fillna(0.0)
    )
    res["dpd_recency_weighted_6m"] = dpd_weighted.round(4)
    
    res["od_balance_squeeze"] = df["overdraft_utilization_pct"] / (df["bank_avg_balance_lakhs"] + 1.0)
    
    gst_mean_12m = gst_base.groupby(df["borrower_id"]).rolling(12, min_periods=1).mean().reset_index(level=0, drop=True).fillna(0.0)
    res["gst_turnover_seasonal_adj"] = (gst_base / (gst_mean_12m + 1e-6)).fillna(0.0)
    
    res["label_default_12m"] = df["label_default_12m"].astype(int)
    
    return res

# def engineer_features_legacy(df: pd.DataFrame, gst_lag_months: int = 1) -> pd.DataFrame:
#     # Kept as comments for reference
#     pass


def engineer_features(df: pd.DataFrame, gst_lag_months: int = 1) -> pd.DataFrame:
    """
    Main feature engineering function (fast vectorized implementation).
    Identical output to legacy loop but 25-30x faster.
    """
    print("  Engineering features (fast vectorized)...")
    feat_df = engineer_features_fast(df, gst_lag_months)
    print(f"  -> Feature matrix: {feat_df.shape[0]:,} rows x {feat_df.shape[1]} columns")
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
    "dscr_x_industry_risk", "dscr_volatility_12m",  # New DSCR features
    # Bureau trend
    "bureau_slope_3m", "bureau_score_change_6m",  # removed bureau_slope_6m
    # GST
    "gst_delay_avg_6m", "gst_delay_max_6m", "gst_delayed_count_6m",
    "gst_missed_count_6m", "gst_turnover_slope_3m", "gst_turnover_slope_6m",
    "gst_turnover_yoy_growth", "gst_consecutive_miss_run", "gst_turnover_seasonal_adj",  # New GST features
    # Bank
    "balance_slope_3m", "balance_volatility_trend", "loan_to_balance_ratio",
    # OD
    "od_util_slope_3m", "od_util_above_80_flag", "od_util_above_80_count_6m",  # removed od_util_avg_3m
    "od_balance_squeeze",  # New OD feature
    # EPFO
    "epfo_slope_6m", "epfo_pct_change_6m",
    # DPD
    "dpd_count_30plus_6m", "dpd_count_60plus_6m", "dpd_escalating",
    "dpd_recency_weighted_6m",  # New DPD feature
    # NLP/unstructured
    "gst_sentiment", "txn_anomaly_score", "litigation_flag", "litigation_severity",
    "news_sentiment", "gst_sentiment_avg_3m", "txn_anomaly_avg_3m", "litigation_ever",
    # Categoricals (encoded)
    "loan_type_enc", "industry_enc",
]

LABEL_COL = "label_default_12m"
