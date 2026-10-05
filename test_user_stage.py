"""UserStage must be hard-coded as 'PROSPECT' on every payload."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from push_leads_to_api import DEFAULT_USER_STAGE, build_payload

ok = True


def check(label, condition):
    global ok
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    ok = ok and bool(condition)


ROW = {"Email": "info@acme.com", "CompanyName": "Acme", "Phone": "+919811112345"}

check("default constant is uppercase PROSPECT", DEFAULT_USER_STAGE == "PROSPECT")

payload = build_payload(ROW, {"productName": "Clientalio"})
check("userStage sent by default", payload.get("userStage") == "PROSPECT")

payload = build_payload(ROW, {"productName": "Dropproof"})
check("userStage sent for dropproof too", payload.get("userStage") == "PROSPECT")
check("extra input cannot override stage", build_payload(ROW, {"userStage": "lead"})["userStage"] == "PROSPECT")

# Must not interfere with the other fields.
payload = build_payload(ROW, {"productName": "Clientalio"})
check("email unaffected", payload["email"] == "info@acme.com")
check("productName unaffected", payload["productName"] == "Clientalio")

# An invalid email is still rejected before anything is sent.
check("invalid email still rejected", build_payload({"Email": "nope"}, {}) is None)

print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
raise SystemExit(0 if ok else 1)