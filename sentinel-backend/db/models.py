"""
Kavach -- SQLAlchemy ORM Models
Tables: users, model_versions, borrower_profiles, predictions, explanations, monthly_snapshots, audit_logs, alerts
"""

from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text,
    Index, UniqueConstraint, ForeignKey,
)
from db.database import Base


# ─── Users ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String(64), unique=True, nullable=False, index=True)
    name          = Column(String(128), nullable=False)
    role          = Column(String(32), nullable=False)  # risk_officer | rm | cro | compliance | admin
    password_hash = Column(String(256), nullable=False)
    is_active     = Column(Boolean, default=True, nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


# ─── Model Versions ───────────────────────────────────────────────────────────

class ModelVersion(Base):
    __tablename__ = "model_versions"

    version_id            = Column(String(32), primary_key=True)
    trained_at            = Column(DateTime, default=datetime.utcnow, nullable=False)
    metrics_snapshot_json = Column(Text, nullable=False)  # JSON representation of performance metrics
    is_current            = Column(Boolean, default=False, nullable=False, index=True)

    def __repr__(self):
        return f"<ModelVersion {self.version_id} (current={self.is_current})>"


# ─── Borrower Profiles ────────────────────────────────────────────────────────

class BorrowerProfile(Base):
    __tablename__ = "borrower_profiles"

    id                     = Column(Integer, primary_key=True, index=True)
    borrower_id            = Column(String(32), unique=True, nullable=False, index=True)
    business_name          = Column(String(256), nullable=False)
    gstin                  = Column(String(256), nullable=False)  # Encrypted at rest
    pan                    = Column(String(256), nullable=False)  # Encrypted at rest
    loan_type              = Column(String(64), nullable=False)
    industry               = Column(String(128), nullable=False)
    region                 = Column(String(64), nullable=False)
    loan_amount_lakhs      = Column(Float, nullable=False)
    vintage_years          = Column(Float, nullable=False)
    employee_count_initial = Column(Integer, nullable=False)
    created_at             = Column(DateTime, default=datetime.utcnow, nullable=False)

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

    id               = Column(Integer, primary_key=True, index=True)
    borrower_id      = Column(String(32), ForeignKey("borrower_profiles.borrower_id", ondelete="CASCADE"), nullable=False, index=True)
    month_index      = Column(Integer, nullable=False, index=True)
    as_of_month      = Column(String(8), nullable=False, index=True)   # "YYYY-MM"
    loan_type        = Column(String(64), nullable=False)
    pd_probability   = Column(Float, nullable=False)
    stress_score     = Column(Float, nullable=False)
    risk_grade       = Column(String(4), nullable=False, index=True)
    model_version_id = Column(String(32), ForeignKey("model_versions.version_id", ondelete="SET NULL"), nullable=True, index=True)
    created_at       = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("borrower_id", "month_index", name="uq_prediction_borrower_month"),
    )

    def __repr__(self):
        return f"<Prediction {self.borrower_id} {self.as_of_month} {self.risk_grade}>"


# ─── SHAP Explanations ────────────────────────────────────────────────────────

class Explanation(Base):
    __tablename__ = "explanations"

    id           = Column(Integer, primary_key=True, index=True)
    borrower_id  = Column(String(32), ForeignKey("borrower_profiles.borrower_id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    reason_codes = Column(Text, nullable=False)   # JSON string of reason codes list
    created_at   = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Explanation {self.borrower_id}>"


# ─── Monthly Snapshots ────────────────────────────────────────────────────────

class MonthlySnapshot(Base):
    __tablename__ = "monthly_snapshots"

    id                          = Column(Integer, primary_key=True, index=True)
    borrower_id                 = Column(String(32), ForeignKey("borrower_profiles.borrower_id", ondelete="CASCADE"), nullable=False, index=True)
    as_of_month                 = Column(String(8), nullable=False)
    month_index                 = Column(Integer, nullable=False, index=True)
    loan_type                   = Column(String(64), nullable=False)
    industry                    = Column(String(128), nullable=False)
    dscr                        = Column(Float, nullable=False)
    bureau_score                = Column(Integer, nullable=False)
    bureau_enquiries_6m         = Column(Integer, nullable=False)
    gst_turnover_lakhs          = Column(Float, nullable=False)
    gst_filing_delay_days       = Column(Integer, nullable=False)
    gst_filing_missed           = Column(Integer, nullable=False)
    bank_avg_balance_lakhs      = Column(Float, nullable=False)
    bank_balance_volatility     = Column(Float, nullable=False)
    overdraft_utilization_pct   = Column(Float, nullable=False)
    epfo_employee_count         = Column(Integer, nullable=False)
    dpd_current                 = Column(Integer, nullable=False)
    dpd_max_12m                 = Column(Integer, nullable=False)
    gst_remark_sentiment_score  = Column(Float, nullable=False)
    transaction_anomaly_score   = Column(Float, nullable=False)
    litigation_flag             = Column(Integer, nullable=False)
    litigation_severity         = Column(Integer, nullable=False)
    news_sentiment_score        = Column(Float, nullable=False)
    label_default_12m           = Column(Integer, nullable=False)
    is_defaulter                = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("borrower_id", "month_index", name="uq_snapshot_borrower_month"),
    )

    def __repr__(self):
        return f"<MonthlySnapshot {self.borrower_id} {self.as_of_month}>"


# ─── Audit Logs ───────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id         = Column(Integer, primary_key=True, index=True)
    event      = Column(Text, nullable=False)
    user       = Column(String(64), default="system", nullable=False)
    timestamp  = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<AuditLog [{self.user}] {self.event[:40]}>"


# ─── Alerts ───────────────────────────────────────────────────────────────────

class AlertRecord(Base):
    __tablename__ = "alerts"

    id            = Column(Integer, primary_key=True, index=True)
    alert_id      = Column(String(64), unique=True, nullable=False, index=True)
    borrower_id   = Column(String(32), ForeignKey("borrower_profiles.borrower_id", ondelete="CASCADE"), nullable=False, index=True)
    business_name = Column(String(256), nullable=False)
    loan_type     = Column(String(64), nullable=False)
    industry      = Column(String(128), nullable=False)
    alert_type    = Column(String(32), nullable=False)   # grade_downgrade | stress_spike
    severity      = Column(String(16), nullable=False, index=True)   # critical | high | medium
    message       = Column(Text, nullable=False)
    old_grade     = Column(String(4), nullable=True)
    new_grade     = Column(String(4), nullable=True)
    stress_score  = Column(Float, nullable=False)
    triggered_at  = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    is_dismissed  = Column(Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<AlertRecord {self.alert_id} {self.severity}>"


# ─── Account Notes (RM Follow-up) ─────────────────────────────────────────────

class AccountNote(Base):
    __tablename__ = "account_notes"

    id          = Column(Integer, primary_key=True, index=True)
    borrower_id = Column(String(32), ForeignKey("borrower_profiles.borrower_id", ondelete="CASCADE"), nullable=False, index=True)
    note_text   = Column(Text, nullable=False)
    created_by  = Column(String(64), default="rm", nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<AccountNote {self.borrower_id} by {self.created_by}>"

