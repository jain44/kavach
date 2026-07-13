# Sentinel: MSME Early Warning Default Prediction System

Sentinel is a comprehensive, production-grade early warning system for predicting Defaults in Micro, Small, and Medium Enterprises (MSMEs), developed for IDBI Innovate 2026. 

It implements a calibrated Machine Learning scoring backend (utilizing XGBoost with Isotonic Calibration and SHAP reason codes) coupled with a modern React SPA dashboard and a persistent PostgreSQL database layer.

---

## 🏗️ Architecture & Stack

Sentinel utilizes a modern full-stack decoupled architecture:

```
                  ┌────────────────────────────────────────┐
                  │          Browser (React SPA)           │
                  └───────────────────┬────────────────────┘
                                      │ HTTP /api/v1/*
                                      ▼
                  ┌────────────────────────────────────────┐
                  │       FastAPI API (Python/Uvicorn)     │
                  └──────┬──────────────────────────┬──────┘
                         │                          │
                         │ SQLAlchemy ORM           │ joblib.load()
                         ▼                          ▼
        ┌──────────────────────────────────┐  ┌───────────────────────────┐
        │       PostgreSQL Database        │  │   ML Calibration Models   │
        │                                  │  │   (.pkl assets on disk)   │
        └──────────────────────────────────┘  └───────────────────────────┘
```

- **Frontend**: React (TypeScript) + Vite + TailwindCSS / Custom CSS + Framer Motion.
- **Backend**: FastAPI (Python) + Uvicorn + Pydantic.
- **Database**: PostgreSQL 16 + SQLAlchemy ORM + Alembic (migrations).
- **ML & Explanations**: XGBoost + Isotonic Calibration + SHAP (SHapley Additive exPlanations) for local feature impact explanations.

---

## 📂 Project Structure

```
Sentinel/
├── sentinel-backend/         # FastAPI backend
│   ├── alembic/              # Database migration scripts
│   ├── api/                  # API endpoints, routers, and schemas
│   │   ├── routes/           # User CRUD & specific endpoint routes
│   │   ├── main.py           # Core FastAPI setup, models loading & endpoints
│   │   └── schemas.py        # Pydantic models for validation
│   ├── db/                   # Database configuration & seeding
│   │   ├── database.py       # Engine creation & sessionmaker
│   │   ├── models.py         # SQLAlchemy ORM models
│   │   └── seed.py           # Idempotent CSV-to-DB seeder
│   ├── ml/                   # Machine learning feature engineering & scoring
│   ├── models/               # Serialized calibrators, metrics & fairness reports
│   ├── data/                 # Raw/generated synthetic CSV datasets
│   ├── requirements.txt      # Python dependencies
│   └── Dockerfile            # Container build specification
├── sentinel-frontend/        # React SPA frontend
│   ├── src/
│   │   ├── components/       # Layouts, Sidebar, and generic elements
│   │   ├── contexts/         # React Auth context (JWT storage)
│   │   ├── lib/              # Axios API client wrapper
│   │   └── pages/            # Portfolio, Details, What-If Simulator, Alerts, Users
│   ├── Dockerfile            # Multi-stage production build (serves via Nginx)
│   └── nginx.conf            # Reverse-proxy setup for SPA routing & API forwarding
├── docker-compose.yml        # Orchestration script (Postgres + Backend + Frontend)
├── start-dev.ps1             # Windows local dev environment quickstart script
└── .gitignore                # Global git ignore file
```

---

## Deployed App

