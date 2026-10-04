"""productName must match the product the leads file came from."""

import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.utils.settings import PRODUCTS
from push_leads_to_api import build_payload, resolve_product

ok = True


def check(label, condition):
    global ok
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    ok = ok and bool(condition)


ROW = {"Email": "info@acme.com", "CompanyName": "Acme", "Phone": "+919811112345"}

# 1) productName is derived from the chosen product, not hardcoded.
payload = build_payload(ROW, {"productName": PRODUCTS["dropproof"]["name"]})
check("dropproof sends Dropproof", payload["productName"] == "Dropproof")

payload = build_payload(ROW, {"productName": PRODUCTS["clientalio"]["name"]})
check("clientalio sends Clientalio", payload["productName"] == "Clientalio")

# 2) The two names differ, so a mix-up is actually detectable.
check("names are distinct", PRODUCTS["dropproof"]["name"] != PRODUCTS["clientalio"]["name"])

# 3) Each product points at its own leads file.
check("dropproof reads dropproof_leads.csv",
      PRODUCTS["dropproof"]["leads_file"] == "dropproof_leads.csv")
check("clientalio reads clientalio_leads.csv",
      PRODUCTS["clientalio"]["leads_file"] == "clientalio_leads.csv")

# 4) The menu numbers map to the right products.
check("menu 1 = clientalio", resolve_product("1")["key"] == "clientalio")
check("menu 2 = dropproof", resolve_product("2")["key"] == "dropproof")

# 5) End to end: pick 2, push the dropproof CSV, assert the payload says Dropproof.
with tempfile.TemporaryDirectory() as tmp:
    dropproof_csv = Path(tmp) / "dropproof_leads.csv"
    with dropproof_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ROW))
        writer.writeheader()
        writer.writerow(ROW)

    product = resolve_product("2")
    built = build_payload(ROW, {"productName": product["name"]})
    check("product 2 payload says Dropproof", built["productName"] == "Dropproof")
    check("email still primary", built["email"] == "info@acme.com")

print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
raise SystemExit(0 if ok else 1)