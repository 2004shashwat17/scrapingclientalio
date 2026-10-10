"""All scraper-generated API payloads send signUpCompleted as numeric zero."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from push_leads_to_api import DEFAULT_SIGNUP_COMPLETED, build_payload

ok = True


def check(label, condition):
    global ok
    print(f'{"PASS" if condition else "FAIL"}  {label}')
    ok = ok and bool(condition)


ROW = {"Email": "info@acme.com", "CompanyName": "Acme"}

check("default signup completion is numeric zero", DEFAULT_SIGNUP_COMPLETED == 0)
for product in ("Clientalio", "Dropproof", "AnotherProduct"):
    payload = build_payload(
        ROW,
        {"productName": product, "signUpCompleted": 1, "signUpDate": "2026-10-09"},
    )
    check(
        f"{product} payload forces signUpCompleted to zero",
        payload.get("signUpCompleted") == 0 and type(payload["signUpCompleted"]) is int,
    )
    check(f"{product} payload sends signUpDate as null", "signUpDate" in payload and payload["signUpDate"] is None)

payload = build_payload(ROW, {})
check("payload without product metadata sends zero", payload.get("signUpCompleted") == 0)
check("payload without product metadata sends null date", "signUpDate" in payload and payload["signUpDate"] is None)

print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
raise SystemExit(0 if ok else 1)
