import os
import sys
import pandas as pd
import numpy as np
import joblib

# Add parent directory to path
sys.path.insert(0, os.path.abspath("."))

from ml.train_model import FEATURE_COLS
from api.main import load_data

async def run_spot_check():
    # Load all models and data using the startup logic
    await load_data()
    
    from api.main import _models, _snapshots_df, run_dynamic_inference
    
    # Pick 3 borrowers
    borrower_ids = ["MSME00001", "MSME00042", "MSME00100"]
    
    print("=== NaN Spot Check ===")
    for bid in borrower_ids:
        # Get raw snapshots
        history = _snapshots_df[_snapshots_df["borrower_id"] == bid].copy()
        last_idx = history.index[-1]
        
        # Introduce NaN values into some features in the last month
        history.loc[last_idx, "dscr"] = np.nan
        history.loc[last_idx, "bureau_score"] = np.nan
        history.loc[last_idx, "overdraft_utilization_pct"] = np.nan
        
        # Define snapshot modification function for live prediction
        def modify_fn(df):
            df = df.copy()
            idx = df.index[-1]
            df.loc[idx, "dscr"] = np.nan
            df.loc[idx, "bureau_score"] = np.nan
            df.loc[idx, "overdraft_utilization_pct"] = np.nan
            return df
            
        # Run live inference
        pd_prob_live, stress_live, grade_live, _, last_row_live = run_dynamic_inference(bid, modify_fn)
        
        # Run batch scoring simulation on the engineered last row
        profile = history.iloc[0]
        loan_type = profile["loan_type"]
        model = _models[loan_type]
        
        X_batch = last_row_live[FEATURE_COLS]
        pd_prob_batch = float(model.predict_proba(X_batch)[:, 1][0])
        
        print(f"Borrower: {bid} ({loan_type})")
        print(f"  Live prediction PD:  {pd_prob_live:.6f}")
        print(f"  Batch prediction PD: {pd_prob_batch:.6f}")
        print(f"  Match: {np.isclose(pd_prob_live, pd_prob_batch)}")
        assert np.isclose(pd_prob_live, pd_prob_batch), f"PD mismatch for {bid}!"

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_spot_check())
