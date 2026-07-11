"""
Sentinel -- MSME Synthetic Dataset Generator  (v2 — Leakage-Free)

Key changes from v1:
  - label_default_12m and default_month are assigned BEFORE any financial
    trajectory is simulated.  No target-conditioned feature generation.
  - Financial trajectories use a PROBABILISTIC stress model:
      * Defaulters have ELEVATED P(stress signal) in an 8-month pre-default
        window — but NOT certainty. Some defaulters look healthy right up
        until default.
      * Non-defaulters exhibit occasional stress patterns too (~8% of months)
        as genuine business noise.
      * A single boolean `stressed` is drawn each month from a binomial;
        every feature independently receives noise around the stressed/healthy
        mean, so stress signals are imperfectly correlated (realistic).
  - _stress_onset_month and _is_defaulter are NOT written to
    monthly_snapshots.csv or full_dataset.csv.  They remain in
    borrower_profiles.csv as audit metadata only and never reach the
    feature-engineering or inference pipeline.
  - default_month is sampled from [DEFAULT_MONTH_MIN, DEFAULT_MONTH_MAX]
    (currently 10–34), ensuring the 12-month label is positive in the
    test window (months 21-23) for the subset of defaulters whose
    default_month falls in [22, 35].
"""

import numpy as np
import pandas as pd
from pathlib import Path
import json
import warnings
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

warnings.filterwarnings("ignore")
np.random.seed(42)

# ─── Constants ───────────────────────────────────────────────────────────────

N_BORROWERS = 5000
N_MONTHS = 24           # 24-month observation window per borrower
DEFAULT_RATE = 0.15     # ~15% base default rate (realistic Indian MSME NPA)
PREDICTION_HORIZON = 12 # predict default within next 12 months

# default_month for defaulters is sampled uniformly from this range.
# Allowing defaults beyond month 23 ensures label_default_12m=1 exists in
# the test window (months 21-23): a borrower with default_month in [22, 35]
# has label=1 at month 21 because 0 < (default_month - 21) <= 12.
DEFAULT_MONTH_MIN = 10   # earliest possible default month
DEFAULT_MONTH_MAX = 34   # latest possible default month

# Pre-default stress window: how many months before default elevated stress begins
PRE_DEFAULT_WINDOW = 8

LOAN_TYPES = ["Working Capital", "Term Loan", "Trade Finance"]
LOAN_TYPE_WEIGHTS = [0.45, 0.35, 0.20]

INDUSTRIES = [
    "Manufacturing", "Trading", "Services", "Construction",
    "Food Processing", "Textiles", "Auto Ancillary", "Pharma",
    "IT/ITES", "Agriculture Allied",
]

REGIONS = ["North", "South", "East", "West", "Central"]

NIC_CODES = {
    "Manufacturing": "C10-C33",
    "Trading": "G45-G47",
    "Services": "S90-S99",
    "Construction": "F41-F43",
    "Food Processing": "C10",
    "Textiles": "C13",
    "Auto Ancillary": "C29",
    "Pharma": "C21",
    "IT/ITES": "J62",
    "Agriculture Allied": "A01",
}

RISK_GRADE_BANDS = [
    (0, 10, "AAA"),
    (10, 20, "AA"),
    (20, 30, "A"),
    (30, 45, "BBB"),
    (45, 60, "BB"),
    (60, 75, "B"),
    (75, 90, "C"),
    (90, 100, "D"),
]


# ─── Helper Functions ─────────────────────────────────────────────────────────

def stress_score_to_grade(score: float) -> str:
    for low, high, grade in RISK_GRADE_BANDS:
        if low <= score < high:
            return grade
    return "D"


