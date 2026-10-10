"""Every scraper-generated API payload defaults source to "scraper"."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from push_leads_to_api import DEFAULT_SOURCE, build_payload

ok = True


def check(label, condition):
    global ok
    print(f'{"PASS" if condition else "FAIL"}  {label}')
    ok = ok and bool(condition)


ROW = {"Email": "info@acme.com", "CompanyName": "Acme"}

check("default source is scraper", DEFAULT_SOURCE == "scraper")
for product in ("Clientalio", "Dropproof", "AnotherProduct"):
    payload = build_payload(ROW, {"productName": product})
    check(f"{product} payload sends scraper source", payload.get("source") == "scraper")

payload = build_payload(ROW, {})
check("payload without extra options sends scraper source", payload.get("source") == "scraper")

print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
raise SystemExit(0 if ok else 1)
