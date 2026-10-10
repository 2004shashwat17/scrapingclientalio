"""UserStage is selected by product and cannot be overridden by input."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from push_leads_to_api import DEFAULT_USER_STAGE, DROPPROOF_USER_STAGE, build_payload

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
check("Dropproof uses Prospects stage", payload.get("userStage") == "Prospects")
check("extra input cannot override stage", build_payload(ROW, {"userStage": "lead"})["userStage"] == "PROSPECT")
payload = build_payload(ROW, {"productName": "Dropproof", "userStage": "lead"})
check("extra input cannot override Dropproof stage", payload["userStage"] == DROPPROOF_USER_STAGE)

# Must not interfere with the other fields.
payload = build_payload(ROW, {"productName": "Clientalio"})
check("email unaffected", payload["email"] == "info@acme.com")
check("productName unaffected", payload["productName"] == "Clientalio")

# An invalid email is still rejected before anything is sent.
check("invalid email still rejected", build_payload({"Email": "nope"}, {}) is None)

print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
raise SystemExit(0 if ok else 1)