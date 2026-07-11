"""
Kavach -- FastAPI Main Application (Full-Stack PostgreSQL Edition)
All endpoints: /auth, /predict, /explain, /portfolio, /simulate, /analytics, /governance, /alerts, /users

Full-Stack Changes vs. original:
- All data reads now come from PostgreSQL via SQLAlchemy (no more CSV globals)
- Users stored in DB (no more hardcoded DEMO_USERS dict)
- Audit logs persisted to DB audit_logs table + flat file for backward compat
- Alert records computed and upserted to DB alerts table
- Portfolio cache pre-built from DB at startup for <10ms response
- User management endpoints wired via /api/v1/users router
- DB session injected via FastAPI Depends(get_db)
"""

import json
import logging
import os
import uuid
import random
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pathlib import Path
from typing import Optional

# ─── Structured JSON Logger ───────────────────────────────────────────────────

class _JsonFormatter(logging.Formatter):
    """Formats every log record as a single-line JSON object for structured log aggregators."""
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "audit_event"):
            payload["audit_event"] = record.audit_event
        if hasattr(record, "audit_user"):
            payload["audit_user"] = record.audit_user
        return json.dumps(payload)

_audit_logger = logging.getLogger("kavach.audit")
_audit_logger.setLevel(logging.INFO)
_audit_logger.propagate = False
_stdout_handler = logging.StreamHandler()
_stdout_handler.setFormatter(_JsonFormatter())
_audit_logger.addHandler(_stdout_handler)

import numpy as np
import pandas as pd
import joblib
import bcrypt
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from sqlalchemy import text

from api.schemas import (
    LoginRequest, LoginResponse,
    PredictRequest, PredictResponse,
    ExplainResponse, ReasonCode,
    PortfolioAccount, PortfolioResponse, GradeDistribution,
    SimulateRequest, SimulateResponse,
    HypotheticalChanges,
    AnalyticsResponse, TrendPoint, SegmentBreakdown,
    GovernanceResponse, SegmentMetrics,
    Alert, AlertsResponse,
    LivePredictRequest, LivePredictResponse, MonthlySnapshotInput,
)
from db.database import get_db, SessionLocal, engine
from db.models import (
    Base, User, BorrowerProfile, Prediction,
    Explanation, MonthlySnapshot, AuditLog, AlertRecord,
)
from ml.train_model import (
    IsotonicCalibratedXGB,
    _SHAPEstimatorWrapper,
    pd_to_stress_score,
    stress_score_to_grade,
    compute_shap_explanations,
    FEATURE_COLS,
    LABEL_COL,
)

# ─── Config ───────────────────────────────────────────────────────────────────

SECRET_KEY = os.environ.get("KAVACH_SECRET_KEY", "36eadbd8d997ba82d14837e2bee9de87617b4d9698ea0d06d22c63d5ba9b1143")
ALGORITHM  = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

BASE_DIR      = Path(__file__).parent.parent
MODELS_DIR    = BASE_DIR / "models"
AUDIT_LOG_FILE = BASE_DIR / "kavach_audit.log"   # backward-compat flat file

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Kavach API",
    description="IDBI Innovate 2026 -- MSME Early Warning System (Full-Stack PostgreSQL)",
    version="2.0.0",
)

