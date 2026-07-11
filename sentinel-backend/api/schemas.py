"""
Kavach -- Pydantic Schemas for FastAPI
All request/response models for /predict, /explain, /portfolio, /simulate, /analytics, /governance
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ─── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str
    role: str  # "risk_officer" | "rm" | "cro" | "compliance"


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    expires_in: int = 86400


# ─── Predict ──────────────────────────────────────────────────────────────────

class PredictRequest(BaseModel):
    borrower_id: str
    loan_type: Optional[str] = None
    as_of_date: Optional[str] = None


class PredictResponse(BaseModel):
    borrower_id: str
    pd_probability: float = Field(..., description="Probability of Default 0-1")
    stress_score: float = Field(..., description="Stress Score 0-100")
    risk_grade: str = Field(..., description="AAA to D")
    model_version: str
    as_of_date: str
    loan_type: str
    industry: str
    confidence_level: Optional[str] = "high"



# ─── Explain ──────────────────────────────────────────────────────────────────

class ReasonCode(BaseModel):
    feature: str
    description: str
    shap_contribution: float
    direction: str  # "increases" | "decreases"
    feature_value: float


class ExplainResponse(BaseModel):
    borrower_id: str
    top_reason_codes: List[ReasonCode]
    narrative_summary: str
    pd_probability: float
    stress_score: float
    risk_grade: str


# ─── Portfolio ────────────────────────────────────────────────────────────────

class PortfolioAccount(BaseModel):
    borrower_id: str
    business_name: str
    loan_type: str
    industry: str
    region: str
    loan_amount_lakhs: float
    pd_probability: float
    stress_score: float
    risk_grade: str
    risk_grade_prev: Optional[str] = None
    stress_score_delta: Optional[float] = None
    dpd_current: int
    dscr: float
    bureau_score: int
    as_of_month: str


class GradeDistribution(BaseModel):
    grade: str
    count: int
    percentage: float


class PortfolioResponse(BaseModel):
    accounts: List[PortfolioAccount]
    total_accounts: int
    grade_distribution: List[GradeDistribution]
    avg_stress_score: float
    high_risk_count: int  # grade C or D
    as_of_month: str


# ─── Simulate ─────────────────────────────────────────────────────────────────

class HypotheticalChanges(BaseModel):
    dscr_delta: Optional[float] = Field(0.0, ge=-20.0, le=20.0, description="Hypothetical change in DSCR")
    gst_delay_days: Optional[int] = Field(0, ge=-365, le=365, description="Hypothetical change in GST filing delay days")
    bureau_score_delta: Optional[int] = Field(0, ge=-600, le=600, description="Hypothetical change in Bureau score")
    overdraft_utilization_delta: Optional[float] = Field(0.0, ge=-1.0, le=1.0, description="Hypothetical change in OD utilization")
    dpd_change: Optional[int] = Field(0, ge=-999, le=999, description="Hypothetical change in current DPD")
    epfo_change_pct: Optional[float] = Field(0.0, ge=-1.0, le=10.0, description="Hypothetical change in workforce percentage")


class SimulateRequest(BaseModel):
    borrower_id: str
    hypothetical_changes: HypotheticalChanges


class SimulateResponse(BaseModel):
    borrower_id: str
    original_stress_score: float
    original_risk_grade: str
    simulated_stress_score: float
    simulated_risk_grade: str
    delta_stress_score: float
    grade_changed: bool
    delta_explanation: List[str]


# ─── Analytics (CRO) ──────────────────────────────────────────────────────────

class TrendPoint(BaseModel):
    month: str
    avg_stress_score: float
    high_risk_count: int
    total_accounts: int


class SegmentBreakdown(BaseModel):
    segment: str
    avg_stress_score: float
    high_risk_pct: float
    count: int


class AnalyticsResponse(BaseModel):
    stress_trend: List[TrendPoint]
    loan_type_breakdown: List[SegmentBreakdown]
    industry_breakdown: List[SegmentBreakdown]
    region_breakdown: List[SegmentBreakdown]
    grade_distribution: List[GradeDistribution]
    total_accounts: int
    portfolio_avg_stress: float
    high_risk_accounts: int


# ─── Governance ───────────────────────────────────────────────────────────────

class SegmentMetrics(BaseModel):
    loan_type: str
    auc_roc: float
    precision_at_top10pct: float
    recall: float
    false_positive_rate: float
    test_n: int


class FairnessSegmentResult(BaseModel):
    status: str
    reliability: Optional[str] = None
    n_total: Optional[int] = None
    n_positive: Optional[int] = None
    n_fn: Optional[int] = None
    fpr: Optional[float] = None
    fnr: Optional[float] = None
    fnr_ci_95_lo: Optional[float] = None
    fnr_ci_95_hi: Optional[float] = None
    ci_overlaps_baseline: Optional[bool] = None
    fpr_deviation: Optional[float] = None
    fnr_deviation: Optional[float] = None


class FlaggedFairnessSegment(BaseModel):
    dimension: str
    segment: str
    reasons: List[str]
    n_positive: Optional[int] = None
    n_fn: Optional[int] = None
    fpr: float
    fnr: float
    fnr_ci_95_lo: Optional[float] = None
    fnr_ci_95_hi: Optional[float] = None
    ci_overlaps_baseline: Optional[bool] = None
    reliability: Optional[str] = None


class FairnessOverall(BaseModel):
    fpr: float
    fnr: float
    total_n: int
    positive_n: int


class FairnessReport(BaseModel):
    overall: FairnessOverall
    by_industry: Dict[str, FairnessSegmentResult]
    by_region: Dict[str, FairnessSegmentResult]
    flagged_segments: List[FlaggedFairnessSegment]


class GovernanceResponse(BaseModel):
    model_version: str
    trained_at: str
    algorithm: str
    feature_count: int
    train_months: str
    val_months: str
    test_months: str
    avg_auc_roc: float
    avg_precision_at_top10: float
    avg_recall: float
    avg_false_positive_rate: float
    meets_auc_target: bool
    per_segment_metrics: List[SegmentMetrics]
    audit_log: List[Dict[str, Any]]
    fairness: Optional[FairnessReport] = None
    fairness_status: Optional[str] = None   # human-readable summary logged at startup


# ─── Alerts ───────────────────────────────────────────────────────────────────

class Alert(BaseModel):
    alert_id: str
    borrower_id: str
    business_name: str
    loan_type: str
    industry: str
    alert_type: str  # "grade_downgrade" | "stress_spike" | "dpd_new" | "litigation"
    severity: str  # "critical" | "high" | "medium"
    message: str
    old_grade: Optional[str] = None
    new_grade: Optional[str] = None
    stress_score: float
    triggered_at: str


class AlertsResponse(BaseModel):
    alerts: List[Alert]
    total: int
    critical_count: int
    high_count: int


# ─── Live Dynamic Predict ─────────────────────────────────────────────────────

class MonthlySnapshotInput(BaseModel):
    dscr: float = Field(..., ge=0.0, le=20.0, description="Debt Service Coverage Ratio")
    bureau_score: int = Field(..., ge=300, le=900, description="CIBIL/Bureau score")
    bureau_enquiries_6m: int = Field(..., ge=0, le=100, description="Bureau enquiries in last 6 months")
    gst_turnover_lakhs: float = Field(..., ge=0.0, le=100000.0, description="GST turnover in Lakhs")
    gst_filing_delay_days: int = Field(..., ge=0, le=365, description="GST filing delay in days")
    gst_filing_missed: int = Field(..., ge=0, le=12, description="GST filing missed months")
    bank_avg_balance_lakhs: float = Field(..., ge=0.0, le=100000.0, description="Average bank balance in Lakhs")
    bank_balance_volatility: float = Field(..., ge=0.0, le=5.0, description="Volatility of bank balance")
    overdraft_utilization_pct: float = Field(..., ge=0.0, le=1.0, description="Overdraft utilization percentage (0.0 to 1.0)")
    epfo_employee_count: int = Field(..., ge=0, le=100000, description="EPFO employee count")
    dpd_current: int = Field(..., ge=0, le=999, description="Current Days Past Due")
    dpd_max_12m: int = Field(..., ge=0, le=999, description="Maximum DPD in last 12 months")
    # NLP / Unstructured
    gst_remark_sentiment_score: float = Field(..., ge=-1.0, le=1.0, description="GST sentiment score (-1 to 1)")
    transaction_anomaly_score: float = Field(..., ge=0.0, le=1.0, description="Transaction anomaly score (0 to 1)")
    litigation_flag: int = Field(..., ge=0, le=1, description="Litigation flag (0 or 1)")
    litigation_severity: int = Field(..., ge=0, le=2, description="Litigation severity class (0, 1, or 2)")
    news_sentiment_score: float = Field(..., ge=-1.0, le=1.0, description="News sentiment score (-1 to 1)")


class LivePredictRequest(BaseModel):
    borrower_id: str
    current_snapshot: MonthlySnapshotInput


class LivePredictResponse(BaseModel):
    borrower_id: str
    pd_probability: float
    stress_score: float
    risk_grade: str
    top_reason_codes: List[ReasonCode]
    narrative_summary: str
    model_version: str
    confidence_level: Optional[str] = "high"

