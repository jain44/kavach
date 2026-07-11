import sys
import unittest
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from api.main import app

class TestKavachBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Using context manager interface programmatically triggers FastAPI startup/shutdown events
        cls.client_ctx = TestClient(app)
        cls.client = cls.client_ctx.__enter__()
        
        # Log in to get the token for protected endpoints
        cls.token = cls._get_auth_token()
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    @classmethod
    def tearDownClass(cls):
        cls.client_ctx.__exit__(None, None, None)

    @classmethod
    def _get_auth_token(cls):
        """Helper to login and retrieve JWT token."""
        login_body = {
            "username": "risk_officer",
            "password": "kavach123",
            "role": "risk_officer"
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

    def test_auth_login_success(self):
        """Test successful authentication."""
        login_body = {
            "username": "rm",
            "password": "kavach123",
            "role": "rm"
        }
        response = self.client.post("/api/v1/auth/login", json=login_body)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["role"], "rm")
        self.assertEqual(data["username"], "Arjun Mehta")

    def test_auth_login_failure(self):
        """Test authentication failure with incorrect credentials."""
        login_body = {
            "username": "rm",
            "password": "wrongpassword",
            "role": "rm"
        }
        response = self.client.post("/api/v1/auth/login", json=login_body)
        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_request_denied(self):
        """Test that unauthenticated requests to protected endpoints return 401."""
        req_body = {
            "borrower_id": "MSME00001",
            "hypothetical_changes": {}
        }
        # Request without headers
        response = self.client.post("/api/v1/simulate", json=req_body)
        self.assertEqual(response.status_code, 401)

    def test_simulate_endpoint_no_changes(self):
        """Test simulate endpoint when no parameter changes are requested."""
        req_body = {
            "borrower_id": "MSME00001",
            "hypothetical_changes": {}
        }
        response = self.client.post("/api/v1/simulate", json=req_body, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["borrower_id"], "MSME00001")
        self.assertEqual(data["simulated_stress_score"], data["original_stress_score"])
        self.assertEqual(data["delta_stress_score"], 0.0)
        self.assertFalse(data["grade_changed"])
        self.assertEqual(data["delta_explanation"], ["No parameter changes applied"])

    def test_simulate_endpoint_dscr_improvement(self):
        """Test simulate endpoint with a positive DSCR change (should decrease stress)."""
        req_body = {
            "borrower_id": "MSME00001",
            "hypothetical_changes": {
                "dscr_delta": 1.0  # Big improvement in cash flow
            }
        }
        response = self.client.post("/api/v1/simulate", json=req_body, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["borrower_id"], "MSME00001")
        # Increasing DSCR should reduce stress score
        self.assertLessEqual(data["simulated_stress_score"], data["original_stress_score"])

    def test_simulate_endpoint_dpd_deterioration(self):
        """Test simulate endpoint with a positive DPD change (should increase stress)."""
        req_body = {
            "borrower_id": "MSME00001",
            "hypothetical_changes": {
                "dpd_change": 60  # Stalled payments for 60 days
            }
        }
        response = self.client.post("/api/v1/simulate", json=req_body, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["borrower_id"], "MSME00001")
        # Increasing DPD should increase stress score
        self.assertGreaterEqual(data["simulated_stress_score"], data["original_stress_score"])

    def test_predict_live_endpoint(self):
        """Test predict live endpoint with raw borrower snapshot inputs."""
        req_body = {
            "borrower_id": "MSME00001",
            "current_snapshot": {
                "dscr": 1.5,
                "bureau_score": 720,
                "bureau_enquiries_6m": 1,
                "gst_turnover_lakhs": 150.0,
                "gst_filing_delay_days": 2,
                "gst_filing_missed": 0,
                "bank_avg_balance_lakhs": 25.0,
                "bank_balance_volatility": 0.08,
                "overdraft_utilization_pct": 0.45,
                "epfo_employee_count": 42,
                "dpd_current": 0,
                "dpd_max_12m": 0,
                "gst_remark_sentiment_score": 0.6,
                "transaction_anomaly_score": 0.1,
                "litigation_flag": 0,
                "litigation_severity": 0,
                "news_sentiment_score": 0.4
            }
        }
        response = self.client.post("/api/v1/predict/live", json=req_body, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["borrower_id"], "MSME00001")
        self.assertIn("pd_probability", data)
        self.assertIn("stress_score", data)
        self.assertIn("risk_grade", data)
        self.assertIn("top_reason_codes", data)
        self.assertIn("narrative_summary", data)
        self.assertIn("model_version", data)
        self.assertTrue(len(data["top_reason_codes"]) > 0)

    def test_borrower_not_found(self):
        """Test endpoints with a non-existent borrower ID (should return 404)."""
        req_body = {
            "borrower_id": "MSME99999",
            "hypothetical_changes": {}
        }
        response = self.client.post("/api/v1/simulate", json=req_body, headers=self.headers)
        self.assertEqual(response.status_code, 404)

        req_body_predict = {
            "borrower_id": "MSME99999",
            "current_snapshot": {
                "dscr": 1.5,
                "bureau_score": 720,
                "bureau_enquiries_6m": 1,
                "gst_turnover_lakhs": 150.0,
                "gst_filing_delay_days": 2,
                "gst_filing_missed": 0,
                "bank_avg_balance_lakhs": 25.0,
                "bank_balance_volatility": 0.08,
                "overdraft_utilization_pct": 0.45,
                "epfo_employee_count": 42,
                "dpd_current": 0,
                "dpd_max_12m": 0,
                "gst_remark_sentiment_score": 0.6,
                "transaction_anomaly_score": 0.1,
                "litigation_flag": 0,
                "litigation_severity": 0,
                "news_sentiment_score": 0.4
            }
        }
        response = self.client.post("/api/v1/predict/live", json=req_body_predict, headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_predict_live_validation_failure(self):
        """Test predict live endpoint with invalid snapshot inputs (should return 422)."""
        req_body = {
            "borrower_id": "MSME00001",
            "current_snapshot": {
                "dscr": 50000.0,
                "bureau_score": -999,
                "bureau_enquiries_6m": 1,
                "gst_turnover_lakhs": 150.0,
                "gst_filing_delay_days": 2,
                "gst_filing_missed": 0,
                "bank_avg_balance_lakhs": 25.0,
                "bank_balance_volatility": 0.08,
                "overdraft_utilization_pct": 0.45,
                "epfo_employee_count": 42,
                "dpd_current": 0,
                "dpd_max_12m": 0,
                "gst_remark_sentiment_score": 0.6,
                "transaction_anomaly_score": 0.1,
                "litigation_flag": 0,
                "litigation_severity": 0,
                "news_sentiment_score": 0.4
            }
        }
        response = self.client.post("/api/v1/predict/live", json=req_body, headers=self.headers)
        self.assertEqual(response.status_code, 422)

    def test_predict_live_ntc(self):
        """Test predict live endpoint returns low confidence for NTC borrowers (< 3 months of history)."""
        import api.main
        # Backup original snapshots
        orig_snapshots = api.main._snapshots_df.copy()
        try:
            # Filter to only 1 snapshot for MSME00001
            bid = "MSME00001"
            api.main._snapshots_df = orig_snapshots[
                (orig_snapshots["borrower_id"] == bid) & (orig_snapshots["month_index"] == 0)
            ].copy()

            req_body = {
                "borrower_id": bid,
                "current_snapshot": {
                    "dscr": 1.5,
                    "bureau_score": 720,
                    "bureau_enquiries_6m": 1,
                    "gst_turnover_lakhs": 150.0,
                    "gst_filing_delay_days": 2,
                    "gst_filing_missed": 0,
                    "bank_avg_balance_lakhs": 25.0,
                    "bank_balance_volatility": 0.08,
                    "overdraft_utilization_pct": 0.45,
                    "epfo_employee_count": 42,
                    "dpd_current": 0,
                    "dpd_max_12m": 0,
                    "gst_remark_sentiment_score": 0.6,
                    "transaction_anomaly_score": 0.1,
                    "litigation_flag": 0,
                    "litigation_severity": 0,
                    "news_sentiment_score": 0.4
                }
            }
            response = self.client.post("/api/v1/predict/live", json=req_body, headers=self.headers)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["confidence_level"], "low — limited history")
        finally:
            # Restore snapshots
            api.main._snapshots_df = orig_snapshots

if __name__ == "__main__":
    unittest.main()