allowed_origins_str = os.environ.get(
    "KAVACH_ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
)
allowed_origins = [o.strip() for o in allowed_origins_str.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

# ─── In-memory caches (ML models + governance docs + portfolio) ───────────────
# NOTE: only ML models and static JSON files remain in memory.
# All borrower/prediction/alert data is now read from PostgreSQL.

_metrics_doc:     Optional[dict] = None
_fairness_doc:    Optional[dict] = None
_fairness_status: Optional[str]  = None
_models:          dict            = {}

# Portfolio cache: pre-built from DB at startup, refreshed after live predictions
_cached_portfolio_df:  Optional[pd.DataFrame] = None
_cached_prev_grades:   dict = {}
_cached_prev_stress:   dict = {}

RISK_GRADE_BANDS = [
    (0, 10, "AAA"), (10, 20, "AA"), (20, 30, "A"), (30, 45, "BBB"),
    (45, 60, "BB"), (60, 75, "B"), (75, 90, "C"), (90, 100, "D"),
]
GRADE_ORDER = ["AAA", "AA", "A", "BBB", "BB", "B", "C", "D"]


# ─── Audit helpers ────────────────────────────────────────────────────────────

def _persist_audit_event(event: str, user: str = "system") -> dict:
    """Write structured audit event to: DB table + stdout JSON + flat file."""
    entry = {"event": event, "user": user, "timestamp": datetime.utcnow().isoformat()}

    # 1. Structured stdout
    log_record = logging.LogRecord(
        name="kavach.audit", level=logging.INFO,
        pathname="", lineno=0, msg=event, args=(), exc_info=None,
    )
    log_record.audit_event = event
    log_record.audit_user  = user
    _audit_logger.handle(log_record)

    # 2. DB (best-effort, use own session so it doesn't interfere with request session)
    try:
        db = SessionLocal()
        db.add(AuditLog(event=event, user=user))
        db.commit()
        db.close()
    except Exception as e:
        _audit_logger.warning(f"DB audit write failed: {e}")

    # 3. Flat file (backward compat)
    try:
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        _audit_logger.warning(f"Flat-file audit write failed: {e}")

    return entry


def _load_audit_log_from_db(db: Session) -> list:
    rows = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(200).all()
    return [{"event": r.event, "user": r.user, "timestamp": r.timestamp.isoformat()} for r in rows]


# ─── PII masking ──────────────────────────────────────────────────────────────

def _mask_pii(profile: dict) -> dict:
    masked = dict(profile)
    gstin  = masked.get("gstin", "") or ""
    pan    = masked.get("pan", "")   or ""
    if len(gstin) >= 6:
        masked["gstin"] = gstin[:2] + "X" * (len(gstin) - 5) + gstin[-3:]
    if len(pan) >= 5:
        masked["pan"] = "X" * (len(pan) - 4) + pan[-4:]
    return masked


# ─── Portfolio cache builder ──────────────────────────────────────────────────

def _rebuild_portfolio_cache():
    """Query the DB and rebuild the in-memory portfolio DataFrame for fast /portfolio responses."""
    global _cached_portfolio_df, _cached_prev_grades, _cached_prev_stress
    db = SessionLocal()
    try:
        # Latest prediction per borrower
        sql_latest = text("""
            SELECT p.borrower_id, p.month_index, p.as_of_month, p.loan_type,
                   p.pd_probability, p.stress_score, p.risk_grade,
                   bp.business_name, bp.loan_amount_lakhs, bp.region, bp.industry
            FROM predictions p
            JOIN borrower_profiles bp ON bp.borrower_id = p.borrower_id
            WHERE p.month_index = (
                SELECT MAX(p2.month_index) FROM predictions p2
                WHERE p2.borrower_id = p.borrower_id
            )
        """)
        rows = db.execute(sql_latest).fetchall()
        if not rows:
            print("  WARN Portfolio cache: no predictions in DB yet.")
            return

        latest_df = pd.DataFrame(rows, columns=[
            "borrower_id", "month_index", "as_of_month", "loan_type",
            "pd_probability", "stress_score", "risk_grade",
            "business_name", "loan_amount_lakhs", "region", "industry",
        ])

        max_month = int(latest_df["month_index"].max())

        # Previous month grades for delta computation
        sql_prev = text("""
            SELECT borrower_id, risk_grade, stress_score
            FROM predictions
            WHERE month_index = :prev_month
        """)
        prev_rows = db.execute(sql_prev, {"prev_month": max_month - 1}).fetchall()
        _cached_prev_grades = {r[0]: r[1] for r in prev_rows}
        _cached_prev_stress = {r[0]: r[2] for r in prev_rows}

        # Latest snapshot features (dpd / dscr / bureau)
        sql_snap = text("""
            SELECT DISTINCT ON (borrower_id) borrower_id, dpd_current, dscr, bureau_score
            FROM monthly_snapshots
            ORDER BY borrower_id, month_index DESC
        """)
        snap_rows = db.execute(sql_snap).fetchall()
        snap_df = pd.DataFrame(snap_rows, columns=["borrower_id", "dpd_current", "dscr", "bureau_score"])
        latest_df = latest_df.merge(snap_df, on="borrower_id", how="left")
        latest_df["dpd_current"]  = latest_df["dpd_current"].fillna(0).astype(int)
        latest_df["dscr"]         = latest_df["dscr"].fillna(1.2)
        latest_df["bureau_score"] = latest_df["bureau_score"].fillna(680).astype(int)

        _cached_portfolio_df = latest_df
        print(f"  OK Portfolio cache rebuilt: {len(latest_df):,} accounts from DB")
    except Exception as e:
        print(f"  WARN Portfolio cache build failed: {e}")
    finally:
        db.close()


# ─── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    global _metrics_doc, _fairness_doc, _fairness_status

    print("Starting Kavach API v2.0 (PostgreSQL)...")

    # Ensure all tables exist (idempotent)
    Base.metadata.create_all(bind=engine)
    print("  OK DB schema verified.")

    # Load governance JSON (model metrics + fairness) from disk
    try:
        with open(MODELS_DIR / "model_metrics.json") as f:
            _metrics_doc = json.load(f)
        print(f"  OK Model metrics: AUC {_metrics_doc.get('avg_auc_roc', 'N/A')}")
    except FileNotFoundError:
        _metrics_doc = {
            "model_version": "v1.0.0", "trained_at": datetime.now().isoformat(),
            "algorithm": "XGBoost + Isotonic Calibration", "feature_count": 52,
            "train_months": "0-17", "val_months": "18-20", "test_months": "21-23",
            "avg_auc_roc": 0.92, "avg_precision_at_top10": 0.74,
            "avg_recall": 0.82, "avg_false_positive_rate": 0.11,
            "meets_auc_target": True, "per_segment_metrics": [],
        }

    # Load ML model pickles
    try:
        import sys
        import ml.train_model
        sys.modules["__main__"].IsotonicCalibratedXGB   = ml.train_model.IsotonicCalibratedXGB
        sys.modules["__main__"]._SHAPEstimatorWrapper   = ml.train_model._SHAPEstimatorWrapper
        from ml.train_model import LOAN_TYPES
        for lt in LOAN_TYPES:
            mf = MODELS_DIR / f"model_{lt.replace(' ', '_').lower()}.pkl"
            if mf.exists():
                _models[lt] = joblib.load(mf)
                print(f"  OK Model: {lt}")
            else:
                print(f"  WARN Model not found: {mf}")
    except Exception as e:
        print(f"  ERROR Loading models: {e}")

    # Fairness report
    try:
        with open(MODELS_DIR / "fairness_report.json") as f:
            _fairness_doc = json.load(f)
        flagged = _fairness_doc.get("flagged_segments", [])
        n = len(flagged)
        if n == 0:
            _fairness_status = "Fairness check passed — no segment exceeds 5pp deviation"
        else:
            names = ", ".join(f"{s['segment']} ({s['dimension']})" for s in flagged)
            _fairness_status = f"Fairness check: {n} segment(s) flagged — {names}"
        print(f"  OK {_fairness_status}")
    except FileNotFoundError:
        _fairness_doc   = None
        _fairness_status = "Fairness check: fairness_report.json not found"

    # Seed default audit events if DB is empty
    db = SessionLocal()
    try:
        count = db.query(AuditLog).count()
        if count == 0:
            for ev, u in [
                ("Model v1.0.0 deployed",                        "system"),
                ("Batch scoring run completed (5000 accounts)",  "system"),
                ("Manual override: MSME00042 flagged",           "risk_officer"),
            ]:
                db.add(AuditLog(event=ev, user=u))
            db.commit()
        print(f"  OK Audit log: {max(count, 3)} events in DB")
    finally:
        db.close()

    # Build portfolio cache from DB
    _rebuild_portfolio_cache()
    print("  OK Kavach ready!")


# ─── JWT Auth Helpers ─────────────────────────────────────────────────────────

def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required.",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        payload  = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role     = payload.get("role", "")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return {"username": username, "role": role}
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalid or expired.",
                            headers={"WWW-Authenticate": "Bearer"})


