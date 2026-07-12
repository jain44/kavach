import os
import sys
import time
import argparse
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from ml.feature_engineering import engineer_features_legacy, engineer_features_fast, FEATURE_COLS

def load_data_from_db(n_borrowers=None):
    db_path = BASE_DIR / "kavach.db"
    if not db_path.exists():
        # Try local path
        db_path = Path("kavach.db")
        if not db_path.exists():
            raise FileNotFoundError(f"Database not found at {db_path}")

    print(f"Connecting to database at {db_path}...")
    conn = sqlite3.connect(str(db_path))

    # Query list of borrowers
    borrower_query = "SELECT borrower_id FROM borrower_profiles"
    if n_borrowers:
        borrower_query += f" LIMIT {n_borrowers}"
    
    borrowers_df = pd.read_sql_query(borrower_query, conn)
    borrower_ids = tuple(borrowers_df["borrower_id"].tolist())

    if not borrower_ids:
        raise ValueError("No borrowers found in database.")

    print(f"Loading data for {len(borrower_ids)} borrowers...")
    
    # Query monthly snapshots
    if len(borrower_ids) == 1:
        snapshot_query = f"SELECT * FROM monthly_snapshots WHERE borrower_id = '{borrower_ids[0]}'"
    else:
        snapshot_query = f"SELECT * FROM monthly_snapshots WHERE borrower_id IN {borrower_ids}"
    snapshots_df = pd.read_sql_query(snapshot_query, conn)

    # Query profiles to get loan_amount_lakhs and vintage_years
    if len(borrower_ids) == 1:
        profile_query = f"SELECT borrower_id, loan_amount_lakhs, vintage_years FROM borrower_profiles WHERE borrower_id = '{borrower_ids[0]}'"
    else:
        profile_query = f"SELECT borrower_id, loan_amount_lakhs, vintage_years FROM borrower_profiles WHERE borrower_id IN {borrower_ids}"
    profiles_df = pd.read_sql_query(profile_query, conn)

    conn.close()

    # Join snapshots and profiles
    merged_df = pd.merge(snapshots_df, profiles_df, on="borrower_id", suffixes=('', '_profile'))

    # Add required extra columns that the feature engineering function needs
    merged_df["_stress_onset_month"] = 100
    merged_df["_is_defaulter"] = 0

    return merged_df

def main():
    parser = argparse.ArgumentParser(description="Parity test between legacy and fast feature engineering")
    parser.add_argument("--n_borrowers", type=int, default=200, help="Number of borrowers to sample (default 200)")
    parser.add_argument("--full", action="store_true", help="Run on all 5000 borrowers")
    args = parser.parse_args()

    n = None if args.full else args.n_borrowers
    try:
        raw_df = load_data_from_db(n)
    except Exception as e:
        print(f"Database error: {e}. Falling back to CSV...")
        # Fallback to loading from full_dataset.csv
        csv_path = BASE_DIR / "data" / "generated" / "full_dataset.csv"
        if not csv_path.exists():
            print(f"Error: full_dataset.csv not found at {csv_path}")
            sys.exit(1)
        raw_df = pd.read_csv(csv_path)
        if n:
            borrower_ids = raw_df["borrower_id"].unique()[:n]
            raw_df = raw_df[raw_df["borrower_id"].isin(borrower_ids)].copy()

    print(f"Input data shape: {raw_df.shape}")

    # Run legacy version
    print("\nRunning legacy (slow loop) feature engineering...")
    start_legacy = time.time()
    legacy_features = engineer_features_legacy(raw_df)
    legacy_time = time.time() - start_legacy
    print(f"Legacy completed in {legacy_time:.2f} seconds. Shape: {legacy_features.shape}")

    # Run fast version
    print("\nRunning fast (vectorized) feature engineering...")
    start_fast = time.time()
    fast_features = engineer_features_fast(raw_df)
    fast_time = time.time() - start_fast
    print(f"Fast completed in {fast_time:.2f} seconds. Shape: {fast_features.shape}")

    print(f"\nSpeedup: {legacy_time / max(fast_time, 1e-6):.1f}x")

    # Align column ordering and rows
    legacy_features = legacy_features.sort_values(["borrower_id", "month_index"]).reset_index(drop=True)
    fast_features = fast_features.sort_values(["borrower_id", "month_index"]).reset_index(drop=True)

    # Check columns
    legacy_cols = set(legacy_features.columns)
    fast_cols = set(fast_features.columns)
    if legacy_cols != fast_cols:
        print(f"Column mismatch! Symmetric difference: {legacy_cols ^ fast_cols}")
        sys.exit(1)

    print("\nComparing columns one by one...")
    mismatches = {}
    
    # We compare all 63 feature columns + labels/metadata
    all_compare_cols = list(legacy_features.columns)

    for col in all_compare_cols:
        l_vals = legacy_features[col]
        f_vals = fast_features[col]

        # Check types
        if pd.api.types.is_numeric_dtype(l_vals) and pd.api.types.is_numeric_dtype(f_vals):
            # For numeric columns, compare using allclose with tolerance
            # NaN is considered equal to NaN
            l_arr = l_vals.to_numpy().astype(float)
            f_arr = f_vals.to_numpy().astype(float)
            close = np.allclose(l_arr, f_arr, atol=1e-6, equal_nan=True)
            if not close:
                # Find where they mismatch
                mask = ~np.isclose(l_arr, f_arr, atol=1e-6, equal_nan=True)
                mismatches[col] = mask
        else:
            # For non-numeric or categorical, compare exactly
            # Handle NaNs/None for strings
            l_arr = l_vals.fillna("NaN_val").to_numpy()
            f_arr = f_vals.fillna("NaN_val").to_numpy()
            exact = np.array_equal(l_arr, f_arr)
            if not exact:
                mask = l_arr != f_arr
                mismatches[col] = mask

    # Save benchmark results
    benchmark_data = {
        "legacy_time_seconds": round(legacy_time, 4),
        "fast_time_seconds": round(fast_time, 4),
        "speedup_ratio": round(legacy_time / max(fast_time, 1e-6), 2),
        "num_borrowers": int(raw_df["borrower_id"].nunique()),
        "total_rows": int(len(raw_df)),
        "parity_verified": len(mismatches) == 0,
        "timestamp": pd.Timestamp.now().isoformat()
    }
    benchmark_path = BASE_DIR / "models" / "comparison_benchmark.json"
    import json
    try:
        with open(benchmark_path, "w") as f:
            json.dump(benchmark_data, f, indent=2)
        print(f"Saved benchmark results to {benchmark_path}")
    except Exception as e:
        print(f"Warning: could not save benchmark file: {e}")

    if not mismatches:
        print("=" * 60)
        print("ALL 63 COLUMNS MATCH EXACTLY! — safe to use engineer_features_fast in production")
        print("=" * 60)
        sys.exit(0)
    else:
        print("=" * 60)
        print(f"FAIL: {len(mismatches)} columns had differences!")
        print("=" * 60)
        for col, mask in mismatches.items():
            num_diff = mask.sum()
            print(f"\nColumn '{col}' has {num_diff} differences (out of {len(mask)} rows).")
            # Show first 5 differences
            diff_indices = np.where(mask)[0][:5]
            for idx in diff_indices:
                borrower = legacy_features.loc[idx, "borrower_id"]
                month = legacy_features.loc[idx, "month_index"]
                l_val = legacy_features.loc[idx, col]
                f_val = fast_features.loc[idx, col]
                print(f"  Borrower: {borrower}, Month: {month} | Legacy: {l_val} | Fast: {f_val}")
        sys.exit(1)

if __name__ == "__main__":
    main()