def generate_random_gstin() -> str:
    state = np.random.randint(1, 36)
    pan = "".join(np.random.choice(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), 5))
    num = "".join(np.random.choice(list("0123456789"), 4))
    alpha = np.random.choice(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    return f"{state:02d}{pan}{num}{alpha}1Z5"


def generate_random_pan() -> str:
    alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return (
        "".join(np.random.choice(list(alpha), 3))
        + "P"
        + np.random.choice(list(alpha))
        + "".join(np.random.choice(list("0123456789"), 4))
        + np.random.choice(list(alpha))
    )


# ─── Phase 1: Borrower Profiles ──────────────────────────────────────────────

def generate_borrower_profiles(n: int = N_BORROWERS) -> pd.DataFrame:
    print(f"[1/4] Generating {n} borrower profiles...")

    industries = np.random.choice(INDUSTRIES, size=n)
    loan_types = np.random.choice(LOAN_TYPES, size=n, p=LOAN_TYPE_WEIGHTS)

    # Loan amount distribution (INR Lakhs) — varies by loan type
    loan_amounts = []
    for lt in loan_types:
        if lt == "Working Capital":
            amt = np.random.lognormal(mean=4.5, sigma=0.8)   # ~90L median
        elif lt == "Term Loan":
            amt = np.random.lognormal(mean=5.2, sigma=0.9)   # ~180L median
        else:  # Trade Finance
            amt = np.random.lognormal(mean=4.8, sigma=0.7)   # ~120L median
        loan_amounts.append(max(10, min(amt, 2000)))

    vintage = np.random.exponential(scale=5, size=n)
    vintage = np.clip(vintage, 0.5, 30).round(1)

    base_date = datetime(2022, 1, 1)
    sanction_offsets = np.random.randint(0, 730, size=n)
    sanction_dates = [base_date + timedelta(days=int(d)) for d in sanction_offsets]

    profiles = pd.DataFrame({
        "borrower_id":            [f"MSME{i+1:05d}" for i in range(n)],
        "business_name":          [f"Business_{i+1:05d} Pvt Ltd" for i in range(n)],
        "industry":               industries,
        "nic_code":               [NIC_CODES[ind] for ind in industries],
        "loan_type":              loan_types,
        "loan_amount_lakhs":      np.round(loan_amounts, 2),
        "vintage_years":          vintage,
        "region":                 np.random.choice(REGIONS, size=n),
        "sanction_date":          [d.strftime("%Y-%m-%d") for d in sanction_dates],
        "gstin":                  [generate_random_gstin() for _ in range(n)],
        "pan":                    [generate_random_pan() for _ in range(n)],
        "employee_count_initial": np.random.randint(5, 250, size=n),
    })

    return profiles


# ─── Phase 2: Default Label Assignment ───────────────────────────────────────

def assign_default_labels(profiles: pd.DataFrame) -> pd.DataFrame:
    """
    CRITICAL: assigns is_defaulter, true_pd, and default_month INDEPENDENTLY
    before any financial trajectory is simulated.  No feature is touched here.

    default_month: uniform in [DEFAULT_MONTH_MIN, DEFAULT_MONTH_MAX].
    Distributing defaults beyond month 23 is the mechanism that produces
    positive labels (label_default_12m=1) in the test window (months 21-23).

    Industry / loan-type / vintage risk adjustments modulate the raw default
    probability but are segment-level priors, not per-borrower financial signals.
    """
    print("[2/4] Assigning default labels (independent of financial features)...")

    n = len(profiles)
    base_pd = np.full(n, DEFAULT_RATE, dtype=float)

    # Industry risk adjustment
    industry_risk = {
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
    for ind, adj in industry_risk.items():
        base_pd[profiles["industry"] == ind] += adj

    # Loan type risk adjustment
    loan_risk = {"Working Capital": 0.02, "Term Loan": 0.0, "Trade Finance": -0.01}
    for lt, adj in loan_risk.items():
        base_pd[profiles["loan_type"] == lt] += adj

    # Vintage adjustment — newer businesses riskier
    vintage_adj = np.where(profiles["vintage_years"] < 2, 0.08,
                  np.where(profiles["vintage_years"] < 5, 0.03, 0.0))
    base_pd += vintage_adj
    base_pd = np.clip(base_pd, 0.01, 0.60)

    defaults = np.random.binomial(1, base_pd)

    # Assign default_month: uniform over [DEFAULT_MONTH_MIN, DEFAULT_MONTH_MAX].
    # Non-defaulters receive -1 (sentinel; never referenced in label computation).
    default_months = np.where(
        defaults == 1,
        np.random.randint(DEFAULT_MONTH_MIN, DEFAULT_MONTH_MAX + 1, size=n),
        -1,
    ).astype(int)

    profiles = profiles.copy()
    profiles["is_defaulter"]  = defaults
    profiles["true_pd"]       = np.round(base_pd, 4)
    profiles["default_month"] = default_months  # audit metadata ONLY, never a model input

    actual_rate = defaults.mean()
    print(f"   -> Default rate: {actual_rate:.1%} (target ~{DEFAULT_RATE:.0%})")

    # Preview expected positive counts in each time window
    def _count_positives(lo: int, hi: int) -> int:
        count = 0
        for dm in default_months[defaults == 1]:
            for m in range(lo, hi + 1):
                if 0 < dm - m <= PREDICTION_HORIZON:
                    count += 1
        return count

    print(f"   -> Expected label=1 rows | train(0-17) : {_count_positives(0,17):,}")
    print(f"   -> Expected label=1 rows | val(18-20)  : {_count_positives(18,20):,}")
    print(f"   -> Expected label=1 rows | test(21-23) : {_count_positives(21,23):,}")

    return profiles


# ─── Phase 3: Monthly Snapshots (Probabilistic Stress Model) ─────────────────

def generate_monthly_snapshots(profiles: pd.DataFrame) -> pd.DataFrame:
    """
    Generates 24-month financial snapshots per borrower using a PROBABILISTIC
    stress model.  Key design invariants:

      1. Financial signals are simulated AFTER labels — no target leakage.
      2. Each month, a single `stressed` boolean is drawn from a Bernoulli
         with P(stress) that depends only on (is_defaulter, distance-to-default).
         Outside the pre-default window — and for all non-defaulters — P(stress)
         is the background rate (~8%), giving genuine false-positive stress signals.
      3. Each feature independently receives additive Gaussian noise around the
         stressed / healthy mean, so individual signals are imperfectly correlated.
      4. `_is_defaulter` and `_stress_onset_month` are NOT written to this output.
         Those columns are retained only in borrower_profiles.csv as metadata.
    """
    print(f"[3/4] Generating {N_MONTHS}-month snapshots (probabilistic stress model)...")

    all_records = []
    base_date = datetime(2023, 1, 1)

    for _, row in profiles.iterrows():
        bid          = row["borrower_id"]
        is_def       = bool(row["is_defaulter"] == 1)
        default_month = int(row["default_month"]) if is_def else 9999
        loan_type    = row["loan_type"]
        industry     = row["industry"]

        # Pre-default stress window start: 8 months before default_month
        stress_start = max(0, default_month - PRE_DEFAULT_WINDOW) if is_def else 9999

        # ── Starting financial state (independent of default status) ──────────
        dscr_curr         = np.random.uniform(0.9, 2.2)
        bureau_curr       = float(np.random.randint(580, 800))
        gst_turnover_curr = row["loan_amount_lakhs"] * np.random.uniform(1.5, 4.0)
        bank_bal_curr     = row["loan_amount_lakhs"] * np.random.uniform(0.10, 0.40)
        od_util_curr      = np.random.uniform(0.20, 0.65)
        epfo_curr         = int(row["employee_count_initial"])

        for month_idx in range(N_MONTHS):
            as_of_date = base_date + relativedelta(months=month_idx)

            # ── Compute this month's stress probability ────────────────────────
            # in_window: defaulter is within PRE_DEFAULT_WINDOW months of default
            in_window = is_def and (stress_start <= month_idx < default_month)

            # depth: 0.0 at window start → 1.0 just before default
            if in_window and default_month > stress_start:
                depth = (month_idx - stress_start) / max(1, default_month - stress_start)
            else:
                depth = 0.0

            # P(stress) ramps from 35% → 85% inside the window.
            # Outside (and for all non-defaulters) it is 8% — genuine noise.
            p_stress = (0.35 + 0.50 * depth) if in_window else 0.08

            # Single draw: whether this month has an elevated-stress regime
            stressed = bool(np.random.random() < p_stress)

            # ── DSCR ──────────────────────────────────────────────────────────
            # Target: stressed → sub-1 territory; healthy → above 1
            dscr_target = (np.random.normal(0.78, 0.20) if stressed
                           else np.random.normal(1.55, 0.28))
            # Exponential smoothing so trajectory is autocorrelated (not i.i.d.)
            dscr_curr = 0.60 * dscr_curr + 0.40 * dscr_target + np.random.normal(0, 0.04)
            dscr_curr = max(0.10, dscr_curr)

            # ── Bureau score ──────────────────────────────────────────────────
            bureau_target = (float(np.random.randint(480, 640)) if stressed
                             else float(np.random.randint(660, 820)))
            bureau_curr = 0.75 * bureau_curr + 0.25 * bureau_target + np.random.uniform(-8, 8)
            bureau_curr = max(300.0, min(900.0, bureau_curr))
            bureau_score = int(round(bureau_curr))

            # Bureau enquiries: credit-seeking behaviour under stress
            bureau_enquiries = int(np.random.poisson(2.5 if stressed else 0.6))

            # ── GST turnover ──────────────────────────────────────────────────
            seasonal = 1.0 + 0.10 * np.sin(2 * np.pi * month_idx / 12)
            gst_growth = (np.random.uniform(0.88, 0.98) if stressed
                          else np.random.uniform(0.98, 1.04))
            gst_turnover_curr = max(1.0,
                gst_turnover_curr * gst_growth * seasonal
                + np.random.normal(0, gst_turnover_curr * 0.03)
            )

            # ── GST filing compliance ─────────────────────────────────────────
            if stressed:
                gst_delay = int(np.random.choice(
                    [0, 15, 30, 45, 60, 90],
                    p=[0.10, 0.20, 0.30, 0.22, 0.12, 0.06],
                ))
                gst_missed = int(np.random.binomial(1, 0.20))
            else:
                gst_delay = int(np.random.choice(
                    [0, 5, 10, 15, 30],
                    p=[0.55, 0.20, 0.12, 0.08, 0.05],
                ))
                gst_missed = int(np.random.binomial(1, 0.02))

            # ── Bank balance & volatility ─────────────────────────────────────
            bal_growth = np.random.uniform(0.87, 0.97) if stressed else np.random.uniform(0.97, 1.03)
            bank_bal_curr = max(0.5,
                bank_bal_curr * bal_growth + np.random.normal(0, bank_bal_curr * 0.04)
            )
            bank_bal_vol = (np.random.uniform(0.14, 0.35) if stressed
                            else np.random.uniform(0.03, 0.14))
            bank_bal_vol = float(np.clip(bank_bal_vol + np.random.uniform(-0.02, 0.02), 0.01, 0.50))

            # ── Overdraft utilization ─────────────────────────────────────────
            od_target = np.random.uniform(0.65, 0.98) if stressed else np.random.uniform(0.15, 0.60)
            od_util_curr = 0.70 * od_util_curr + 0.30 * od_target + np.random.uniform(-0.03, 0.03)
            od_util_curr = float(np.clip(od_util_curr, 0.0, 1.0))

            # ── EPFO employee count ───────────────────────────────────────────
            if stressed:
                epfo_delta = int(np.random.choice([-3, -2, -1,  0,  1],
                                                   p=[0.20, 0.30, 0.30, 0.15, 0.05]))
            else:
                epfo_delta = int(np.random.choice([-1,  0,  1,  2,  3],
                                                   p=[0.05, 0.30, 0.35, 0.20, 0.10]))
            epfo_curr = max(1, epfo_curr + epfo_delta)

            # ── DPD ───────────────────────────────────────────────────────────
            if stressed and depth > 0.5:      # deep in the pre-default window
                dpd_current = int(np.random.choice(
                    [0, 30, 60, 90, 180], p=[0.15, 0.28, 0.30, 0.20, 0.07]
                ))
            elif stressed:                    # early pre-default window
                dpd_current = int(np.random.choice(
                    [0, 30, 60], p=[0.50, 0.35, 0.15]
                ))
            else:                             # no stress
                dpd_current = int(np.random.choice(
                    [0, 30], p=[0.95, 0.05]
                ))
            dpd_max_12m = max(dpd_current, int(np.random.choice(
                [0, 30, 60, 90], p=[0.80, 0.12, 0.05, 0.03]
            )))

            # ── Unstructured / NLP signals ────────────────────────────────────
            gst_sentiment = float(np.clip(
                np.random.normal(-0.30 if stressed else 0.35, 0.22),
                -1.0, 1.0,
            ))
            txn_anomaly = float(np.clip(
                (np.random.beta(2, 3) + 0.20) if stressed else np.random.beta(1, 6),
                0.0, 1.0,
            ))
            # Litigation: probabilistic even inside the window (not certain)
            if stressed and depth > 0.40:
                lit_flag = int(np.random.binomial(1, 0.20))
                lit_sev  = int(np.random.choice([0, 1, 2], p=[0.50, 0.30, 0.20]))
            else:
                lit_flag = int(np.random.binomial(1, 0.02))
                lit_sev  = 0
            news_sentiment = float(np.clip(
                np.random.normal(-0.25 if stressed else 0.10, 0.16),
                -1.0, 1.0,
            ))

            # ── Label: will this borrower default in the next 12 months? ──────
            # Strictly future-only: 0 < (default_month - month_idx) <= 12
            label_12m = int(
                is_def and 0 < default_month - month_idx <= PREDICTION_HORIZON
            )

            # NOTE: _is_defaulter and _stress_onset_month are intentionally
            # OMITTED here.  They exist only in borrower_profiles.csv (metadata).
            all_records.append({
                "borrower_id":                 bid,
                "as_of_month":                 as_of_date.strftime("%Y-%m"),
                "month_index":                 month_idx,
                "loan_type":                   loan_type,
                "industry":                    industry,
                "dscr":                        round(float(dscr_curr), 4),
                "bureau_score":                bureau_score,
                "bureau_enquiries_6m":         bureau_enquiries,
                "gst_turnover_lakhs":          round(float(gst_turnover_curr), 2),
                "gst_filing_delay_days":       gst_delay,
                "gst_filing_missed":           gst_missed,
                "bank_avg_balance_lakhs":      round(float(bank_bal_curr), 2),
                "bank_balance_volatility":     round(float(bank_bal_vol), 4),
                "overdraft_utilization_pct":   round(od_util_curr, 4),
                "epfo_employee_count":         epfo_curr,
                "dpd_current":                 dpd_current,
                "dpd_max_12m":                 dpd_max_12m,
                "gst_remark_sentiment_score":  round(gst_sentiment, 4),
                "transaction_anomaly_score":   round(txn_anomaly, 4),
                "litigation_flag":             lit_flag,
                "litigation_severity":         lit_sev,
                "news_sentiment_score":        round(news_sentiment, 4),
                "label_default_12m":           label_12m,
            })

    df = pd.DataFrame(all_records)
    print(f"   -> {len(df):,} snapshot rows generated.")
    return df


# ─── Phase 4: Save & Validate ─────────────────────────────────────────────────

def validate_and_save(profiles: pd.DataFrame, snapshots: pd.DataFrame, out_dir: Path):
    print("[4/4] Validating and saving datasets...")

    out_dir.mkdir(parents=True, exist_ok=True)

    # Merge profile columns needed by feature engineering.
    # is_defaulter, true_pd, default_month stay in borrower_profiles.csv ONLY
    # — they must not flow into the ML pipeline.
    full = snapshots.merge(
        profiles[[
            "borrower_id", "loan_amount_lakhs", "vintage_years",
            "region", "gstin", "pan", "employee_count_initial",
        ]],
        on="borrower_id", how="left",
    )

    profiles.to_csv(out_dir / "borrower_profiles.csv",  index=False)
    snapshots.to_csv(out_dir / "monthly_snapshots.csv", index=False)
    full.to_csv(out_dir / "full_dataset.csv",           index=False)

    # Label statistics per split window
    def _window_stats(lo: int, hi: int):
        w = full[full["month_index"].between(lo, hi)]
        pos = int(w["label_default_12m"].sum())
        n   = int(len(w))
        return pos, n, pos / n if n else 0.0

    tr_pos, tr_n, tr_rate = _window_stats(0,  17)
    va_pos, va_n, va_rate = _window_stats(18, 20)
    te_pos, te_n, te_rate = _window_stats(21, 23)

    stats = {
        "total_borrowers":        int(len(profiles)),
        "total_rows":             int(len(full)),
        "months_per_borrower":    N_MONTHS,
        "default_rate":           float(profiles["is_defaulter"].mean()),
        "label_positive_rate":    float(full["label_default_12m"].mean()),
        "train_positives":        tr_pos,
        "val_positives":          va_pos,
        "test_positives":         te_pos,
        "train_positive_rate":    round(tr_rate, 4),
        "val_positive_rate":      round(va_rate, 4),
        "test_positive_rate":     round(te_rate, 4),
        "loan_type_distribution": profiles["loan_type"].value_counts().to_dict(),
        "industry_distribution":  profiles["industry"].value_counts().to_dict(),
        "feature_columns":        [c for c in full.columns if not c.startswith("_")],
        "generated_at":           datetime.now().isoformat(),
    }

    with open(out_dir / "dataset_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    print("\n-- Dataset Summary -----------------------------------------")
    print(f"  Borrowers            : {stats['total_borrowers']:,}")
    print(f"  Total rows           : {stats['total_rows']:,}")
    print(f"  Borrower default rate: {stats['default_rate']:.1%}")
    print(f"  Train(0-17)  positives: {tr_pos:,} / {tr_n:,}  ({tr_rate:.1%})")
    print(f"  Val(18-20)   positives: {va_pos:,} / {va_n:,}  ({va_rate:.1%})")
    print(f"  Test(21-23)  positives: {te_pos:,} / {te_n:,}  ({te_rate:.1%})")
    print("------------------------------------------------------------\n")

    # Sanity assertions
    assert stats["total_borrowers"] == N_BORROWERS, "Borrower count mismatch"
    assert stats["total_rows"] == N_BORROWERS * N_MONTHS, "Row count mismatch"
    assert 0.08 < stats["default_rate"] < 0.25, \
        f"Default rate out of range: {stats['default_rate']}"
    assert full.isnull().sum().sum() == 0, "Nulls found in dataset!"

    # Critical: test set must have positive labels in every segment
    for lt in LOAN_TYPES:
        seg = full[(full["month_index"] >= 21) & (full["loan_type"] == lt)]
        n_pos = int(seg["label_default_12m"].sum())
        assert n_pos >= 10, (
            f"Test set has only {n_pos} positives for {lt}. "
            f"Increase DEFAULT_MONTH_MAX (currently {DEFAULT_MONTH_MAX})."
        )
        print(f"  CHECK Test positives [{lt}]: {n_pos}")

    print("  OK  All validation checks passed.")
    return full


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Sentinel -- MSME Synthetic Data Generator  (v2 Leakage-Free)")
    print("=" * 60)

    try:
        from dateutil.relativedelta import relativedelta  # noqa: F811
    except ImportError:
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dateutil"])
        from dateutil.relativedelta import relativedelta  # noqa: F811

    out_dir = Path(__file__).parent / "generated"

    profiles   = generate_borrower_profiles(N_BORROWERS)
    profiles   = assign_default_labels(profiles)
    snapshots  = generate_monthly_snapshots(profiles)
    full_df    = validate_and_save(profiles, snapshots, out_dir)

    print("\nDONE  Data generation complete!")
    print(f"   Output: {out_dir.resolve()}")
