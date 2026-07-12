"""
Kavach -- Adversarial & Edge-Case Stress Testing
Runs stress testing against the live inference API for various edge cases:
a) Extreme bad
b) Extreme healthy
c) Sparse history (NTC)
d) Conflicting signals
e) NaN / missing fields
"""

import sys
import os
import json
import numpy as np
from pathlib import Path
from datetime import datetime

# Explicitly force local SQLite database for stress testing
os.environ["DATABASE_URL"] = "sqlite:///./kavach.db"

# Add parent directory to system path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from api.main import app
from db.database import SessionLocal
from db.models import BorrowerProfile, MonthlySnapshot, ModelVersion, User
from db.crypto import encrypt_val

def get_auth_token(client, username):
    role = "risk_officer" if username == "risk_officer" else username
    res = client.post("/api/v1/auth/login", json={
        "username": username,
        "password": "kavach123",
        "role": role
    })
    if res.status_code == 200:
        return res.json()["access_token"]
    return ""

def main():
    print("=" * 60)
    print("  Kavach -- Live API Stress Testing")
    print("=" * 60)

    db = SessionLocal()
    # Seed a specific test profile for NTC check
    try:
        # Check if TESTNTC002 exists, if not seed it
        ntc = db.query(BorrowerProfile).filter_by(borrower_id="TESTNTC002").first()
        if not ntc:
            db.add(BorrowerProfile(
                borrower_id="TESTNTC002",
                business_name="NTC Live Stress Test Corp",
                gstin=encrypt_val("27CCCCC3333C3Z7"),
                pan=encrypt_val("XYZW9876C"),
                loan_type="Working Capital",
                industry="Retail",
                region="East",
                loan_amount_lakhs=15.0,
                vintage_years=1.2,
                employee_count_initial=3
            ))
            # Seed exactly 1 monthly snapshot (making history length = 1 < 3)
            db.add(MonthlySnapshot(
                borrower_id="TESTNTC002", as_of_month="2025-01", month_index=0,
                loan_type="Working Capital", industry="Retail", dscr=1.2,
                bureau_score=700, bureau_enquiries_6m=1, gst_turnover_lakhs=3.0,
                gst_filing_delay_days=0, gst_filing_missed=0, bank_avg_balance_lakhs=1.0,
                bank_balance_volatility=0.1, overdraft_utilization_pct=0.5,
                epfo_employee_count=4, dpd_current=0, dpd_max_12m=0,
                gst_remark_sentiment_score=0.6, transaction_anomaly_score=0.1,
                litigation_flag=0, litigation_severity=0, news_sentiment_score=0.5,
                label_default_12m=0, is_defaulter=0
            ))
            db.commit()
            print("Seeded NTC test profile (TESTNTC002) successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding NTC profile: {e}")
    finally:
        db.close()

    client_ctx = TestClient(app)
    with client_ctx as client:
        token = get_auth_token(client, "risk_officer")
        headers = {"Authorization": f"Bearer {token}"}

        # Case a) Extreme Bad
        print("\nCase a) Extreme Bad Bounds...")
        payload_bad = {
            "borrower_id": "MSME00001",
            "current_snapshot": {
                "dscr": 0.01,
                "bureau_score": 300,
                "bureau_enquiries_6m": 25,
                "gst_turnover_lakhs": 0.0,
                "gst_filing_delay_days": 180,
                "gst_filing_missed": 12,
                "bank_avg_balance_lakhs": 0.0,
                "bank_balance_volatility": 4.5,
                "overdraft_utilization_pct": 1.0,
                "epfo_employee_count": 0,
                "dpd_current": 90,
                "dpd_max_12m": 180,
                "gst_remark_sentiment_score": -1.0,
                "transaction_anomaly_score": 1.0,
                "litigation_flag": 1,
                "litigation_severity": 2,
                "news_sentiment_score": -1.0
            }
        }
        res = client.post("/api/v1/predict/live", json=payload_bad, headers=headers)
        print(f"  Status Code: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            print(f"  PD Probability: {data['pd_probability']:.4f}")
            print(f"  Stress Score  : {data['stress_score']:.2f}")
            print(f"  Risk Grade    : {data['risk_grade']}")
            print(f"  Top SHAP reason codes: {data['top_reason_codes'][:3]}")
        else:
            print(f"  Error Response: {res.text}")

        # Case b) Extreme Healthy
        print("\nCase b) Extreme Healthy Bounds...")
        payload_healthy = {
            "borrower_id": "MSME00001",
            "current_snapshot": {
                "dscr": 15.0,
                "bureau_score": 900,
                "bureau_enquiries_6m": 0,
                "gst_turnover_lakhs": 500.0,
                "gst_filing_delay_days": 0,
                "gst_filing_missed": 0,
                "bank_avg_balance_lakhs": 150.0,
                "bank_balance_volatility": 0.01,
                "overdraft_utilization_pct": 0.0,
                "epfo_employee_count": 250,
                "dpd_current": 0,
                "dpd_max_12m": 0,
                "gst_remark_sentiment_score": 1.0,
                "transaction_anomaly_score": 0.0,
                "litigation_flag": 0,
                "litigation_severity": 0,
                "news_sentiment_score": 1.0
            }
        }
        res = client.post("/api/v1/predict/live", json=payload_healthy, headers=headers)
        print(f"  Status Code: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            print(f"  PD Probability: {data['pd_probability']:.4f}")
            print(f"  Stress Score  : {data['stress_score']:.2f}")
            print(f"  Risk Grade    : {data['risk_grade']}")
            print(f"  Top SHAP reason codes: {data['top_reason_codes'][:3]}")
        else:
            print(f"  Error Response: {res.text}")

        # Case c) Sparse History (NTC check)
        print("\nCase c) Sparse History (TESTNTC002)...")
        payload_ntc = {
            "borrower_id": "TESTNTC002",
            "current_snapshot": {
                "dscr": 1.2,
                "bureau_score": 700,
                "bureau_enquiries_6m": 1,
                "gst_turnover_lakhs": 3.0,
                "gst_filing_delay_days": 0,
                "gst_filing_missed": 0,
                "bank_avg_balance_lakhs": 1.0,
                "bank_balance_volatility": 0.1,
                "overdraft_utilization_pct": 0.5,
                "epfo_employee_count": 4,
                "dpd_current": 0,
                "dpd_max_12m": 0,
                "gst_remark_sentiment_score": 0.6,
                "transaction_anomaly_score": 0.1,
                "litigation_flag": 0,
                "litigation_severity": 0,
                "news_sentiment_score": 0.5
            }
        }
        res = client.post("/api/v1/predict/live", json=payload_ntc, headers=headers)
        print(f"  Status Code: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            print(f"  PD Probability: {data['pd_probability']:.4f}")
            print(f"  Stress Score  : {data['stress_score']:.2f}")
            print(f"  Risk Grade    : {data['risk_grade']}")
            print(f"  Confidence Lvl: {data['confidence_level']}")
        else:
            print(f"  Error Response: {res.text}")

        # Case d) Conflicting Signals
        print("\nCase d) Conflicting Signals...")
        payload_conflict = {
            "borrower_id": "MSME00001",
            "current_snapshot": {
                "dscr": 1.8, # excellent
                "bureau_score": 850, # excellent
                "bureau_enquiries_6m": 0,
                "gst_turnover_lakhs": 15.0,
                "gst_filing_delay_days": 90, # red flag
                "gst_filing_missed": 0,
                "bank_avg_balance_lakhs": 5.0,
                "bank_balance_volatility": 0.05,
                "overdraft_utilization_pct": 0.2,
                "epfo_employee_count": 15,
                "dpd_current": 0,
                "dpd_max_12m": 0,
                "gst_remark_sentiment_score": 0.7,
                "transaction_anomaly_score": 0.05,
                "litigation_flag": 1, # red flag
                "litigation_severity": 2, # red flag
                "news_sentiment_score": 0.5
            }
        }
        res = client.post("/api/v1/predict/live", json=payload_conflict, headers=headers)
        print(f"  Status Code: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            print(f"  PD Probability: {data['pd_probability']:.4f}")
            print(f"  Stress Score  : {data['stress_score']:.2f}")
            print(f"  Risk Grade    : {data['risk_grade']}")
            print(f"  Top SHAP reason codes: {data['top_reason_codes'][:5]}")
        else:
            print(f"  Error Response: {res.text}")

        # Case e) NaN / Missing Fields
        print("\nCase e) NaN / Missing Fields...")
        # Since JSON does not have raw NaN (usually represented by null or missing values),
        # let's try sending nulls for several fields.
        # But wait! Does the current Pydantic schema allow nulls? Let's check how Pydantic responds.
        payload_nan = {
            "borrower_id": "MSME00001",
            "current_snapshot": {
                "dscr": None, # missing DSCR
                "bureau_score": 750,
                "bureau_enquiries_6m": 1,
                "gst_turnover_lakhs": None, # missing GST
                "gst_filing_delay_days": 0,
                "gst_filing_missed": 0,
                "bank_avg_balance_lakhs": 5.0,
                "bank_balance_volatility": None, # missing volatility
                "overdraft_utilization_pct": 0.2,
                "epfo_employee_count": 20,
                "dpd_current": 0,
                "dpd_max_12m": 0,
                "gst_remark_sentiment_score": 0.8,
                "transaction_anomaly_score": 0.02,
                "litigation_flag": 0,
                "litigation_severity": 0,
                "news_sentiment_score": None # missing news sentiment
            }
        }
        res = client.post("/api/v1/predict/live", json=payload_nan, headers=headers)
        print(f"  Status Code: {res.status_code}")
        print(f"  Response Content: {res.text}")

if __name__ == "__main__":
    main()
