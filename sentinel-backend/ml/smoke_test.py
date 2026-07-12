import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from api.main import app

def run_smoke_test():
    print("============================================================")
    # Configure the test client inside a 'with' context to trigger startup events
    with TestClient(app) as client:
        # We will test all 5 roles
        roles = {
            "cro": "cro",
            "compliance": "compliance",
            "risk_officer": "risk_officer",
            "rm": "rm",
            "admin": "admin"
        }
        
        # Track test statuses
        results = {}
        
        # Verify anonymous health ping
        print("[TEST] Anonymous Health Ping...")
        r_ping = client.get("/health")
        assert r_ping.status_code == 200, f"Ping failed: {r_ping.text}"
        ping_data = r_ping.json()
        assert ping_data["status"] == "ok"
        assert ping_data["data_loaded"] is True
        print("  -> PASSED")

        # Verify detailed health calibration monitor
        print("[TEST] Detailed Health & Calibration Drift Monitor...")
        r_health = client.get("/api/v1/health")
        assert r_health.status_code == 200, f"Health failed: {r_health.text}"
        health_data = r_health.json()
        assert health_data["database"] == "ok" or "sqlite" in health_data["database"]
        assert "calibration_monitor" in health_data
        cal_monitor = health_data["calibration_monitor"]
        print(f"  -> Drift Status: {cal_monitor['status']} | Live PD: {cal_monitor['live_avg_pd']} | Deviation: {cal_monitor['deviation_pp']}pp")
        print("  -> PASSED")

        # Sample borrower ID to test against
        borrower_id = "MSME00042"

        for role_name, username in roles.items():
            print(f"\n====================== ROLE: {role_name.upper()} ======================")
            
            # 1. Login
            print(f"[TEST] Auth Login for {username}...")
            login_res = client.post("/api/v1/auth/login", json={
                "username": username,
                "password": "kavach123",
                "role": role_name
            })
            if login_res.status_code != 200:
                print(f"  -> FAILED to login: {login_res.text}")
                results[role_name] = "FAIL (Login)"
                continue
            
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print("  -> Login Successful")
            
            # 2. Portfolio Heatmap Load
            print("[TEST] Fetching Portfolio Heatmap...")
            port_res = client.get("/api/v1/portfolio", headers=headers)
            assert port_res.status_code == 200, f"Portfolio fetch failed: {port_res.text}"
            port_data = port_res.json()
            assert "accounts" in port_data
            assert port_data["total_accounts"] > 0
            print(f"  -> Total Accounts: {port_data['total_accounts']} | Avg Stress: {port_data['avg_stress_score']}")
            
            # Verify Score Δ MoM calculation (accounts list check)
            for acc in port_data["accounts"][:5]:
                # Just verify keys exist
                assert "stress_score_delta" in acc
                assert "risk_grade_prev" in acc
            print("  -> PASSED")

            # 3. Account Detail Predict & Masking Check
            print(f"[TEST] Fetching prediction for {borrower_id}...")
            pred_res = client.post("/api/v1/predict", headers=headers, json={"borrower_id": borrower_id})
            assert pred_res.status_code == 200, f"Prediction fetch failed: {pred_res.text}"
            pred_data = pred_res.json()
            
            # Check PII Masking logic
            pan = pred_data.get("pan", "")
            gstin = pred_data.get("gstin", "")
            if role_name in ("compliance", "admin"):
                assert "X" not in pan or len(pan) < 5 or pan.startswith("XXXX") == False, f"PII should be unmasked for {role_name}: {pan}"
                assert "X" not in gstin or len(gstin) < 6, f"PII should be unmasked for {role_name}: {gstin}"
                print(f"  -> PII Masking: UNMASKED as expected (PAN: {pan}, GSTIN: {gstin})")
            else:
                assert "X" in pan or pan == "XXXXXXXXXX", f"PII should be masked for {role_name}: {pan}"
                assert "X" in gstin or gstin == "XXXXXXXXXXXXXXX", f"PII should be masked for {role_name}: {gstin}"
                print(f"  -> PII Masking: MASKED as expected (PAN: {pan}, GSTIN: {gstin})")
            print("  -> PASSED")

            # 4. Explainability (SHAP reasons)
            print(f"[TEST] Fetching SHAP explanations for {borrower_id}...")
            exp_res = client.get(f"/api/v1/explain/{borrower_id}", headers=headers)
            assert exp_res.status_code == 200, f"Explain failed: {exp_res.text}"
            exp_data = exp_res.json()
            assert "top_reason_codes" in exp_data
            assert "narrative_summary" in exp_data
            print(f"  -> Narrative Summary: {exp_data['narrative_summary'][:80]}...")
            print("  -> PASSED")

            # 5. Account History
            print(f"[TEST] Fetching account history for {borrower_id}...")
            hist_res = client.get(f"/api/v1/account/{borrower_id}/history", headers=headers)
            assert hist_res.status_code == 200, f"History failed: {hist_res.text}"
            hist_data = hist_res.json()
            assert "history" in hist_data
            print(f"  -> History Data Points: {len(hist_data['history'])}")
            print("  -> PASSED")

            # 6. Account RM Notes (GET & POST)
            print(f"[TEST] Managing notes for {borrower_id}...")
            notes_res = client.get(f"/api/v1/account/{borrower_id}/notes", headers=headers)
            assert notes_res.status_code == 200
            notes_count_before = len(notes_res.json()["notes"])
            
            # Post note
            post_res = client.post(f"/api/v1/account/{borrower_id}/notes", headers=headers, json={
                "note_text": f"Smoke testing RM action log from role {role_name}"
            })
            assert post_res.status_code == 201
            
            # Verify GET reflects post
            notes_res_after = client.get(f"/api/v1/account/{borrower_id}/notes", headers=headers)
            assert len(notes_res_after.json()["notes"]) == notes_count_before + 1
            print(f"  -> Notes log verify: successfully appended note (Count: {notes_count_before} -> {notes_count_before + 1})")
            print("  -> PASSED")

            # 7. What-If Simulator
            print(f"[TEST] Executing What-If Simulation for {borrower_id}...")
            sim_res = client.post("/api/v1/simulate", headers=headers, json={
                "borrower_id": borrower_id,
                "hypothetical_changes": {
                    "dscr_delta": -0.4,
                    "gst_delay_days": 10,
                    "bureau_score_delta": -50,
                    "overdraft_utilization_delta": 0.1,
                    "dpd_change": 15,
                    "epfo_change_pct": -0.1
                }
            })
            assert sim_res.status_code == 200, f"Simulation failed: {sim_res.text}"
            sim_data = sim_res.json()
            print(f"  -> Orig Stress: {sim_data['original_stress_score']} | Sim Stress: {sim_data['simulated_stress_score']} | Delta: {sim_data['delta_stress_score']}")
            print("  -> PASSED")

            # 8. Warning Alerts Panel
            print("[TEST] Fetching Alerts...")
            alert_res = client.get("/api/v1/alerts?days=30", headers=headers)
            assert alert_res.status_code == 200, f"Alerts failed: {alert_res.text}"
            alert_data = alert_res.json()
            assert "alerts" in alert_data
            print(f"  -> Total active alerts retrieved: {alert_data['total']}")
            print("  -> PASSED")

            # 9. Model Governance Panel (Role Restricted)
            print("[TEST] Fetching Model Governance Page...")
            gov_res = client.get("/api/v1/governance", headers=headers)
            if role_name in ("cro", "compliance"):
                assert gov_res.status_code == 200, f"Governance access denied for {role_name}: {gov_res.text}"
                gov_data = gov_res.json()
                # Factual checks on the metrics payload
                assert gov_data["meets_auc_target"] is True, "meets_auc_target should be true after training config update"
                assert gov_data["algorithm"] == "Unified XGBoost + Isotonic Calibration"
                assert "backtest_results" in gov_data and gov_data["backtest_results"] is not None
                assert len(gov_data["backtest_results"]) == 3
                print(f"  -> Governance payload check: meets_auc_target={gov_data['meets_auc_target']} | avg_auc_roc={gov_data['avg_auc_roc']}")
                print(f"  -> Backtest records: Window 1={gov_data['backtest_results'][0]['auc']:.4f} | Window 2={gov_data['backtest_results'][1]['auc']:.4f}")
                print("  -> ACCESS GRANTED & PAYLOAD VERIFIED")
            else:
                assert gov_res.status_code == 403, f"Governance should be blocked for {role_name}, got {gov_res.status_code}"
                print("  -> ACCESS DENIED (Correctly blocked by server-side RBAC guard)")
            print("  -> PASSED")

            # 10. User Management CRUD (Role Restricted)
            print("[TEST] Fetching User CRUD List...")
            user_res = client.get("/api/v1/users", headers=headers)
            if role_name in ("cro", "admin"):
                assert user_res.status_code == 200, f"User list access denied for {role_name}: {user_res.text}"
                users_list = user_res.json()
                assert len(users_list) >= 5
                print(f"  -> Total Users registered: {len(users_list)}")
                print("  -> ACCESS GRANTED & PAYLOAD VERIFIED")
            else:
                assert user_res.status_code == 403, f"User list should be blocked for {role_name}, got {user_res.status_code}"
                print("  -> ACCESS DENIED (Correctly blocked by server-side RBAC guard)")
            print("  -> PASSED")

            results[role_name] = "PASS"

        print("\n====================== SMOKE TEST SUMMARY ======================")
        all_passed = True
        for role, status in results.items():
            print(f"  Role: {role:<15} -> {status}")
            if status != "PASS":
                all_passed = False
                
        print("============================================================")
        if all_passed:
            print("  VERDICT: ALL SMOKE TESTS PASSED - REGRESSION CHECK CLEARED!")
            sys.exit(0)
        else:
            print("  VERDICT: SMOKE TEST FAILED!")
            sys.exit(1)

if __name__ == "__main__":
    run_smoke_test()