Latest frontend deployment: [https://kavach-gules.vercel.app/](https://kavach-gules.vercel.app/)

---

## Setup & Execution

You can run Sentinel locally using three different methods depending on your preferences.

### Option A: PowerShell Quickstart (Recommended for Windows)

> **Prerequisite**: Docker Desktop running locally (starts PostgreSQL).

Run the automated dev startup script in a PowerShell window:
```powershell
.\start-dev.ps1
```
This script will automatically:
1. Spin up a PostgreSQL 16 container in Docker.
2. Initialize a Python virtual environment and install backend dependencies.
3. Apply database schemas via Alembic.
4. Seed the database with the MSME profiles, predictions, and snapshot histories from CSVs.
5. Concurrently launch the FastAPI backend (Port 8000) and the Vite development server (Port 5173).

---

### Option B: Docker Compose (All-in-One Containerized)

To build and run the entire stack (PostgreSQL database, FastAPI backend API, React app behind Nginx) inside Docker:
```bash
docker-compose up --build
```
- **Frontend App**: [http://localhost](http://localhost) (Served on port 80 via Nginx proxy)
- **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Database Server**: `localhost:5432`

---

### Option C: Manual Setup

1. **Start PostgreSQL**: Set up a PostgreSQL instance and database named `kavach_db` on `localhost:5432`.
2. **Setup Backend**:
   ```bash
   cd sentinel-backend
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   
   # Set environment variables (or write them in sentinel-backend/.env)
   export DATABASE_URL="postgresql+psycopg://kavach:kavach123@localhost:5432/kavach_db"
   export KAVACH_SECRET_KEY="your-secure-secret-key"
   
   # Apply migrations and seed data
   python -m alembic upgrade head
   python -m db.seed
   
   # Start server
   uvicorn api.main:app --reload --port 8000
   ```
3. **Setup Frontend**:
   ```bash
   cd sentinel-frontend
   npm install
   npm run dev
   ```
   Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Verified Demo Values

- Target borrower: `MSME00231`
- Current stress / grade: `82.0 / C`
- Current PD: `35.96%`
- What-if sliders: `DPD -30 days`, `DSCR +0.50`
- Simulated stress / grade: `65.93 / B`
- Governance AUC-ROC: `0.743`
- Governance Precision @ Top 10%: `38.87%`

---

## Demo Logins

All demo accounts share the password: **`kavach123`**

| Username | Role | Accessible Viewpages |
|---|---|---|
| `risk_officer` | Risk Officer | Heatmap, Account Details, What-If Simulator, Alerts |
| `rm` | Relationship Manager | Heatmap, Account Details, What-If Simulator, Alerts |
| `cro` | Chief Risk Officer | **All Pages** (including Portfolio Analytics, Governance, and User Management) |
| `compliance` | Compliance Officer | Account Details, Model Governance |
| `admin` | Administrator | User Management (User CRUD) |

---

## 📊 Features

1. **Portfolio Heatmap & Analytics**: Multi-dimensional view of loan exposures mapped against calibrated credit risk grades (AAA to D) and stress scores.
2. **Explainable AI (XAI)**: Locally computed SHAP explanations representing exactly why an MSME has high probability of default (PD).
3. **What-If Stress Simulator**: Dynamic sandbox recalculating stress outcomes instantly based on parameter deltas (DSCR changes, DPD spikes, bureau score drops).
4. **Model Governance**: Model performance dashboards showcasing AUC-ROC, Precision/Recall, and demographic fairness parity tracking.
5. **Calibrator Drift Monitoring**: Baseline drift metrics computed during API health checks (`/api/v1/health`), signaling when model recalibration is necessary.
6. **Audited User Management**: CRUD user administrative page with strict role guards (restricted to CRO/Admin) and automated audit logging.

---

## 💼 Business Case, Competitive Landscape & Regulatory Alignment (Phase 5)

This section presents the real cost-benefit analysis, competitive positioning, and regulatory compliance alignment for Sentinel, custom-tailored to IDBI Bank's financial disclosures and the latest Reserve Bank of India (RBI) mandates.

### 1. Real Cost-Benefit / ROI Model
Using IDBI Bank’s actual public financial disclosures as of **December 31, 2025 (Q3 FY2026)**, the bank's net advances stand at **₹2,38,786 crore**, with the active MSME segment advances portfolio valued at **₹22,826 crore**.

The table below illustrates a transparent, spreadsheet-style ROI model estimating the financial impact of deploying Sentinel. The model measures how Sentinel's recall lift (default detection rate of **51.07%** vs. the legacy baseline of **5.5%**) translates to reduced slippages-to-NPA and direct provisioning savings under three scenarios.

| Metric / Assumption | Conservative | Base Case | Optimistic | Source / Rationale |
| :--- | :---: | :---: | :---: | :--- |
| **Active MSME Advances Portfolio** | ₹22,826 Cr | ₹22,826 Cr | ₹22,826 Cr | IDBI Bank Investor Presentation (Dec 2025) |
| **Assumed MSME NPA Rate (%)** | 5.0% | 7.0% | 9.0% | *Assumption* (Slightly above overall bank GNPA of 2.57%) |
| **Annual Slippage-to-NPA Rate (%)** | 1.5% | 2.0% | 2.5% | *Assumption* (Proportion of performing book defaulting yearly) |
| **Projected Annual NPA Slippage (₹)** | ₹342.39 Cr | ₹456.52 Cr | ₹570.65 Cr | Calculated: Portfolio × Slippage Rate |
| **Sentinel Recall Lift over Legacy** | 45.57% | 45.57% | 45.57% | **Measured**: Sentinel Recall (51.07%) - Legacy (5.5%) |
| **Early-Flagged Prevention Rate (%)** | 10.0% | 15.0% | 25.0% | *Assumption* (Cure rate via proactive restructured terms) |
| **Prevented Annual NPA Slippages (₹)** | **₹15.60 Cr** | **₹31.21 Cr** | **₹65.01 Cr** | Calculated: Slippage × Recall Lift × Prevention Rate |
| **Direct Provisioning Savings (₹)** | **₹3.90 Cr** | **₹7.80 Cr** | **₹16.25 Cr** | Calculated: Prevented Slippages × 25% Prov. Cost |
| **Total Cumulative 3-Year Savings (₹)** | **₹58.50 Cr** | **₹117.03 Cr** | **₹243.78 Cr** | Calculated: 3 × (Prevented Slippage + Prov. Savings) |

#### Rationale & Key Assumptions:
*   **Provisioning Cost (25%)**: Under RBI IRAC norms, substandard assets require a minimum 15% provision (secured) to 25% (unsecured), rising to 40% for Doubtful status. An average provisioning cost of 25% is used.
*   **Prevention Rate (10%-25%)**: Proactive intervention (debt restructuring, credit lines adjustments) enables the recovery team to prevent a percentage of early-detected standard accounts from deteriorating to 90+ DPD NPA.

---

### 2. Competitive Landscape Refresh
A comparative evaluation of Sentinel against current offerings in the Indian MSME credit scoring and lending space (CRIF High Mark, Jocata, and Perfios) reveals distinct strategic positioning.

| Feature / Dimension | Sentinel | CRIF High Mark (CIBR) | Jocata (SWARA) | Perfios (KScan AI) |
| :--- | :--- | :--- | :--- | :--- |
| **Core Focus** | **Post-Sanction Portfolio Monitoring** | Credit Evaluation at Origination | Automated Onboarding / Sourcing | Intelligence Layer & Data Extraction |
| **Primary Data Source** | Multimodal: Daily CC/OD Balances + GST Lags + EPFO Trends + Legal | Historical Repayment Records (Bureau Database) | Tax Filings (GST) + Bank Statement Analyzer | Verified Public Documents (900+ Registries) |
| **Calibration Method** | **Isotonic Calibration** (Maps raw scores to true default rates) | Ordinal Risk Ranking (CIBR 1 to 13) | Proprietary behavioral rating | Rule-based analytics and identity validation |
| **Risk Sensitivity** | Real-time / Daily (Early Warning Signals) | Reactive (Dependent on monthly bank uploads) | Sourcing-point query only | Sourcing-point query only |
| **Interactivity** | **Interactive What-If stress sandbox** | Static credit bureau reports | Static "Go/No-Go" API | Static underwriting dashboard |

*   **Sentinel Differentiation**: While competitors act as "gatekeepers" at the point of loan origination (gate-keeping credit check), Sentinel is built for continuous, post-sanction portfolio monitoring—acting as an automated cockpit to discover credit deterioration long before default events occur.

---

### 3. Regulatory & Compliance Alignment
Sentinel is designed to comply with the latest regulatory mandates issued by the Reserve Bank of India (RBI):

*   **RBI Draft Guidance on Model Risk Management (MRM) (June 24, 2026)**:
    *   *Mandate*: Regulated Entities must implement a Board-approved Model Risk Management Framework covering the entire model life cycle. Institutions are fully accountable for AI/ML models.
    *   *Alignment*: Sentinel maintains a centralized Model Governance module tracking validation metrics (AUC-ROC, F1, PR curves) and demographic parity audits (demographic fairness checked via 95% Wilson CI bounds).
    *   *Kill Switch & Oversight*: The system provides full transparency to Compliance Officers, including NTC warning tags and fallback logic to unified model baselines, preventing un-monitored AI decision drift.
*   **RBI IRAC & SMA Norms**:
    *   *Mandate*: Banks must classify stressed assets into Special Mention Accounts (SMA-0: 1-30 days overdue, SMA-1: 31-60 days, SMA-2: 61-90 days) and report large credits to CRILC.
    *   *Alignment*: Sentinel is an Early Warning System (EWS) designed to capture risks *prior* to formal SMA status. In our pipeline setup (`time_based_split`), post-default accounts ($\ge 90$ DPD NPA) are strictly excluded from the active scoring pool to prevent decision boundary contamination.
*   **Digital Public Infrastructure & Alternate Data (ULI & Account Aggregator)**:
    *   *Mandate*: RBI continues to expand consent-based credit frameworks (Unified Lending Interface - ULI and Account Aggregator - AA) to close the MSME credit gap.
    *   *Alignment*: Sentinel's feature pipeline integrates alternate data (GST filing delay, EPFO count trend, legal litigation) mimicking AA data feeds to establish a comprehensive credit profile.

