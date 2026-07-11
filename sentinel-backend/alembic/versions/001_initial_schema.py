"""Initial schema — all Kavach tables (Hardened)

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
        sa.Column("created_at",    sa.DateTime(),   nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at",    sa.DateTime(),   nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_users_username", "users", ["username"])

    # ── model_versions ────────────────────────────────────────────────────────
    op.create_table(
        "model_versions",
        sa.Column("version_id",            sa.String(32), primary_key=True),
        sa.Column("trained_at",            sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("metrics_snapshot_json", sa.Text(),     nullable=False),
        sa.Column("is_current",            sa.Boolean(),  nullable=False, server_default="false"),
    )
    op.create_index("ix_model_versions_is_current", "model_versions", ["is_current"])

    # ── borrower_profiles ─────────────────────────────────────────────────────
    op.create_table(
        "borrower_profiles",
        sa.Column("id",                     sa.Integer(),   primary_key=True),
        sa.Column("borrower_id",            sa.String(32),  nullable=False, unique=True),
        sa.Column("business_name",          sa.String(256), nullable=False),
        sa.Column("gstin",                  sa.String(256), nullable=False),
        sa.Column("pan",                    sa.String(256), nullable=False),
        sa.Column("loan_type",              sa.String(64),  nullable=False),
        sa.Column("industry",               sa.String(128), nullable=False),
        sa.Column("region",                 sa.String(64),  nullable=False),
        sa.Column("loan_amount_lakhs",      sa.Float(),     nullable=False),
        sa.Column("vintage_years",          sa.Float(),     nullable=False),
        sa.Column("employee_count_initial", sa.Integer(),   nullable=False),
        sa.Column("created_at",             sa.DateTime(),  nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_bp_borrower_id", "borrower_profiles", ["borrower_id"])
    op.create_index("ix_bp_industry",    "borrower_profiles", ["industry"])
    op.create_index("ix_bp_region",      "borrower_profiles", ["region"])
    op.create_index("ix_bp_loan_type",   "borrower_profiles", ["loan_type"])

    # ── predictions ───────────────────────────────────────────────────────────
    op.create_table(
        "predictions",
        sa.Column("id",               sa.Integer(), primary_key=True),
        sa.Column("borrower_id",      sa.String(32),  sa.ForeignKey("borrower_profiles.borrower_id", ondelete="CASCADE"), nullable=False),
        sa.Column("month_index",      sa.Integer(),   nullable=False),
        sa.Column("as_of_month",      sa.String(8),   nullable=False),
        sa.Column("loan_type",        sa.String(64),  nullable=False),
        sa.Column("pd_probability",   sa.Float(),     nullable=False),
        sa.Column("stress_score",     sa.Float(),     nullable=False),
        sa.Column("risk_grade",       sa.String(4),   nullable=False),
        sa.Column("model_version_id", sa.String(32),  sa.ForeignKey("model_versions.version_id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at",       sa.DateTime(),  nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("borrower_id", "month_index", name="uq_prediction_borrower_month"),
    )
    op.create_index("ix_pred_borrower_id",      "predictions", ["borrower_id"])
    op.create_index("ix_pred_month_index",      "predictions", ["month_index"])
    op.create_index("ix_pred_risk_grade",       "predictions", ["risk_grade"])
    op.create_index("ix_pred_as_of_month",      "predictions", ["as_of_month"])
    op.create_index("ix_pred_model_version_id", "predictions", ["model_version_id"])

    # ── explanations ──────────────────────────────────────────────────────────
    op.create_table(
        "explanations",
        sa.Column("id",           sa.Integer(),  primary_key=True),
        sa.Column("borrower_id",  sa.String(32), sa.ForeignKey("borrower_profiles.borrower_id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("reason_codes", sa.Text(),     nullable=False),
        sa.Column("created_at",   sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_exp_borrower_id", "explanations", ["borrower_id"])

    # ── monthly_snapshots ─────────────────────────────────────────────────────
    op.create_table(
        "monthly_snapshots",
        sa.Column("id",                         sa.Integer(),  primary_key=True),
        sa.Column("borrower_id",                sa.String(32), sa.ForeignKey("borrower_profiles.borrower_id", ondelete="CASCADE"), nullable=False),
        sa.Column("as_of_month",                sa.String(8),  nullable=False),
        sa.Column("month_index",                sa.Integer(),  nullable=False),
        sa.Column("loan_type",                  sa.String(64), nullable=False),
        sa.Column("industry",                   sa.String(128), nullable=False),
        sa.Column("dscr",                       sa.Float(),    nullable=False),
        sa.Column("bureau_score",               sa.Integer(),  nullable=False),
        sa.Column("bureau_enquiries_6m",        sa.Integer(),  nullable=False),
        sa.Column("gst_turnover_lakhs",         sa.Float(),    nullable=False),
        sa.Column("gst_filing_delay_days",      sa.Integer(),  nullable=False),
        sa.Column("gst_filing_missed",          sa.Integer(),  nullable=False),
        sa.Column("bank_avg_balance_lakhs",     sa.Float(),    nullable=False),
        sa.Column("bank_balance_volatility",    sa.Float(),    nullable=False),
        sa.Column("overdraft_utilization_pct",  sa.Float(),    nullable=False),
        sa.Column("epfo_employee_count",        sa.Integer(),  nullable=False),
        sa.Column("dpd_current",                sa.Integer(),  nullable=False),
        sa.Column("dpd_max_12m",                sa.Integer(),  nullable=False),
        sa.Column("gst_remark_sentiment_score", sa.Float(),    nullable=False),
        sa.Column("transaction_anomaly_score",  sa.Float(),    nullable=False),
        sa.Column("litigation_flag",            sa.Integer(),  nullable=False),
        sa.Column("litigation_severity",        sa.Integer(),  nullable=False),
        sa.Column("news_sentiment_score",       sa.Float(),    nullable=False),
        sa.Column("label_default_12m",          sa.Integer(),  nullable=False),
        sa.Column("is_defaulter",               sa.Integer(),  nullable=False),
        sa.UniqueConstraint("borrower_id", "month_index", name="uq_snapshot_borrower_month"),
    )
    op.create_index("ix_snap_borrower_id",  "monthly_snapshots", ["borrower_id"])
    op.create_index("ix_snap_month_index",  "monthly_snapshots", ["month_index"])

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id",        sa.Integer(),  primary_key=True),
        sa.Column("event",     sa.Text(),     nullable=False),
        sa.Column("user",      sa.String(64), nullable=False, server_default="system"),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_audit_timestamp", "audit_logs", ["timestamp"])

    # ── alerts ────────────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id",            sa.Integer(),  primary_key=True),
        sa.Column("alert_id",      sa.String(64), nullable=False, unique=True),
        sa.Column("borrower_id",   sa.String(32), sa.ForeignKey("borrower_profiles.borrower_id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_name", sa.String(256), nullable=False),
        sa.Column("loan_type",     sa.String(64),  nullable=False),
        sa.Column("industry",      sa.String(128), nullable=False),
        sa.Column("alert_type",    sa.String(32),  nullable=False),
        sa.Column("severity",      sa.String(16),  nullable=False),
        sa.Column("message",       sa.Text(),     nullable=False),
        sa.Column("old_grade",     sa.String(4),   nullable=True),
        sa.Column("new_grade",     sa.String(4),   nullable=True),
        sa.Column("stress_score",  sa.Float(),     nullable=False),
        sa.Column("triggered_at",  sa.DateTime(),  nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("is_dismissed",  sa.Boolean(),   nullable=False, server_default="false"),
    )
    op.create_index("ix_alert_borrower_id",  "alerts", ["borrower_id"])
    op.create_index("ix_alert_severity",     "alerts", ["severity"])
    op.create_index("ix_alert_triggered_at", "alerts", ["triggered_at"])

    # ── audit_logs immutability triggers ──────────────────────────────────────
    connection = op.get_bind()
    dialect = connection.dialect.name
    if dialect == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION prevent_audit_log_mod()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'Audit logs are immutable. UPDATE and DELETE operations are prohibited.';
            END;
            $$ LANGUAGE plpgsql;
        """)
        op.execute("""
            CREATE TRIGGER audit_log_immutable
            BEFORE UPDATE OR DELETE ON audit_logs
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_log_mod();
        """)
    elif dialect == "sqlite":
        op.execute("""
            CREATE TRIGGER audit_log_no_update
            BEFORE UPDATE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'Audit logs are immutable. UPDATE operations are prohibited.');
            END;
        """)
        op.execute("""
            CREATE TRIGGER audit_log_no_delete
            BEFORE DELETE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'Audit logs are immutable. DELETE operations are prohibited.');
            END;
        """)


def downgrade() -> None:
    connection = op.get_bind()
    dialect = connection.dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_log_immutable ON audit_logs;")
        op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_mod();")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS audit_log_no_update;")
        op.execute("DROP TRIGGER IF EXISTS audit_log_no_delete;")

    op.drop_table("alerts")
    op.drop_table("audit_logs")
    op.drop_table("monthly_snapshots")
    op.drop_table("explanations")
    op.drop_table("predictions")
    op.drop_table("borrower_profiles")
    op.drop_table("model_versions")
    op.drop_table("users")

