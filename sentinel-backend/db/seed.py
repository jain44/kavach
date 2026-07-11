"""
Kavach -- Database Seed Script
Reads existing CSV files and inserts all data into PostgreSQL.

Run once after creating the database schema:
    python -m db.seed

This script is idempotent: re-running it will skip rows that already exist.
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
from sqlalchemy.exc import IntegrityError

from db.database import engine, SessionLocal
from db.models import (
    Base, User, BorrowerProfile, Prediction,
    Explanation, MonthlySnapshot, AuditLog, AlertRecord
)

BATCH_SIZE = 500   # Rows inserted per transaction batch


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


def _batch_insert(db: Session, objects: list, label: str):
    """Insert objects in batches, skipping duplicates via IntegrityError."""
    inserted = 0
    skipped  = 0
    for i in range(0, len(objects), BATCH_SIZE):
        batch = objects[i : i + BATCH_SIZE]
        try:
            db.bulk_save_objects(batch)
            db.commit()
            inserted += len(batch)
        except IntegrityError:
            db.rollback()
            # Fall back to individual inserts to skip only duplicates
            for obj in batch:
                try:
                    db.add(obj)
                    db.commit()
                    inserted += 1
                except IntegrityError:
                    db.rollback()
                    skipped += 1
        if (i // BATCH_SIZE) % 10 == 0:
            print(f"    {label}: {inserted:,} inserted, {skipped:,} skipped ...", end="\r")
    print(f"    {label}: {inserted:,} inserted, {skipped:,} skipped.    ")
    return inserted


# ─── Seed Functions ───────────────────────────────────────────────────────────

def seed_users(db: Session):
    print("\n[1/7] Seeding users...")
    demo_users = [
        ("risk_officer", "Priya Sharma",    "risk_officer", "kavach123"),
        ("rm",           "Arjun Mehta",     "rm",           "kavach123"),
        ("cro",          "Dr. Vikram Nair", "cro",          "kavach123"),
        ("compliance",   "Anjali Iyer",     "compliance",   "kavach123"),
        ("admin",        "System Admin",    "admin",        "kavach123"),
    ]
    created = 0
    for username, name, role, password in demo_users:
        exists = db.query(User).filter_by(username=username).first()
        if not exists:
            db.add(User(
                username=username,
                name=name,
                role=role,
                password_hash=_hash(password),
                is_active=True,
            ))
            created += 1
    db.commit()
    print(f"    Users: {created} created, {len(demo_users) - created} already exist.")


def seed_borrower_profiles(db: Session):
    print("\n[2/7] Seeding borrower profiles...")
    csv_path = DATA_DIR / "borrower_profiles.csv"
    if not csv_path.exists():
        print(f"    WARN: {csv_path} not found — skipping.")
        return

    df = pd.read_csv(csv_path)
    print(f"    Loaded {len(df):,} rows from CSV.")

    objects = []
    for _, row in df.iterrows():
        objects.append(BorrowerProfile(
            borrower_id=str(row["borrower_id"]),
            business_name=str(row.get("business_name", "")),
            gstin=str(row.get("gstin", "")),
            pan=str(row.get("pan", "")),
            loan_type=str(row.get("loan_type", "")),
            industry=str(row.get("industry", "")),
            region=str(row.get("region", "")),
            loan_amount_lakhs=_safe_float(row.get("loan_amount_lakhs")),
            vintage_years=_safe_float(row.get("vintage_years")),
            employee_count_initial=_safe_int(row.get("employee_count_initial")),
        ))
    _batch_insert(db, objects, "BorrowerProfile")


def seed_predictions(db: Session):
    print("\n[3/7] Seeding predictions...")
    csv_path = DATA_DIR / "predictions.csv"
    if not csv_path.exists():
        print(f"    WARN: {csv_path} not found — skipping.")
        return

    df = pd.read_csv(csv_path)
    print(f"    Loaded {len(df):,} rows from CSV.")

    objects = []
    for _, row in df.iterrows():
        objects.append(Prediction(
            borrower_id=str(row["borrower_id"]),
            month_index=_safe_int(row["month_index"]),
            as_of_month=str(row["as_of_month"]),
            loan_type=str(row.get("loan_type", "")),
            pd_probability=_safe_float(row["pd_probability"]),
            stress_score=_safe_float(row["stress_score"]),
            risk_grade=str(row["risk_grade"]),
            model_version="v1.0.0",
        ))
    _batch_insert(db, objects, "Prediction")


def seed_explanations(db: Session):
    print("\n[4/7] Seeding explanations...")
    csv_path = DATA_DIR / "explanations.csv"
    if not csv_path.exists():
        print(f"    WARN: {csv_path} not found — skipping.")
        return

    df = pd.read_csv(csv_path)
    print(f"    Loaded {len(df):,} rows from CSV.")

    objects = []
    for _, row in df.iterrows():
        objects.append(Explanation(
            borrower_id=str(row["borrower_id"]),
            reason_codes=str(row["reason_codes"]),
        ))
    _batch_insert(db, objects, "Explanation")


def seed_snapshots(db: Session):
    print("\n[5/7] Seeding monthly snapshots...")
    csv_path = DATA_DIR / "monthly_snapshots.csv"
    if not csv_path.exists():
        print(f"    WARN: {csv_path} not found — skipping.")
        return

    df = pd.read_csv(csv_path)
    print(f"    Loaded {len(df):,} rows from CSV. (This may take a few minutes...)")

    objects = []
    for _, row in df.iterrows():
        objects.append(MonthlySnapshot(
            borrower_id=str(row["borrower_id"]),
            as_of_month=str(row["as_of_month"]),
            month_index=_safe_int(row["month_index"]),
            loan_type=str(row.get("loan_type", "")),
            industry=str(row.get("industry", "")),
            dscr=_safe_float(row.get("dscr")),
            bureau_score=_safe_int(row.get("bureau_score"), 650),
            bureau_enquiries_6m=_safe_int(row.get("bureau_enquiries_6m")),
            gst_turnover_lakhs=_safe_float(row.get("gst_turnover_lakhs")),
            gst_filing_delay_days=_safe_int(row.get("gst_filing_delay_days")),
            gst_filing_missed=_safe_int(row.get("gst_filing_missed")),
            bank_avg_balance_lakhs=_safe_float(row.get("bank_avg_balance_lakhs")),
            bank_balance_volatility=_safe_float(row.get("bank_balance_volatility")),
            overdraft_utilization_pct=_safe_float(row.get("overdraft_utilization_pct")),
            epfo_employee_count=_safe_int(row.get("epfo_employee_count")),
            dpd_current=_safe_int(row.get("dpd_current")),
            dpd_max_12m=_safe_int(row.get("dpd_max_12m")),
            gst_remark_sentiment_score=_safe_float(row.get("gst_remark_sentiment_score")),
            transaction_anomaly_score=_safe_float(row.get("transaction_anomaly_score")),
            litigation_flag=_safe_int(row.get("litigation_flag")),
            litigation_severity=_safe_int(row.get("litigation_severity")),
            news_sentiment_score=_safe_float(row.get("news_sentiment_score")),
            label_default_12m=_safe_int(row.get("label_default_12m")),
            is_defaulter=_safe_int(row.get("_is_defaulter", row.get("is_defaulter", 0))),
        ))
    _batch_insert(db, objects, "MonthlySnapshot")


def seed_audit_logs(db: Session):
    print("\n[6/7] Seeding audit logs...")
    # Read flat-file audit log if it exists
    audit_file = BASE_DIR / "kavach_audit.log"
    seed_events = [
        ("Model v1.0.0 deployed",                       "system"),
        ("Batch scoring run completed (5000 accounts)", "system"),
        ("Manual override: MSME00042 flagged",          "risk_officer"),
        ("Database migration completed: CSV → PostgreSQL", "system"),
    ]

    count = 0
    if audit_file.exists():
        with open(audit_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    db.add(AuditLog(
                        event=entry.get("event", ""),
                        user=entry.get("user", "system"),
                        timestamp=datetime.fromisoformat(entry["timestamp"]) if "timestamp" in entry else datetime.utcnow(),
                    ))
                    count += 1
                except Exception:
                    pass
        db.commit()
        print(f"    Migrated {count} events from flat-file audit log.")
    else:
        for event, user in seed_events:
            db.add(AuditLog(event=event, user=user))
        db.commit()
        print(f"    Seeded {len(seed_events)} default audit events.")


def seed_alerts(db: Session):
    print("\n[7/7] Pre-computing and seeding initial alerts...")
    # Alerts are computed dynamically from predictions, so we just note the seed
    existing = db.query(AlertRecord).count()
    if existing > 0:
        print(f"    {existing} alerts already exist — skipping.")
        return

    # A placeholder seed alert so the table isn't empty
    db.add(AuditLog(
        event="Alert table initialized — live alerts computed on first API request",
        user="system",
    ))
    db.commit()
    print("    Alert table ready (populated on first /api/v1/alerts request).")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Kavach DB Seed — CSV → PostgreSQL")
    print("=" * 60)
    print(f"  Target: {os.environ.get('DATABASE_URL', 'postgresql+psycopg2://kavach:kavach123@localhost:5432/kavach_db')}")
    print()

    # Create all tables
    print("[0/7] Creating schema (if not exists)...")
    Base.metadata.create_all(bind=engine)
    print("    Schema ready.")

    db = SessionLocal()
    try:
        t0 = time.time()
        seed_users(db)
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
