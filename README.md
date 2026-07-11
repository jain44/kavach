# Kavach: MSME Early Warning Default Prediction System

Kavach is a comprehensive, production-grade early warning system for predicting Defaults in Micro, Small, and Medium Enterprises (MSMEs), developed for IDBI Innovate 2026. 

It implements a calibrated Machine Learning scoring backend (utilizing XGBoost with Isotonic Calibration and SHAP reason codes) coupled with a modern React SPA dashboard and a persistent PostgreSQL database layer.

---

## 🏗️ Architecture & Stack

Kavach utilizes a modern full-stack decoupled architecture:

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
Kavach/
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

## 🚀 Setup & Execution

You can run Kavach locally using three different methods depending on your preferences.

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

## 🔑 Demo Logins

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