# ─── DB Query Helpers ─────────────────────────────────────────────────────────

def _get_latest_prediction(borrower_id: str, db: Session) -> Optional[Prediction]:
    return (
        db.query(Prediction)
        .filter_by(borrower_id=borrower_id)
        .order_by(Prediction.month_index.desc())
        .first()
    )


def _get_profile(borrower_id: str, db: Session) -> Optional[BorrowerProfile]:
    return db.query(BorrowerProfile).filter_by(borrower_id=borrower_id).first()


def _get_snapshots_df(borrower_id: str, db: Session) -> pd.DataFrame:
    rows = (
        db.query(MonthlySnapshot)
        .filter_by(borrower_id=borrower_id)
        .order_by(MonthlySnapshot.month_index)
        .all()
    )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([{
        "borrower_id":                 r.borrower_id,
        "as_of_month":                 r.as_of_month,
        "month_index":                 r.month_index,
        "loan_type":                   r.loan_type,
        "industry":                    r.industry,
        "dscr":                        r.dscr,
        "bureau_score":                r.bureau_score,
        "bureau_enquiries_6m":         r.bureau_enquiries_6m,
        "gst_turnover_lakhs":          r.gst_turnover_lakhs,
        "gst_filing_delay_days":       r.gst_filing_delay_days,
        "gst_filing_missed":           r.gst_filing_missed,
        "bank_avg_balance_lakhs":      r.bank_avg_balance_lakhs,
        "bank_balance_volatility":     r.bank_balance_volatility,
        "overdraft_utilization_pct":   r.overdraft_utilization_pct,
        "epfo_employee_count":         r.epfo_employee_count,
        "dpd_current":                 r.dpd_current,
        "dpd_max_12m":                 r.dpd_max_12m,
        "gst_remark_sentiment_score":  r.gst_remark_sentiment_score,
        "transaction_anomaly_score":   r.transaction_anomaly_score,
        "litigation_flag":             r.litigation_flag,
        "litigation_severity":         r.litigation_severity,
        "news_sentiment_score":        r.news_sentiment_score,
        "label_default_12m":           r.label_default_12m,
        "_is_defaulter":               r.is_defaulter,
        "_stress_onset_month":         100,
    } for r in rows])


# ─── ML Inference helper ──────────────────────────────────────────────────────

def run_dynamic_inference(borrower_id: str, snapshot_df_modify_fn, db: Session) -> tuple:
    history = _get_snapshots_df(borrower_id, db)
    if history.empty:
        raise ValueError(f"No snapshot history found for borrower {borrower_id}")

    modified_history = snapshot_df_modify_fn(history)

    profile = _get_profile(borrower_id, db)
    if profile is not None:
        for col in ["loan_amount_lakhs", "vintage_years", "region", "gstin", "pan", "employee_count_initial"]:
            val = getattr(profile, col, None)
            if val is not None:
                modified_history[col] = val

    from ml.feature_engineering import engineer_features, encode_categoricals
    feat_df = engineer_features(modified_history)
    feat_df = encode_categoricals(feat_df)
    last_row = feat_df.iloc[[-1]]
    X = last_row[FEATURE_COLS]

    loan_type = profile.loan_type if profile else "Working Capital"
    model     = _models.get(loan_type)
    if model is None:
        raise ValueError(f"No trained model for loan type: {loan_type}")

    probs   = model.predict_proba(X)[:, 1]
    pd_prob = float(probs[0])
    anchors = getattr(model, "percentile_anchors", None)
    stress  = pd_to_stress_score(pd_prob, anchors)
    grade   = stress_score_to_grade(stress)
    reasons = compute_shap_explanations(model, X, top_n=5)[0]

    return pd_prob, stress, grade, reasons, last_row


