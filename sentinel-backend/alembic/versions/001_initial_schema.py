"""Initial schema — all Kavach tables

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-07-11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id",            sa.Integer(),    primary_key=True),
        sa.Column("username",      sa.String(64),   nullable=False, unique=True),
        sa.Column("name",          sa.String(128),  nullable=False),
        sa.Column("role",          sa.String(32),   nullable=False),
        sa.Column("password_hash", sa.String(256),  nullable=False),
        sa.Column("is_active",     sa.Boolean(),    nullable=False, server_default="true"),
        sa.Column("created_at",    sa.DateTime(),   server_default=sa.text("NOW()")),
        sa.Column("updated_at",    sa.DateTime(),   server_default=sa.text("NOW()")),
    )
    op.create_index("ix_users_username", "users", ["username"])

    # ── borrower_profiles ─────────────────────────────────────────────────────
    op.create_table(
        "borrower_profiles",
        sa.Column("id",                     sa.Integer(), primary_key=True),
        sa.Column("borrower_id",            sa.String(32),  nullable=False, unique=True),
        sa.Column("business_name",          sa.String(256)),
        sa.Column("gstin",                  sa.String(20)),
        sa.Column("pan",                    sa.String(12)),
        sa.Column("loan_type",              sa.String(64)),
        sa.Column("industry",               sa.String(128)),
        sa.Column("region",                 sa.String(64)),
        sa.Column("loan_amount_lakhs",      sa.Float()),
        sa.Column("vintage_years",          sa.Float()),
        sa.Column("employee_count_initial", sa.Integer()),
        sa.Column("created_at",             sa.DateTime(), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_bp_borrower_id", "borrower_profiles", ["borrower_id"])
    op.create_index("ix_bp_industry",    "borrower_profiles", ["industry"])
    op.create_index("ix_bp_region",      "borrower_profiles", ["region"])
    op.create_index("ix_bp_loan_type",   "borrower_profiles", ["loan_type"])

    # ── predictions ───────────────────────────────────────────────────────────
    op.create_table(
        "predictions",
        sa.Column("id",             sa.Integer(), primary_key=True),
        sa.Column("borrower_id",    sa.String(32),  nullable=False),
        sa.Column("month_index",    sa.Integer(),   nullable=False),
        sa.Column("as_of_month",    sa.String(8),   nullable=False),
        sa.Column("loan_type",      sa.String(64)),
        sa.Column("pd_probability", sa.Float(),     nullable=False),
        sa.Column("stress_score",   sa.Float(),     nullable=False),
        sa.Column("risk_grade",     sa.String(4),   nullable=False),
        sa.Column("model_version",  sa.String(16),  server_default="v1.0.0"),
        sa.Column("created_at",     sa.DateTime(),  server_default=sa.text("NOW()")),
        sa.UniqueConstraint("borrower_id", "month_index", name="uq_prediction_borrower_month"),
    )
    op.create_index("ix_pred_borrower_id",  "predictions", ["borrower_id"])
    op.create_index("ix_pred_month_index",  "predictions", ["month_index"])
    op.create_index("ix_pred_risk_grade",   "predictions", ["risk_grade"])
    op.create_index("ix_pred_as_of_month",  "predictions", ["as_of_month"])

    # ── explanations ──────────────────────────────────────────────────────────
    op.create_table(
        "explanations",
        sa.Column("id",           sa.Integer(),  primary_key=True),
        sa.Column("borrower_id",  sa.String(32), nullable=False, unique=True),
        sa.Column("reason_codes", sa.Text(),     nullable=False),
        sa.Column("created_at",   sa.DateTime(), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_exp_borrower_id", "explanations", ["borrower_id"])

    # ── monthly_snapshots ─────────────────────────────────────────────────────
    op.create_table(
        "monthly_snapshots",
        sa.Column("id",                         sa.Integer(),  primary_key=True),
        sa.Column("borrower_id",                sa.String(32), nullable=False),
        sa.Column("as_of_month",                sa.String(8),  nullable=False),
        sa.Column("month_index",                sa.Integer(),  nullable=False),
        sa.Column("loan_type",                  sa.String(64)),
        sa.Column("industry",                   sa.String(128)),
        sa.Column("dscr",                       sa.Float()),
        sa.Column("bureau_score",               sa.Integer()),
        sa.Column("bureau_enquiries_6m",        sa.Integer()),
        sa.Column("gst_turnover_lakhs",         sa.Float()),
        sa.Column("gst_filing_delay_days",      sa.Integer()),
        sa.Column("gst_filing_missed",          sa.Integer()),
        sa.Column("bank_avg_balance_lakhs",     sa.Float()),
        sa.Column("bank_balance_volatility",    sa.Float()),
        sa.Column("overdraft_utilization_pct",  sa.Float()),
        sa.Column("epfo_employee_count",        sa.Integer()),
        sa.Column("dpd_current",                sa.Integer()),
        sa.Column("dpd_max_12m",                sa.Integer()),
        sa.Column("gst_remark_sentiment_score", sa.Float()),
        sa.Column("transaction_anomaly_score",  sa.Float()),
        sa.Column("litigation_flag",            sa.Integer()),
        sa.Column("litigation_severity",        sa.Integer()),
        sa.Column("news_sentiment_score",       sa.Float()),
        sa.Column("label_default_12m",          sa.Integer()),
        sa.Column("is_defaulter",               sa.Integer()),
        sa.UniqueConstraint("borrower_id", "month_index", name="uq_snapshot_borrower_month"),
    )
    op.create_index("ix_snap_borrower_id",  "monthly_snapshots", ["borrower_id"])
    op.create_index("ix_snap_month_index",  "monthly_snapshots", ["month_index"])

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id",        sa.Integer(),  primary_key=True),
        sa.Column("event",     sa.Text(),     nullable=False),
        sa.Column("user",      sa.String(64), server_default="system"),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_audit_timestamp", "audit_logs", ["timestamp"])

    # ── alerts ────────────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id",            sa.Integer(),  primary_key=True),
        sa.Column("alert_id",      sa.String(64), nullable=False, unique=True),
        sa.Column("borrower_id",   sa.String(32), nullable=False),
        sa.Column("business_name", sa.String(256)),
        sa.Column("loan_type",     sa.String(64)),
        sa.Column("industry",      sa.String(128)),
        sa.Column("alert_type",    sa.String(32), nullable=False),
        sa.Column("severity",      sa.String(16), nullable=False),
        sa.Column("message",       sa.Text()),
        sa.Column("old_grade",     sa.String(4)),
        sa.Column("new_grade",     sa.String(4)),
        sa.Column("stress_score",  sa.Float()),
        sa.Column("triggered_at",  sa.DateTime(), server_default=sa.text("NOW()")),
        sa.Column("is_dismissed",  sa.Boolean(),  server_default="false"),
    )
    op.create_index("ix_alert_borrower_id",  "alerts", ["borrower_id"])
    op.create_index("ix_alert_severity",     "alerts", ["severity"])
    op.create_index("ix_alert_triggered_at", "alerts", ["triggered_at"])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("audit_logs")
    op.drop_table("monthly_snapshots")
    op.drop_table("explanations")
    op.drop_table("predictions")
    op.drop_table("borrower_profiles")
    op.drop_table("users")
