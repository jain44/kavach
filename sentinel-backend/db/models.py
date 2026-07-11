"""
Kavach -- SQLAlchemy ORM Models
Tables: users, borrower_profiles, predictions, explanations, monthly_snapshots, audit_logs, alerts
"""

from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text,
    Index, UniqueConstraint, ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB
from db.database import Base


# ─── Users ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id          = Column(Integer, primary_key=True, index=True)
    username    = Column(String(64), unique=True, nullable=False, index=True)
    name        = Column(String(128), nullable=False)
    role        = Column(String(32), nullable=False)  # risk_officer | rm | cro | compliance | admin
    password_hash = Column(String(256), nullable=False)
    is_active   = Column(Boolean, default=True, nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


# ─── Borrower Profiles ────────────────────────────────────────────────────────

class BorrowerProfile(Base):
    __tablename__ = "borrower_profiles"

    id                    = Column(Integer, primary_key=True, index=True)
    borrower_id           = Column(String(32), unique=True, nullable=False, index=True)
    business_name         = Column(String(256))
    gstin                 = Column(String(20))
    pan                   = Column(String(12))
    loan_type             = Column(String(64))
    industry              = Column(String(128))
    region                = Column(String(64))
    loan_amount_lakhs     = Column(Float)
    vintage_years         = Column(Float)
    employee_count_initial = Column(Integer)
    created_at            = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_bp_industry", "industry"),
        Index("ix_bp_region", "region"),
        Index("ix_bp_loan_type", "loan_type"),
    )

    def __repr__(self):
        return f"<BorrowerProfile {self.borrower_id}>"


# ─── Predictions ──────────────────────────────────────────────────────────────

class Prediction(Base):
    __tablename__ = "predictions"

    id             = Column(Integer, primary_key=True, index=True)
    borrower_id    = Column(String(32), nullable=False, index=True)
    month_index    = Column(Integer, nullable=False)
    as_of_month    = Column(String(8), nullable=False)   # "YYYY-MM"
    loan_type      = Column(String(64))
    pd_probability = Column(Float, nullable=False)
    stress_score   = Column(Float, nullable=False)
    risk_grade     = Column(String(4), nullable=False)
    model_version  = Column(String(16), default="v1.0.0")
    created_at     = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("borrower_id", "month_index", name="uq_prediction_borrower_month"),
        Index("ix_pred_month_index", "month_index"),
        Index("ix_pred_risk_grade", "risk_grade"),
        Index("ix_pred_as_of_month", "as_of_month"),
    )

    def __repr__(self):
        return f"<Prediction {self.borrower_id} {self.as_of_month} {self.risk_grade}>"


# ─── SHAP Explanations ────────────────────────────────────────────────────────

class Explanation(Base):
    __tablename__ = "explanations"

    id           = Column(Integer, primary_key=True, index=True)
    borrower_id  = Column(String(32), nullable=False, unique=True, index=True)
    reason_codes = Column(Text, nullable=False)   # JSON string of reason codes list
    created_at   = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Explanation {self.borrower_id}>"


# ─── Monthly Snapshots ────────────────────────────────────────────────────────

class MonthlySnapshot(Base):
    __tablename__ = "monthly_snapshots"

    id                          = Column(Integer, primary_key=True, index=True)
    borrower_id                 = Column(String(32), nullable=False, index=True)
    as_of_month                 = Column(String(8), nullable=False)
    month_index                 = Column(Integer, nullable=False)
    loan_type                   = Column(String(64))
    industry                    = Column(String(128))
    dscr                        = Column(Float)
    bureau_score                = Column(Integer)
    bureau_enquiries_6m         = Column(Integer)
    gst_turnover_lakhs          = Column(Float)
    gst_filing_delay_days       = Column(Integer)
    gst_filing_missed           = Column(Integer)
    bank_avg_balance_lakhs      = Column(Float)
    bank_balance_volatility     = Column(Float)
    overdraft_utilization_pct   = Column(Float)
    epfo_employee_count         = Column(Integer)
    dpd_current                 = Column(Integer)
    dpd_max_12m                 = Column(Integer)
    gst_remark_sentiment_score  = Column(Float)
    transaction_anomaly_score   = Column(Float)
    litigation_flag             = Column(Integer)
    litigation_severity         = Column(Integer)
    news_sentiment_score        = Column(Float)
    label_default_12m           = Column(Integer)
    is_defaulter                = Column(Integer)

    __table_args__ = (
        UniqueConstraint("borrower_id", "month_index", name="uq_snapshot_borrower_month"),
        Index("ix_snap_month_index", "month_index"),
    )

    def __repr__(self):
        return f"<MonthlySnapshot {self.borrower_id} {self.as_of_month}>"


# ─── Audit Logs ───────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id         = Column(Integer, primary_key=True, index=True)
    event      = Column(Text, nullable=False)
    user       = Column(String(64), default="system")
    timestamp  = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<AuditLog [{self.user}] {self.event[:40]}>"


# ─── Alerts ───────────────────────────────────────────────────────────────────

class AlertRecord(Base):
    __tablename__ = "alerts"

    id            = Column(Integer, primary_key=True, index=True)
    alert_id      = Column(String(64), unique=True, nullable=False, index=True)
    borrower_id   = Column(String(32), nullable=False, index=True)
    business_name = Column(String(256))
    loan_type     = Column(String(64))
    industry      = Column(String(128))
    alert_type    = Column(String(32), nullable=False)   # grade_downgrade | stress_spike
    severity      = Column(String(16), nullable=False)   # critical | high | medium
    message       = Column(Text)
    old_grade     = Column(String(4))
    new_grade     = Column(String(4))
    stress_score  = Column(Float)
    triggered_at  = Column(DateTime, default=datetime.utcnow, index=True)
    is_dismissed  = Column(Boolean, default=False)

    __table_args__ = (
        Index("ix_alert_severity", "severity"),
        Index("ix_alert_triggered_at", "triggered_at"),
    )

    def __repr__(self):
        return f"<AlertRecord {self.alert_id} {self.severity}>"