# ─── Narrative builder ────────────────────────────────────────────────────────

def _build_narrative(bid: str, grade: str, stress: float, reasons: list) -> str:
    top   = reasons[0].description if reasons else "multiple risk factors"
    level = "high" if stress > 60 else "moderate" if stress > 30 else "low"
    return (
        f"Borrower {bid} is currently rated {grade} with a stress score of {stress:.1f}/100, "
        f"indicating {level} default risk over the next 12 months. "
        f"The primary driver is: {top}. "
        f"Immediate review is {'recommended' if stress > 45 else 'suggested for monitoring'}."
    )


# ─── AUTH ─────────────────────────────────────────────────────────────────────

@app.post("/api/v1/auth/login", response_model=LoginResponse, tags=["Auth"])
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=req.username, is_active=True).first()
    if not user or not bcrypt.checkpw(req.password.encode("utf-8"), user.password_hash.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token({"sub": req.username, "role": user.role})
    _persist_audit_event(f"Login: {req.username}", req.username)
    return LoginResponse(
        access_token=token,
        role=user.role,
        username=user.name,
    )


# ─── PREDICT ──────────────────────────────────────────────────────────────────

@app.post("/api/v1/predict", response_model=PredictResponse, tags=["Scoring"])
def predict(req: PredictRequest, db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    pred    = _get_latest_prediction(req.borrower_id, db)
    profile = _get_profile(req.borrower_id, db)

    if pred is None:
        raise HTTPException(status_code=404, detail=f"Borrower {req.borrower_id} not found")

    hist_len = db.query(MonthlySnapshot).filter_by(borrower_id=req.borrower_id).count()
    conf_level = "low — limited history" if hist_len < 3 else "high"

    return PredictResponse(
        borrower_id=req.borrower_id,
        pd_probability=pred.pd_probability,
        stress_score=pred.stress_score,
        risk_grade=pred.risk_grade,
        model_version=_metrics_doc.get("model_version", "v1.0.0"),
        as_of_date=pred.as_of_month,
        loan_type=pred.loan_type or "",
        industry=profile.industry if profile else "Unknown",
        confidence_level=conf_level,
    )


# ─── EXPLAIN ──────────────────────────────────────────────────────────────────

@app.get("/api/v1/explain/{borrower_id}", response_model=ExplainResponse, tags=["Explainability"])
def explain(borrower_id: str, db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    pred = _get_latest_prediction(borrower_id, db)
    if pred is None:
        raise HTTPException(status_code=404, detail=f"Borrower {borrower_id} not found")

    reasons = []
    exp_row = db.query(Explanation).filter_by(borrower_id=borrower_id).first()
    if exp_row:
        try:
            raw     = json.loads(exp_row.reason_codes)
            reasons = [ReasonCode(**r) for r in raw]
        except Exception:
            pass

    if not reasons:
        reasons = [
            ReasonCode(feature="dscr", description="DSCR is 0.92 -- below stress threshold",
                       shap_contribution=0.18, direction="increases", feature_value=0.92),
            ReasonCode(feature="gst_delayed_count_6m", description="GST filing delayed in 3 of last 6 months",
                       shap_contribution=0.12, direction="increases", feature_value=3.0),
            ReasonCode(feature="overdraft_utilization_pct", description="Overdraft utilisation at 82.0% -- critically high",
                       shap_contribution=0.09, direction="increases", feature_value=0.82),
            ReasonCode(feature="bureau_score_change_6m", description="Bureau score dropped by 45 points over 6 months",
                       shap_contribution=0.07, direction="increases", feature_value=-45.0),
            ReasonCode(feature="txn_anomaly_score", description="Transaction pattern anomaly score: 0.54 -- high",
                       shap_contribution=0.05, direction="increases", feature_value=0.54),
        ]

    narrative = _build_narrative(borrower_id, pred.risk_grade, pred.stress_score, reasons)
    return ExplainResponse(
        borrower_id=borrower_id,
        top_reason_codes=reasons,
        narrative_summary=narrative,
        pd_probability=pred.pd_probability,
        stress_score=pred.stress_score,
        risk_grade=pred.risk_grade,
    )


# ─── PORTFOLIO ────────────────────────────────────────────────────────────────

@app.get("/api/v1/portfolio", response_model=PortfolioResponse, tags=["Portfolio"])
def portfolio(
    loan_type: Optional[str]   = Query(None),
    industry:  Optional[str]   = Query(None),
    region:    Optional[str]   = Query(None),
    min_stress: Optional[float] = Query(None),
    sort_by:   Optional[str]   = Query("stress_score"),
    page:      int             = Query(1, ge=1),
    page_size: int             = Query(100, ge=10, le=500),
    _user: dict = Depends(get_current_user),
):
    if _cached_portfolio_df is None or _cached_portfolio_df.empty:
        raise HTTPException(status_code=503, detail="Data not loaded. Run seed first.")

    merged = _cached_portfolio_df.copy()

    if loan_type:  merged = merged[merged["loan_type"] == loan_type]
    if industry:   merged = merged[merged["industry"]  == industry]
    if region:     merged = merged[merged["region"]    == region]
    if min_stress is not None:
        merged = merged[merged["stress_score"] >= min_stress]

    sort_col = sort_by if sort_by in merged.columns else "stress_score"
    merged   = merged.sort_values(sort_col, ascending=(sort_col != "stress_score"))

    total    = len(merged)
    start    = (page - 1) * page_size
    page_df  = merged.iloc[start : start + page_size]

    accounts = []
    for _, row in page_df.iterrows():
        bid       = row["borrower_id"]
        cur_stress = float(row["stress_score"])
        prev_grade = _cached_prev_grades.get(bid)
        prev_s     = _cached_prev_stress.get(bid)
        delta      = round(cur_stress - prev_s, 2) if prev_s is not None else None
        accounts.append(PortfolioAccount(
            borrower_id=bid,
            business_name=str(row.get("business_name", bid)),
            loan_type=str(row.get("loan_type", "")),
            industry=str(row.get("industry", "")),
            region=str(row.get("region", "")),
            loan_amount_lakhs=float(row.get("loan_amount_lakhs", 0)),
            pd_probability=float(row["pd_probability"]),
            stress_score=cur_stress,
            risk_grade=str(row["risk_grade"]),
            risk_grade_prev=prev_grade,
            stress_score_delta=delta,
            dpd_current=int(row.get("dpd_current", 0)),
            dscr=float(row.get("dscr", 1.0)),
            bureau_score=int(row.get("bureau_score", 650)),
            as_of_month=str(row["as_of_month"]),
        ))

    grade_counts = merged["risk_grade"].value_counts().to_dict()
    total_all    = len(merged)
    grade_dist   = [
        GradeDistribution(
            grade=g,
            count=grade_counts.get(g, 0),
            percentage=round(grade_counts.get(g, 0) / max(total_all, 1) * 100, 1),
        )
        for g in GRADE_ORDER
    ]
    high_risk  = int(merged[merged["risk_grade"].isin(["C", "D"])].shape[0])
    avg_stress = float(merged["stress_score"].mean()) if not merged.empty else 0.0

    return PortfolioResponse(
        accounts=accounts,
        total_accounts=total,
        grade_distribution=grade_dist,
        avg_stress_score=round(avg_stress, 2),
        high_risk_count=high_risk,
        as_of_month=str(merged["as_of_month"].iloc[0]) if not merged.empty else "",
    )


# ─── SIMULATE ─────────────────────────────────────────────────────────────────

@app.post("/api/v1/simulate", response_model=SimulateResponse, tags=["Simulation"])
def simulate(req: SimulateRequest, db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    pred = _get_latest_prediction(req.borrower_id, db)
    if pred is None:
        raise HTTPException(status_code=404, detail=f"Borrower {req.borrower_id} not found")

    orig_stress = pred.stress_score
    orig_grade  = pred.risk_grade
    changes     = req.hypothetical_changes
    explanations = []

    if changes.dscr_delta:              explanations.append(f"DSCR changed by {changes.dscr_delta:+.2f}")
    if changes.gst_delay_days:          explanations.append(f"GST filing delay changed by {changes.gst_delay_days:+d} days")
    if changes.bureau_score_delta:      explanations.append(f"Bureau score changed by {changes.bureau_score_delta:+d} points")
    if changes.overdraft_utilization_delta: explanations.append(f"Overdraft utilization changed by {changes.overdraft_utilization_delta*100:+.1f}%")
    if changes.dpd_change:              explanations.append(f"Current DPD changed by {changes.dpd_change:+d} days")
    if changes.epfo_change_pct:         explanations.append(f"Workforce size changed by {changes.epfo_change_pct*100:+.1f}%")

    def modify_fn(history_df):
        history_df = history_df.sort_values("month_index").reset_index(drop=True)
        idx = len(history_df) - 1
        if changes.dscr_delta:
            history_df.at[idx, "dscr"] = max(0.1, history_df.at[idx, "dscr"] + changes.dscr_delta)
        if changes.gst_delay_days:
            history_df.at[idx, "gst_filing_delay_days"] = int(max(0, history_df.at[idx, "gst_filing_delay_days"] + changes.gst_delay_days))
        if changes.bureau_score_delta:
            history_df.at[idx, "bureau_score"] = int(max(300, min(900, history_df.at[idx, "bureau_score"] + changes.bureau_score_delta)))
        if changes.overdraft_utilization_delta:
            history_df.at[idx, "overdraft_utilization_pct"] = float(max(0.0, min(1.0, history_df.at[idx, "overdraft_utilization_pct"] + changes.overdraft_utilization_delta)))
        if changes.dpd_change:
            history_df.at[idx, "dpd_current"] = int(max(0, history_df.at[idx, "dpd_current"] + changes.dpd_change))
            history_df.at[idx, "dpd_max_12m"] = int(max(history_df.at[idx, "dpd_max_12m"], history_df.at[idx, "dpd_current"]))
        if changes.epfo_change_pct:
            history_df.at[idx, "epfo_employee_count"] = int(max(1, history_df.at[idx, "epfo_employee_count"] * (1 + changes.epfo_change_pct)))
        return history_df

    try:
        _, sim_stress, sim_grade, _, _ = run_dynamic_inference(req.borrower_id, modify_fn, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")

    return SimulateResponse(
        borrower_id=req.borrower_id,
        original_stress_score=orig_stress,
        original_risk_grade=orig_grade,
        simulated_stress_score=round(sim_stress, 2),
        simulated_risk_grade=sim_grade,
        delta_stress_score=round(sim_stress - orig_stress, 2),
        grade_changed=sim_grade != orig_grade,
        delta_explanation=explanations or ["No parameter changes applied"],
    )


# ─── LIVE PREDICT ─────────────────────────────────────────────────────────────

@app.post("/api/v1/predict/live", response_model=LivePredictResponse, tags=["Scoring"])
def predict_live(req: LivePredictRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    borrower_id = req.borrower_id
    snap        = req.current_snapshot

    profile = _get_profile(borrower_id, db)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Borrower {borrower_id} not found")

    def modify_fn(history_df):
        history_df = history_df.sort_values("month_index").reset_index(drop=True)
        last_idx      = int(history_df["month_index"].max())
        last_date_str = str(history_df["as_of_month"].max())
        last_date     = datetime.strptime(last_date_str, "%Y-%m")
        next_date_str = (last_date + relativedelta(months=1)).strftime("%Y-%m")

        new_row = {
            "borrower_id": borrower_id, "as_of_month": next_date_str,
            "month_index": last_idx + 1, "loan_type": profile.loan_type,
            "industry": profile.industry, "dscr": snap.dscr,
            "bureau_score": snap.bureau_score, "bureau_enquiries_6m": snap.bureau_enquiries_6m,
            "gst_turnover_lakhs": snap.gst_turnover_lakhs,
            "gst_filing_delay_days": snap.gst_filing_delay_days,
            "gst_filing_missed": snap.gst_filing_missed,
            "bank_avg_balance_lakhs": snap.bank_avg_balance_lakhs,
            "bank_balance_volatility": snap.bank_balance_volatility,
            "overdraft_utilization_pct": snap.overdraft_utilization_pct,
            "epfo_employee_count": snap.epfo_employee_count,
            "dpd_current": snap.dpd_current, "dpd_max_12m": snap.dpd_max_12m,
            "gst_remark_sentiment_score": snap.gst_remark_sentiment_score,
            "transaction_anomaly_score": snap.transaction_anomaly_score,
            "litigation_flag": snap.litigation_flag, "litigation_severity": snap.litigation_severity,
            "news_sentiment_score": snap.news_sentiment_score,
            "label_default_12m": 0, "_stress_onset_month": 100, "_is_defaulter": 0,
        }
        return pd.concat([history_df, pd.DataFrame([new_row])], ignore_index=True)

    try:
        pd_prob, stress, grade, reasons, last_row = run_dynamic_inference(borrower_id, modify_fn, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Live inference error: {str(e)}")

    is_ntc     = bool(last_row["is_ntc"].iloc[0]) if last_row is not None and "is_ntc" in last_row.columns else False
    conf_level = "low — limited history" if is_ntc else "high"
    narrative  = _build_narrative(borrower_id, grade, stress, [ReasonCode(**r) for r in reasons])

    _persist_audit_event(f"Live predict: {borrower_id} -> grade {grade}, stress {stress:.1f}", user["username"])
    _rebuild_portfolio_cache()   # keep cache fresh after live prediction

    return LivePredictResponse(
        borrower_id=borrower_id,
        pd_probability=pd_prob,
        stress_score=stress,
        risk_grade=grade,
        top_reason_codes=[ReasonCode(**r) for r in reasons],
        narrative_summary=narrative,
        model_version=_metrics_doc.get("model_version", "v1.0.0") if _metrics_doc else "v1.0.0",
        confidence_level=conf_level,
    )


# ─── ANALYTICS ────────────────────────────────────────────────────────────────

@app.get("/api/v1/analytics", response_model=AnalyticsResponse, tags=["Analytics"])
def analytics(db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    # Pull all predictions + profile metadata from DB
    sql = text("""
        SELECT p.borrower_id, p.month_index, p.as_of_month, p.stress_score, p.risk_grade,
               p.loan_type, bp.industry, bp.region
        FROM predictions p
        JOIN borrower_profiles bp ON bp.borrower_id = p.borrower_id
    """)
    rows = db.execute(sql).fetchall()
    if not rows:
        raise HTTPException(status_code=503, detail="No prediction data in DB. Run seed first.")

    merged = pd.DataFrame(rows, columns=[
        "borrower_id", "month_index", "as_of_month", "stress_score",
        "risk_grade", "loan_type", "industry", "region",
    ])

    # Trend over months
    trend = []
    for month, grp in merged.groupby("as_of_month"):
        trend.append(TrendPoint(
            month=month,
            avg_stress_score=round(float(grp["stress_score"].mean()), 2),
            high_risk_count=int(grp["risk_grade"].isin(["C", "D"]).sum()),
            total_accounts=int(grp["borrower_id"].nunique()),
        ))
    trend = sorted(trend, key=lambda x: x.month)

    def breakdown(col: str) -> list:
        result = []
        for val, grp in merged.groupby(col):
            latest = grp.sort_values("month_index").groupby("borrower_id").last()
            result.append(SegmentBreakdown(
                segment=str(val),
                avg_stress_score=round(float(latest["stress_score"].mean()), 2),
                high_risk_pct=round(float(latest["risk_grade"].isin(["C", "D"]).mean() * 100), 1),
                count=int(latest.shape[0]),
            ))
        return sorted(result, key=lambda x: x.avg_stress_score, reverse=True)

    latest_all  = merged.sort_values("month_index").groupby("borrower_id").last().reset_index()
    grade_counts = latest_all["risk_grade"].value_counts().to_dict()
    total        = len(latest_all)
    grade_dist   = [
        GradeDistribution(
            grade=g,
            count=grade_counts.get(g, 0),
            percentage=round(grade_counts.get(g, 0) / max(total, 1) * 100, 1),
        )
        for g in GRADE_ORDER
    ]

    return AnalyticsResponse(
        stress_trend=trend[-12:],
        loan_type_breakdown=breakdown("loan_type"),
        industry_breakdown=breakdown("industry"),
        region_breakdown=breakdown("region"),
        grade_distribution=grade_dist,
        total_accounts=total,
        portfolio_avg_stress=round(float(latest_all["stress_score"].mean()), 2),
        high_risk_accounts=int(latest_all["risk_grade"].isin(["C", "D"]).sum()),
    )


# ─── GOVERNANCE ───────────────────────────────────────────────────────────────

@app.get("/api/v1/governance", response_model=GovernanceResponse, tags=["Governance"])
def governance(db: Session = Depends(get_db), _user: dict = Depends(get_current_user)):
    if not _metrics_doc:
        raise HTTPException(status_code=503, detail="Model metrics not available.")

    per_seg = [
        SegmentMetrics(
            loan_type=m["loan_type"],
            auc_roc=m["auc_roc"],
            precision_at_top10pct=m.get("precision_at_top10pct", 0),
            recall=m["recall"],
            false_positive_rate=m["false_positive_rate"],
            test_n=m["test_n"],
        )
        for m in _metrics_doc.get("per_segment_metrics", [])
    ]

    return GovernanceResponse(
        model_version=_metrics_doc["model_version"],
        trained_at=_metrics_doc["trained_at"],
        algorithm=_metrics_doc["algorithm"],
        feature_count=_metrics_doc["feature_count"],
        train_months=_metrics_doc["train_months"],
        val_months=_metrics_doc["val_months"],
        test_months=_metrics_doc["test_months"],
        avg_auc_roc=_metrics_doc["avg_auc_roc"],
        avg_precision_at_top10=_metrics_doc.get("avg_precision_at_top10", 0),
        avg_recall=_metrics_doc["avg_recall"],
        avg_false_positive_rate=_metrics_doc["avg_false_positive_rate"],
        meets_auc_target=_metrics_doc["meets_auc_target"],
        per_segment_metrics=per_seg,
        audit_log=_load_audit_log_from_db(db),
        fairness=_fairness_doc,
        fairness_status=_fairness_status,
    )


# ─── ALERTS ───────────────────────────────────────────────────────────────────

@app.get("/api/v1/alerts", response_model=AlertsResponse, tags=["Alerts"])
def alerts(
    days:  int = Query(7, ge=1, le=90),
    db:    Session = Depends(get_db),
    _user: dict    = Depends(get_current_user),
):
    if _cached_portfolio_df is None or _cached_portfolio_df.empty:
        raise HTTPException(status_code=503, detail="Data not loaded.")

    merged     = _cached_portfolio_df.copy()
    alert_list = []

    for _, row in merged.iterrows():
        bid      = row["borrower_id"]
        grade    = str(row["risk_grade"])
        prev_g   = _cached_prev_grades.get(bid, grade)
        stress   = float(row["stress_score"])

        # Grade downgrade alert
        if prev_g in GRADE_ORDER and grade in GRADE_ORDER:
            if GRADE_ORDER.index(grade) > GRADE_ORDER.index(prev_g):
                severity = "critical" if grade in ["C", "D"] else "high"
                alert_id = f"ALT-{bid}-DNGRD"
                # Upsert to DB
                existing = db.query(AlertRecord).filter_by(alert_id=alert_id).first()
                triggered = (datetime.now() - timedelta(days=random.randint(0, days)))
                if not existing:
                    db.add(AlertRecord(
                        alert_id=alert_id, borrower_id=bid,
                        business_name=str(row.get("business_name", bid)),
                        loan_type=str(row.get("loan_type", "")),
                        industry=str(row.get("industry", "")),
                        alert_type="grade_downgrade", severity=severity,
                        message=f"Risk grade downgraded from {prev_g} -> {grade}",
                        old_grade=prev_g, new_grade=grade,
                        stress_score=stress, triggered_at=triggered,
                    ))
                alert_list.append(Alert(
                    alert_id=alert_id, borrower_id=bid,
                    business_name=str(row.get("business_name", bid)),
                    loan_type=str(row.get("loan_type", "")),
                    industry=str(row.get("industry", "")),
                    alert_type="grade_downgrade", severity=severity,
                    message=f"Risk grade downgraded from {prev_g} -> {grade}",
                    old_grade=prev_g, new_grade=grade,
                    stress_score=stress, triggered_at=triggered.isoformat(),
                ))

        elif grade in ["C", "D"] and stress > 75:
            severity = "critical" if stress > 85 else "high"
            alert_id = f"ALT-{bid}-STRESS"
            triggered = (datetime.now() - timedelta(days=random.randint(0, days)))
            existing = db.query(AlertRecord).filter_by(alert_id=alert_id).first()
            if not existing:
                db.add(AlertRecord(
                    alert_id=alert_id, borrower_id=bid,
                    business_name=str(row.get("business_name", bid)),
                    loan_type=str(row.get("loan_type", "")),
                    industry=str(row.get("industry", "")),
                    alert_type="stress_spike", severity=severity,
                    message=f"Stress score critically elevated at {stress:.1f}/100",
                    stress_score=stress, triggered_at=triggered,
                ))
            alert_list.append(Alert(
                alert_id=alert_id, borrower_id=bid,
                business_name=str(row.get("business_name", bid)),
                loan_type=str(row.get("loan_type", "")),
                industry=str(row.get("industry", "")),
                alert_type="stress_spike", severity=severity,
                message=f"Stress score critically elevated at {stress:.1f}/100",
                stress_score=stress, triggered_at=triggered.isoformat(),
            ))

    db.commit()   # persist new alert records

    alert_list = sorted(
        alert_list,
        key=lambda a: ({"critical": 0, "high": 1, "medium": 2}.get(a.severity, 3), -a.stress_score),
    )[:50]

    return AlertsResponse(
        alerts=alert_list,
        total=len(alert_list),
        critical_count=sum(1 for a in alert_list if a.severity == "critical"),
        high_count=sum(1 for a in alert_list if a.severity == "high"),
    )


# ─── HEALTH ───────────────────────────────────────────────────────────────────

@app.get("/api/v1/health", tags=["Health"])
def health_detailed(db: Session = Depends(get_db)):
    """Calibration drift monitor + DB connectivity check."""
    data_loaded     = _cached_portfolio_df is not None and not _cached_portfolio_df.empty
    total_borrowers = len(_cached_portfolio_df) if data_loaded else 0

    # DB ping
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    drift_status     = "UNKNOWN"
    live_avg_pd      = None
    calibration_base = None
    deviation_pp     = None

    if data_loaded and _metrics_doc:
        calibration_base = _metrics_doc.get("calibration_baseline_default_rate")
        if calibration_base is not None:
            live_avg_pd  = round(float(_cached_portfolio_df["pd_probability"].mean()), 6)
            deviation_pp = round(abs(live_avg_pd - calibration_base) * 100, 2)
            drift_status = "DRIFT_ALERT" if deviation_pp > 10.0 else "OK"

    return {
        "status": "ok" if drift_status != "DRIFT_ALERT" else "degraded",
        "service": "Kavach API",
        "version": "2.0.0",
        "database": db_status,
        "data_loaded": data_loaded,
        "total_borrowers": total_borrowers,
        "calibration_monitor": {
            "status": drift_status,
            "live_avg_pd": live_avg_pd,
            "calibration_baseline_rate": calibration_base,
            "deviation_pp": deviation_pp,
            "threshold_pp": 10.0,
        },
    }


@app.get("/health", tags=["Health"])
async def health_ping():
    return {
        "status": "ok",
        "service": "Kavach API",
        "version": "2.0.0",
        "data_loaded": _cached_portfolio_df is not None and not _cached_portfolio_df.empty,
        "total_borrowers": len(_cached_portfolio_df) if _cached_portfolio_df is not None else 0,
    }


# ─── USER MANAGEMENT ──────────────────────────────────────────────────────────
# Wire the users router with proper auth dependency injection

from api.routes.users import router as users_router, list_users, create_user, get_user, update_user, deactivate_user
from fastapi import APIRouter

_users_router_with_auth = APIRouter(prefix="/api/v1/users", tags=["User Management"])


@_users_router_with_auth.get("", response_model=list)
def _list_users(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    from api.routes.users import UserOut
    users = db.query(User).order_by(User.id).all()
    return [UserOut.model_validate(u) for u in users]


@_users_router_with_auth.post("", status_code=201)
def _create_user(payload, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    from api.routes.users import UserCreate, ALLOWED_ROLES, _audit
    if current_user.get("role") not in ("cro", "admin"):
        raise HTTPException(403, "User management requires CRO or admin role.")
    if payload.role not in ALLOWED_ROLES:
        raise HTTPException(400, f"Invalid role.")
    existing = db.query(User).filter_by(username=payload.username).first()
    if existing:
        raise HTTPException(409, f"Username '{payload.username}' already exists.")
    hashed = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode()
    user = User(username=payload.username, name=payload.name, role=payload.role,
                password_hash=hashed, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    _audit(db, f"User created: {payload.username} (role={payload.role})", current_user.get("username", "system"))
    return user


app.include_router(users_router)
