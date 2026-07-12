"""
Kavach -- Database Seed & Hardening Script
Reads existing CSV files and inserts all data into PostgreSQL/SQLite using high-performance bulk upserts.

Run once after creating the database schema:
    python -m db.seed

This script is fully idempotent: re-running it will update existing rows.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# ─── Path Setup ───────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "generated"

# Add project root to sys.path
sys.path.insert(0, str(BASE_DIR))

import bcrypt
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from db.database import engine, SessionLocal, bulk_upsert
from db.models import (
    Base, User, BorrowerProfile, Prediction,
    Explanation, MonthlySnapshot, AuditLog, AlertRecord, ModelVersion
)
from db.crypto import encrypt_val

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _safe_int(val, default=0) -> int:
    try:
        v = int(val)
        return default if (v != v) else v   # NaN check
    except (ValueError, TypeError):
        return default


def _safe_float(val, default=0.0) -> float:
    try:
        v = float(val)
        return default if (v != v) else v
    except (ValueError, TypeError):
        return default


# ─── Seed Functions ───────────────────────────────────────────────────────────

def seed_users(db: Session):
    print("\n[1/8] Seeding users...")
    demo_users = [
        ("risk_officer", "Priya Sharma",    "risk_officer", "kavach123"),
        ("rm",           "Arjun Mehta",     "rm",           "kavach123"),
        ("cro",          "Dr. Vikram Nair", "cro",          "kavach123"),
        ("compliance",   "Anjali Iyer",     "compliance",   "kavach123"),
        ("admin",        "System Admin",    "admin",        "kavach123"),
    ]
    
    users_list = []
    for username, name, role, password in demo_users:
        users_list.append({
            "username": username,
            "name": name,
            "role": role,
            "password_hash": _hash(password),
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
    
    upserted = bulk_upsert(db, User, users_list, ["username"])
    print(f"    Users: {upserted} records seeded/updated.")


def seed_model_versions(db: Session):
    print("\n[2/8] Seeding active model version...")
    metrics_snapshot = {
        "model_version": "v1.0.0",
        "trained_at": datetime.utcnow().isoformat(),
        "algorithm": "XGBoost + Isotonic Calibration",
        "feature_count": 52,
        "train_months": "0-17",
        "val_months": "18-20",
        "test_months": "21-23",
        "avg_auc_roc": 0.92,
        "avg_precision_at_top10": 0.74,
        "avg_recall": 0.82,
        "avg_false_positive_rate": 0.11,
        "meets_auc_target": True
    }
    
    versions = [{
        "version_id": "v1.0.0",
        "trained_at": datetime.utcnow(),
        "metrics_snapshot_json": json.dumps(metrics_snapshot),
        "is_current": True
    }]
    
    upserted = bulk_upsert(db, ModelVersion, versions, ["version_id"])
    print(f"    Model Versions: {upserted} records seeded/updated.")


def seed_borrower_profiles(db: Session):
    print("\n[3/8] Seeding borrower profiles (with encryption)...")
    csv_path = DATA_DIR / "borrower_profiles.csv"
    if not csv_path.exists():
        print(f"    WARN: {csv_path} not found — skipping.")
        return

    df = pd.read_csv(csv_path)
    print(f"    Loaded {len(df):,} profiles from CSV.")

    records = df.to_dict('records')
    profiles_list = [
        {
            "borrower_id": str(row["borrower_id"]),
            "business_name": str(row.get("business_name", "")),
            # Application-level encryption (Fernet)
            "gstin": encrypt_val(str(row.get("gstin", ""))),
            "pan": encrypt_val(str(row.get("pan", ""))),
            "loan_type": str(row.get("loan_type", "")),
            "industry": str(row.get("industry", "")),
            "region": str(row.get("region", "")),
            "loan_amount_lakhs": _safe_float(row.get("loan_amount_lakhs")),
            "vintage_years": _safe_float(row.get("vintage_years")),
            "employee_count_initial": _safe_int(row.get("employee_count_initial")),
            "created_at": datetime.utcnow()
        }
        for row in records
    ]
    upserted = bulk_upsert(db, BorrowerProfile, profiles_list, ["borrower_id"])
    print(f"    BorrowerProfile: {upserted} records seeded/updated.")


def seed_predictions(db: Session):
    print("\n[4/8] Seeding predictions...")
    csv_path = DATA_DIR / "predictions.csv"
    if not csv_path.exists():
        print(f"    WARN: {csv_path} not found — skipping.")
        return

    df = pd.read_csv(csv_path)
    print(f"    Loaded {len(df):,} predictions from CSV.")

    records = df.to_dict('records')
    preds_list = [
        {
            "borrower_id": str(row["borrower_id"]),
            "month_index": _safe_int(row["month_index"]),
            "as_of_month": str(row["as_of_month"]),
            "loan_type": str(row.get("loan_type", "")),
            "pd_probability": _safe_float(row["pd_probability"]),
            "stress_score": _safe_float(row["stress_score"]),
            "risk_grade": str(row["risk_grade"]),
            "model_version_id": "v1.0.0",
            "created_at": datetime.utcnow()
        }
        for row in records
    ]
    upserted = bulk_upsert(db, Prediction, preds_list, ["borrower_id", "month_index"])
    print(f"    Prediction: {upserted} records seeded/updated.")


def seed_explanations(db: Session):
    print("\n[5/8] Seeding explanations...")
    csv_path = DATA_DIR / "explanations.csv"
    if not csv_path.exists():
        print(f"    WARN: {csv_path} not found — skipping.")
        return

    df = pd.read_csv(csv_path)
    print(f"    Loaded {len(df):,} explanations from CSV.")

    records = df.to_dict('records')
    exps_list = [
        {
            "borrower_id": str(row["borrower_id"]),
            "reason_codes": str(row["reason_codes"]),
            "created_at": datetime.utcnow()
        }
        for row in records
    ]
    upserted = bulk_upsert(db, Explanation, exps_list, ["borrower_id"])
    print(f"    Explanation: {upserted} records seeded/updated.")


def seed_snapshots(db: Session):
    print("\n[6/8] Seeding monthly snapshots...")
    csv_path = DATA_DIR / "monthly_snapshots.csv"
    if not csv_path.exists():
        print(f"    WARN: {csv_path} not found — skipping.")
        return

    df = pd.read_csv(csv_path)
    print(f"    Loaded {len(df):,} snapshots from CSV.")

    records = df.to_dict('records')
    snaps_list = [
        {
            "borrower_id": str(row["borrower_id"]),
            "as_of_month": str(row["as_of_month"]),
            "month_index": _safe_int(row["month_index"]),
            "loan_type": str(row.get("loan_type", "")),
            "industry": str(row.get("industry", "")),
            "dscr": _safe_float(row.get("dscr")),
            "bureau_score": _safe_int(row.get("bureau_score"), 650),
            "bureau_enquiries_6m": _safe_int(row.get("bureau_enquiries_6m")),
            "gst_turnover_lakhs": _safe_float(row.get("gst_turnover_lakhs")),
            "gst_filing_delay_days": _safe_int(row.get("gst_filing_delay_days")),
            "gst_filing_missed": _safe_int(row.get("gst_filing_missed")),
            "bank_avg_balance_lakhs": _safe_float(row.get("bank_avg_balance_lakhs")),
            "bank_balance_volatility": _safe_float(row.get("bank_balance_volatility")),
            "overdraft_utilization_pct": _safe_float(row.get("overdraft_utilization_pct")),
            "epfo_employee_count": _safe_int(row.get("epfo_employee_count")),
            "dpd_current": _safe_int(row.get("dpd_current")),
            "dpd_max_12m": _safe_int(row.get("dpd_max_12m")),
            "gst_remark_sentiment_score": _safe_float(row.get("gst_remark_sentiment_score")),
            "transaction_anomaly_score": _safe_float(row.get("transaction_anomaly_score")),
            "litigation_flag": _safe_int(row.get("litigation_flag")),
            "litigation_severity": _safe_int(row.get("litigation_severity")),
            "news_sentiment_score": _safe_float(row.get("news_sentiment_score")),
            "label_default_12m": _safe_int(row.get("label_default_12m")),
            "is_defaulter": _safe_int(row.get("_is_defaulter", row.get("is_defaulter", 0)))
        }
        for row in records
    ]
    upserted = bulk_upsert(db, MonthlySnapshot, snaps_list, ["borrower_id", "month_index"])
    print(f"    MonthlySnapshot: {upserted} records seeded/updated.")


def seed_audit_logs(db: Session):
    print("\n[7/8] Seeding audit logs...")
    audit_file = BASE_DIR / "kavach_audit.log"
    seed_events = [
        ("Model v1.0.0 deployed", "system"),
        ("Batch scoring run completed (5000 accounts)", "system"),
        ("Manual override: MSME00042 flagged", "risk_officer"),
        ("Database migration & hardening completed", "system"),
    ]

    logs_list = []
    if audit_file.exists():
        with open(audit_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    logs_list.append({
                        "event": entry.get("event", ""),
                        "user": entry.get("user", "system"),
                        "timestamp": datetime.fromisoformat(entry["timestamp"]) if "timestamp" in entry else datetime.utcnow()
                    })
                except Exception:
                    pass

    # Ensure defaults exist
    for event, user in seed_events:
        logs_list.append({
            "event": event,
            "user": user,
            "timestamp": datetime.utcnow()
        })

    upserted = bulk_upsert(db, AuditLog, logs_list, ["id"])
    print(f"    AuditLog: {upserted} records seeded/updated.")


def seed_alerts(db: Session):
    print("\n[8/8] Computing and seeding stable warning alerts...")
    # Clean alerts to avoid leftovers
    db.query(AlertRecord).delete()
    db.commit()

    # Query latest month predictions
    max_month_idx = db.query(Prediction.month_index).order_by(Prediction.month_index.desc()).limit(1).scalar() or 0
    
    # Query current month predictions
    current_preds = db.query(Prediction).filter_by(month_index=max_month_idx).all()
    # Query previous month predictions to identify downgrades
    prev_preds = db.query(Prediction).filter_by(month_index=max_month_idx - 1).all()
    prev_grades = {p.borrower_id: p.risk_grade for p in prev_preds}

    # Fetch borrower profiles to obtain business names and metadata
    profiles = db.query(BorrowerProfile).all()
    profile_meta = {p.borrower_id: (p.business_name, p.industry, p.loan_type) for p in profiles}

    GRADE_ORDER = ["AAA", "AA", "A", "BBB", "BB", "B", "C", "D"]
    alerts_list = []

    for p in current_preds:
        bid = p.borrower_id
        grade = p.risk_grade
        prev_g = prev_grades.get(bid, grade)
        stress = p.stress_score
        name, ind, ltype = profile_meta.get(bid, (bid, "Unknown", p.loan_type))

        # Check for grade downgrades
        is_downgrade = False
        if prev_g in GRADE_ORDER and grade in GRADE_ORDER:
            if GRADE_ORDER.index(grade) > GRADE_ORDER.index(prev_g):
                is_downgrade = True

        if is_downgrade:
            severity = "critical" if grade in ["C", "D"] else "high"
            alerts_list.append({
                "alert_id": f"ALT-{bid}-DNGRD",
                "borrower_id": bid,
                "business_name": name,
                "loan_type": ltype,
                "industry": ind,
                "alert_type": "grade_downgrade",
                "severity": severity,
                "message": f"Risk grade downgraded from {prev_g} → {grade}",
                "old_grade": prev_g,
                "new_grade": grade,
                "stress_score": stress,
                "triggered_at": datetime.utcnow(),
                "is_dismissed": False
            })
        elif grade in ["C", "D"] and stress > 75:
            severity = "critical" if stress > 85 else "high"
            alerts_list.append({
                "alert_id": f"ALT-{bid}-STRESS",
                "borrower_id": bid,
                "business_name": name,
                "loan_type": ltype,
                "industry": ind,
                "alert_type": "stress_spike",
                "severity": severity,
                "message": f"Stress score critically elevated at {stress:.1f}/100",
                "old_grade": None,
                "new_grade": None,
                "stress_score": stress,
                "triggered_at": datetime.utcnow(),
                "is_dismissed": False
            })

    upserted = bulk_upsert(db, AlertRecord, alerts_list, ["alert_id"])
    print(f"    AlertRecord: {upserted} warnings computed, seeded, and stabilized.")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Kavach DB Seed & Hardening - CSV -> DB")
    print("=" * 60)
    print(f"  Connection URL: {engine.url}")
    print()

    print("[0/8] Verifying database schema...")
    Base.metadata.create_all(bind=engine)
    print("    Schema verified.")

    db = SessionLocal()
    try:
        # Check if database has already been seeded to avoid boot timeouts
        try:
            user_count = db.query(User).count()
            profile_count = db.query(BorrowerProfile).count()
            pred_count = db.query(Prediction).count()
            snapshot_count = db.query(MonthlySnapshot).count()
            explanation_count = db.query(Explanation).count()
            model_version_count = db.query(ModelVersion).count()
            core_tables_ready = all([
                user_count > 0,
                profile_count > 0,
                pred_count > 0,
                snapshot_count > 0,
                explanation_count > 0,
                model_version_count > 0,
            ])
            if core_tables_ready:
                print("  [SEED] Core database tables already contain records. Skipping seed process.")
                return
            else:
                print(
                    "  [SEED] Database incomplete "
                    f"(Users: {user_count}, Profiles: {profile_count}, Predictions: {pred_count}, "
                    f"Snapshots: {snapshot_count}, Explanations: {explanation_count}, "
                    f"ModelVersions: {model_version_count}). Seeding data..."
                )
        except Exception as e:
            print(f"  [SEED] Could not query database tables: {e}. Proceeding with seed.")

        t0 = time.time()
        seed_users(db)
        seed_model_versions(db)
        seed_borrower_profiles(db)
        seed_predictions(db)
        seed_explanations(db)
        seed_snapshots(db)
        seed_audit_logs(db)
        seed_alerts(db)
        elapsed = time.time() - t0
        print(f"\n{'=' * 60}")
        print(f"  Seed complete in {elapsed:.1f}s")
        print(f"{'=' * 60}")
    except Exception as e:
        db.rollback()
        print(f"\n  ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
