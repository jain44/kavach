import urllib.request
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

# Login
status, login_res = post_json(f"{BASE}/api/v1/auth/login", {"username": "cro", "password": "kavach123", "role": "cro"})
token = login_res["access_token"]
H = {"Authorization": f"Bearer {token}"}

# Let's try different simulation combinations
combos = [
    {
        "desc": "DPD -30, DSCR +0.5",
        "changes": {"dpd_change": -30, "dscr_delta": 0.50}
    },
    {
        "desc": "DPD -30, DSCR +0.5, Bureau +100",
        "changes": {"dpd_change": -30, "dscr_delta": 0.50, "bureau_score_delta": 100}
    },
    {
        "desc": "DPD -30, DSCR +0.5, Bureau +100, OD Util -0.5",
        "changes": {"dpd_change": -30, "dscr_delta": 0.50, "bureau_score_delta": 100, "overdraft_utilization_delta": -0.50}
    },
    {
        "desc": "DPD -30, DSCR +1.0, Bureau +150, OD Util -0.5, EPFO +0.5",
        "changes": {
            "dpd_change": -30,
            "dscr_delta": 1.0,
            "bureau_score_delta": 150,
            "overdraft_utilization_delta": -0.50,
            "epfo_change_pct": 0.5
        }
    }
]

for c in combos:
    payload = {
        "borrower_id": BORROWER,
        "hypothetical_changes": {
            "dpd_change": c["changes"].get("dpd_change", 0),
            "dscr_delta": c["changes"].get("dscr_delta", 0.0),
            "bureau_score_delta": c["changes"].get("bureau_score_delta", 0),
            "overdraft_utilization_delta": c["changes"].get("overdraft_utilization_delta", 0.0),
            "gst_delay_days": c["changes"].get("gst_delay_days", 0),
            "epfo_change_pct": c["changes"].get("epfo_change_pct", 0.0)
        }
    }
    st, res = post_json(f"{BASE}/api/v1/simulate", payload, headers=H)
    if st == 200:
        print(f"{c['desc']}:")
        print(f"  Stress: {res['original_stress_score']} -> {res['simulated_stress_score']}")
        print(f"  Grade:  {res['original_risk_grade']} -> {res['simulated_risk_grade']}")
    else:
        print(f"Failed {c['desc']}: {st} {res}")
