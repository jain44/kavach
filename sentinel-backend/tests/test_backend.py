import sys
import unittest
from pathlib import Path
from datetime import datetime

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Configure environment for testing with SQLite fallback
import os
os.environ["DATABASE_URL"] = "sqlite:///./kavach_test.db"

from fastapi.testclient import TestClient
from api.main import app
from db.database import SessionLocal, engine
from db.models import Base, User, BorrowerProfile, MonthlySnapshot, AuditLog, Prediction, ModelVersion
from db.crypto import encrypt_val, decrypt_val

class TestKavachBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. Ensure clean schema recreation on test DB
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        # 2. Seed minimum required test data
        db = SessionLocal()
        try:
            # Seed test model version
            db.add(ModelVersion(
                version_id="v1.0.0",
                trained_at=datetime.utcnow(),
                metrics_snapshot_json="{}",
                is_current=True
            ))

            import bcrypt
            # Seed test users with different roles
            db.add(User(
                username="risk_officer", name="Priya Sharma", role="risk_officer",
                password_hash=bcrypt.hashpw(b"kavach123", bcrypt.gensalt()).decode(), is_active=True
            ))
            db.add(User(
                username="rm", name="Arjun Mehta", role="rm",
                password_hash=bcrypt.hashpw(b"kavach123", bcrypt.gensalt()).decode(), is_active=True
            ))
            db.add(User(
                username="compliance", name="Anjali Iyer", role="compliance",
                password_hash=bcrypt.hashpw(b"kavach123", bcrypt.gensalt()).decode(), is_active=True
            ))
            db.add(User(
                username="cro", name="Dr. Vikram Nair", role="cro",
                password_hash=bcrypt.hashpw(b"kavach123", bcrypt.gensalt()).decode(), is_active=True
            ))

            # Seed a test borrower profile with encrypted PII
            db.add(BorrowerProfile(
                borrower_id="MSME00001",
                business_name="Acme Corp",
                gstin=encrypt_val("27AAAAA1111A1Z5"),
                pan=encrypt_val("ABCDE1234A"),
                loan_type="Working Capital",
                industry="Manufacturing",
                region="West",
                loan_amount_lakhs=45.0,
                vintage_years=3.5,
                employee_count_initial=15
            ))

            # Seed sufficient snapshots for MSME00001
            for m in range(5):
                db.add(MonthlySnapshot(
                    borrower_id="MSME00001", as_of_month=f"2025-0{m+1}", month_index=m,
                    loan_type="Working Capital", industry="Manufacturing", dscr=1.4,
                    bureau_score=710, bureau_enquiries_6m=1, gst_turnover_lakhs=12.0,
                    gst_filing_delay_days=0, gst_filing_missed=0, bank_avg_balance_lakhs=4.0,
                    bank_balance_volatility=0.05, overdraft_utilization_pct=0.3,
                    epfo_employee_count=18, dpd_current=0, dpd_max_12m=0,
                    gst_remark_sentiment_score=0.7, transaction_anomaly_score=0.05,
                    litigation_flag=0, litigation_severity=0, news_sentiment_score=0.5,
                    label_default_12m=0, is_defaulter=0
                ))

            # Seed a prediction for MSME00001
            db.add(Prediction(
                borrower_id="MSME00001", month_index=4, as_of_month="2025-05",
                loan_type="Working Capital", pd_probability=0.015, stress_score=8.0,
                risk_grade="AAA", model_version_id="v1.0.0"
            ))

            from sqlalchemy import text
            # Create append-only triggers on test SQLite database
            db.execute(text("""
                CREATE TRIGGER IF NOT EXISTS audit_log_no_update
                BEFORE UPDATE ON audit_logs
                BEGIN
                    SELECT RAISE(ABORT, 'Audit logs are immutable. UPDATE operations are prohibited.');
                END;
            """))
            db.execute(text("""
                CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
                BEFORE DELETE ON audit_logs
                BEGIN
                    SELECT RAISE(ABORT, 'Audit logs are immutable. DELETE operations are prohibited.');
                END;
            """))

            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

        cls.client_ctx = TestClient(app)
        cls.client = cls.client_ctx.__enter__()
        
        # Log in to get tokens for different roles
        cls.token_ro = cls._get_auth_token("risk_officer")
        cls.token_rm = cls._get_auth_token("rm")
        cls.token_comp = cls._get_auth_token("compliance")
        cls.token_cro = cls._get_auth_token("cro")

    @classmethod
    def tearDownClass(cls):
        cls.client_ctx.__exit__(None, None, None)
        # Drop all test database tables
        Base.metadata.drop_all(bind=engine)
        if os.path.exists("./kavach_test.db"):
            try:
                os.remove("./kavach_test.db")
            except Exception:
                pass

    @classmethod
    def _get_auth_token(cls, username):
        """Helper to login and retrieve JWT token."""
        role = "risk_officer" if username == "risk_officer" else username
        login_body = {
            "username": username,
            "password": "kavach123",
            "role": role
        }
        res = cls.client.post("/api/v1/auth/login", json=login_body)
        if res.status_code == 200:
            return res.json()["access_token"]
        return ""

    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "Kavach API")
        self.assertTrue(data["data_loaded"])

    def test_unauthenticated_request_denied(self):
        """Test that unauthenticated requests to protected endpoints return 401."""
        req_body = {
            "borrower_id": "MSME00001",
            "hypothetical_changes": {}
        }
        response = self.client.post("/api/v1/simulate", json=req_body)
        self.assertEqual(response.status_code, 401)

    def test_simulate_endpoint_no_changes(self):
        """Test simulate endpoint when no parameter changes are requested."""
        req_body = {
            "borrower_id": "MSME00001",
            "hypothetical_changes": {}
        }
        headers = {"Authorization": f"Bearer {self.token_ro}"}
        response = self.client.post("/api/v1/simulate", json=req_body, headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["borrower_id"], "MSME00001")
        self.assertEqual(data["simulated_stress_score"], data["original_stress_score"])
        self.assertEqual(data["delta_stress_score"], 0.0)
        self.assertFalse(data["grade_changed"])

    def test_rbac_governance_access(self):
        """Test Server-side RBAC role gating on governance endpoint."""
        # 1. RM (Relationship Manager) should be blocked (403)
        headers_rm = {"Authorization": f"Bearer {self.token_rm}"}
        response_rm = self.client.get("/api/v1/governance", headers=headers_rm)
        self.assertEqual(response_rm.status_code, 403)
        self.assertIn("forbidden", response_rm.json()["detail"].lower())

        # 2. Compliance Officer should be allowed (200)
        headers_comp = {"Authorization": f"Bearer {self.token_comp}"}
        response_comp = self.client.get("/api/v1/governance", headers=headers_comp)
        self.assertEqual(response_comp.status_code, 200)

        # 3. CRO should be allowed (200)
        headers_cro = {"Authorization": f"Bearer {self.token_cro}"}
        response_cro = self.client.get("/api/v1/governance", headers=headers_cro)
        self.assertEqual(response_cro.status_code, 200)

    def test_pii_decryption_and_masking(self):
        """Test PII (PAN/GSTIN) decryption and masking based on roles (DPDP Act compliance)."""
        # 1. Query with RM role (should receive masked GSTIN and PAN)
        headers_rm = {"Authorization": f"Bearer {self.token_rm}"}
        response_rm = self.client.post("/api/v1/predict", json={"borrower_id": "MSME00001"}, headers=headers_rm)
        self.assertEqual(response_rm.status_code, 200)
        data_rm = response_rm.json()
        self.assertEqual(data_rm["pan"], "XXXXXX234A")
        self.assertEqual(data_rm["gstin"], "27XXXXXXXXXX1Z5")

        # 2. Query with Compliance role (should receive decrypted, raw/unmasked GSTIN and PAN)
        headers_comp = {"Authorization": f"Bearer {self.token_comp}"}
        response_comp = self.client.post("/api/v1/predict", json={"borrower_id": "MSME00001"}, headers=headers_comp)
        self.assertEqual(response_comp.status_code, 200)
        data_comp = response_comp.json()
        self.assertEqual(data_comp["pan"], "ABCDE1234A")
        self.assertEqual(data_comp["gstin"], "27AAAAA1111A1Z5")

    def test_audit_logs_immutability(self):
        """Test that update and delete queries on the audit_logs table are blocked at the DB level."""
        db = SessionLocal()
        try:
            # Insert a temporary log
            log = AuditLog(event="Test entry", user="tester")
            db.add(log)
            db.commit()
            log_id = log.id

            # Try to UPDATE the log entry
            with self.assertRaises(Exception):
                db.query(AuditLog).filter_by(id=log_id).update({"event": "Tampered event"})
                db.commit()
            db.rollback()

            # Try to DELETE the log entry
            with self.assertRaises(Exception):
                db.query(AuditLog).filter_by(id=log_id).delete()
                db.commit()
            db.rollback()

        finally:
            db.close()

    def test_predict_live_ntc(self):
        """Test that predict/live triggers low confidence for NTC borrowers (< 3 months history)."""
        db = SessionLocal()
        try:
            # Seed NTC borrower profile
            db.add(BorrowerProfile(
                borrower_id="TESTNTC001", business_name="Ntc Corp",
                gstin=encrypt_val("27BBBBB2222B2Z6"), pan=encrypt_val("WXYZ5678B"),
                loan_type="Working Capital", industry="Retail", region="North",
                loan_amount_lakhs=10.0, vintage_years=1.0, employee_count_initial=2
            ))
            # Seed only 1 monthly snapshot (making history length = 1 < 3)
            db.add(MonthlySnapshot(
                borrower_id="TESTNTC001", as_of_month="2025-01", month_index=0,
                loan_type="Working Capital", industry="Retail", dscr=1.1,
                bureau_score=680, bureau_enquiries_6m=2, gst_turnover_lakhs=2.5,
                gst_filing_delay_days=1, gst_filing_missed=0, bank_avg_balance_lakhs=0.8,
                bank_balance_volatility=0.2, overdraft_utilization_pct=0.8,
                epfo_employee_count=3, dpd_current=0, dpd_max_12m=0,
                gst_remark_sentiment_score=0.5, transaction_anomaly_score=0.4,
                litigation_flag=0, litigation_severity=0, news_sentiment_score=0.5,
                label_default_12m=0, is_defaulter=0
            ))
            db.commit()
        finally:
            db.close()

        req_body = {
            "borrower_id": "TESTNTC001",
            "current_snapshot": {
                "dscr": 1.1, "bureau_score": 680, "bureau_enquiries_6m": 2,
                "gst_turnover_lakhs": 2.5, "gst_filing_delay_days": 1, "gst_filing_missed": 0,
                "bank_avg_balance_lakhs": 0.8, "bank_balance_volatility": 0.2,
                "overdraft_utilization_pct": 0.8, "epfo_employee_count": 3,
                "dpd_current": 0, "dpd_max_12m": 0, "gst_remark_sentiment_score": 0.5,
                "transaction_anomaly_score": 0.4, "litigation_flag": 0, "litigation_severity": 0,
                "news_sentiment_score": 0.5
            }
        }
        headers = {"Authorization": f"Bearer {self.token_ro}"}
        response = self.client.post("/api/v1/predict/live", json=req_body, headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["confidence_level"], "low — limited history (2mo)")


if __name__ == "__main__":
    unittest.main()
