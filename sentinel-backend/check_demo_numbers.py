"""
Sentinel Demo Numbers Checker (No external dependencies, No unicode emojis)
Logs in as CRO and prints all the exact numbers needed for the demo script.
Run: venv\Scripts\python.exe check_demo_numbers.py
"""

import urllib.request
import urllib.parse
import json

BASE = "http://localhost:8000"
BORROWER = "MSME00231"

def post_json(url, data, headers=None):
    headers = headers or {}
    headers["Content-Type"] = "application/json"
    req_data = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")

def get_json(url, headers=None):
    headers = headers or {}
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")

print("\n" + "="*60)
print("  SENTINEL DEMO NUMBER CHECKER")
print("="*60)

# ── 1. Login ──────────────────────────────────────────────────────────────────
status, login_res = post_json(f"{BASE}/api/v1/auth/login", {"username": "cro", "password": "kavach123", "role": "cro"})
if status != 200:
    print(f"  [ERROR] Login failed: {status} {login_res}")
    exit(1)
token = login_res["access_token"]
H = {"Authorization": f"Bearer {token}"}
print("\n  [OK] Logged in as CRO")

# ── 2. Portfolio Overview ─────────────────────────────────────────────────────
print("\n" + "-"*60)
print("  SEGMENT 1 -- Portfolio Overview")
print("-"*60)

status, port = get_json(f"{BASE}/api/v1/portfolio?page_size=300", headers=H)
if status == 200:
    print(f"  Total Accounts    : {port['total_accounts']}")
    print(f"  Avg Stress Score  : {port['avg_stress_score']}")
    print(f"  High Risk (C/D)   : {port['high_risk_count']}")
    print(f"  As of Month       : {port['as_of_month']}")

    # Find MSME00231 in portfolio
    target = next((a for a in port["accounts"] if a["borrower_id"] == BORROWER), None)
    if target:
        print(f"\n  [{BORROWER} in Portfolio]")
        print(f"  Stress Score      : {target['stress_score']}")
        print(f"  Risk Grade        : {target['risk_grade']}")
        print(f"  Prev Grade        : {target.get('risk_grade_prev', 'N/A')}")
        print(f"  Score MoM Delta   : {target.get('stress_score_delta', 'N/A')}")
        print(f"  PD Probability    : {round(target['pd_probability']*100, 2)}%")
    else:
        print(f"\n  [WARN] {BORROWER} not found in first 300 accounts")
else:
    print(f"  [ERROR] Portfolio failed: {status} {port}")
    target = None

# ── 3. Account Detail ─────────────────────────────────────────────────────────
print("\n" + "-"*60)
print("  SEGMENT 2 -- Account Detail & XAI")
print("-"*60)

p_status, p = post_json(f"{BASE}/api/v1/predict", {"borrower_id": BORROWER}, headers=H)
if p_status == 200:
    print(f"  PD Probability    : {round(p['pd_probability']*100, 2)}%")
    print(f"  Stress Score      : {p['stress_score']}")
    print(f"  Risk Grade        : {p['risk_grade']}")
    print(f"  Confidence        : {p.get('confidence_level', 'N/A')}")
else:
    print(f"  [ERROR] Predict failed: {p_status} {p}")

expl_status, e = get_json(f"{BASE}/api/v1/explain/{BORROWER}", headers=H)
if expl_status == 200:
    print(f"\n  SHAP Top Drivers:")
    for i, driver in enumerate(e.get("top_features", [])[:5], 1):
        shap_val = driver.get("shap_value", driver.get("value", "?"))
        feat     = driver.get("feature", driver.get("name", "?"))
        direction = "+" if float(shap_val) > 0 else ""
        print(f"    {i}. {feat:<35} SHAP: {direction}{shap_val}")
    print(f"\n  Narrative: {e.get('narrative_summary', 'N/A')[:120]}...")
elif expl_status == 503 or (isinstance(e, str) and "SHAP explanation model is not fit" in e) or (isinstance(e, dict) and "detail" in e and "not fit" in e["detail"]):
    print("  [WARN] SHAP not available or model not fit yet -- XAI panel will fallback on default values or placeholder drivers on screen")
else:
    print(f"  [ERROR] Explain failed: {expl_status} {e}")

# ── 4. What-If Simulator ──────────────────────────────────────────────────────
print("\n" + "-"*60)
print("  SEGMENT 3 -- What-If Simulator")
print("-"*60)

sim_payload = {
    "borrower_id": BORROWER,
    "hypothetical_changes": {
        "dpd_change": -30,
        "dscr_delta": 0.50,
        "bureau_score_delta": 0,
        "overdraft_utilization_delta": 0.0,
        "gst_delay_days": 0,
        "epfo_change_pct": 0.0
    }
}
sim_status, s = post_json(f"{BASE}/api/v1/simulate", sim_payload, headers=H)
if sim_status == 200:
    print(f"  Original Grade    : {s['original_risk_grade']}")
    print(f"  Simulated Grade   : {s['simulated_risk_grade']}")
    print(f"  Original Stress   : {s['original_stress_score']}")
    print(f"  Simulated Stress  : {s['simulated_stress_score']}")
else:
    print(f"  [ERROR] Simulate failed: {sim_status} {s}")

# ── 5. Model Governance ───────────────────────────────────────────────────────
print("\n" + "-"*60)
print("  SEGMENT 4 -- Model Governance")
print("-"*60)

gov_status, g = get_json(f"{BASE}/api/v1/governance", headers=H)
if gov_status == 200:
    print(f"  Model Version     : {g['model_version']}")
    print(f"  Algorithm         : {g['algorithm']}")
    print(f"  Feature Count     : {g['feature_count']}")
    print(f"  AUC-ROC           : {g['avg_auc_roc']}")
    print(f"  Precision @Top10% : {round(g['avg_precision_at_top10']*100, 2)}%")
    print(f"  Avg Recall        : {round(g['avg_recall']*100, 2)}%")
    print(f"  Fairness Status   : {g.get('fairness_status', 'N/A')}")
else:
    print(f"  [ERROR] Governance failed: {gov_status} {g}")

# ── 6. Cheat Sheet ────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("  DEMO CHEAT SHEET -- FILL THIS IN YOUR SCRIPT")
print("="*60)

if status == 200:
    print(f"  Portfolio accounts       : {port['total_accounts']}")
    print(f"  Avg stress score         : {port['avg_stress_score']}")
if target:
    print(f"  MSME00231 stress score   : {target['stress_score']}")
    print(f"  MSME00231 grade          : {target['risk_grade']}")
if p_status == 200:
    print(f"  MSME00231 PD             : {round(p['pd_probability']*100, 2)}%")
if sim_status == 200:
    print(f"  Post-sim Stress (DPD-30, DSCR+0.5) : {round(s['simulated_stress_score'], 2)}")
    print(f"  Post-sim grade           : {s['simulated_risk_grade']}")
print(f"  Model version            : v2.0.0  (From JSON: {g.get('model_version', 'v2.0.0') if gov_status == 200 else 'v2.0.0'})")
print(f"  AUC-ROC                  : 0.743  (From JSON: {g.get('avg_auc_roc', 0.743) if gov_status == 200 else 0.743})")
print(f"  Precision @Top10%        : 38.87%  (From JSON: {round(g.get('avg_precision_at_top10', 0.3887)*100, 2) if gov_status == 200 else 38.87}%)")
print("\n" + "="*60 + "\n")
