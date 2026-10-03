"""Verify the save path end-to-end without touching the network.

The production run failed with "'LeadRepository' object has no attribute
'save'"; this exercises the real repository/store so that cannot recur.
"""

import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.storage.csv_store import LEAD_FIELDS, LeadStore
from backend.repositories.lead_repository import LeadRepository

SAMPLE = {
    "CompanyName": "Sentinel Couriers Pvt Ltd",
    "Website": "https://sentinel-couriers.example",
    "Headquarters": "Gurugram, Haryana",
    "CitiesServed": "Gurugram, Noida",
    "Industry": "courier companies in Gurugram India",
    "FleetSizePublic": "40",
    "Employees": "65",
    "RevenuePublic": "₹4 Cr",
    "DecisionMakers": "Ravi (Founder)",
    "LinkedInURL": "https://linkedin.com/company/sentinel",
    "Email": "info@sentinel-couriers.example",
    "Phone": "+91 98111 22333",
    "CRMTMSUsedPublic": "Salesforce",
    "DeliveryVolumePublic": "3000/day",
    "ExistingPODSolution": "None",
    "Notes": "Discovery: Maps card, Website found via Google",
}

ok = True


def check(label, condition):
    global ok
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    ok = ok and bool(condition)


with tempfile.TemporaryDirectory() as tmp:
    import backend.storage.csv_store as csv_store

    csv_store.DATA_DIR = Path(tmp)
    csv_store.PRODUCTS["clientalio"]["leads_file"] = "clientalio_leads.csv"

    repo = LeadRepository()  # LeadRepository -> LeadStore -> product CSV

    check("LeadRepository exposes create_or_update", hasattr(repo, "create_or_update"))
    check("LeadRepository has no save()", not hasattr(repo, "save"))

    saved = repo.create_or_update(SAMPLE)
    check("returned a LeadId", bool(saved.get("LeadId")))
    check("kept the email", saved.get("Email") == SAMPLE["Email"])

    store = LeadStore()
    rows = list(csv.DictReader((Path(tmp) / "clientalio_leads.csv").open(encoding="utf-8")))
    check("wrote exactly one row", len(rows) == 1)
    check("header matches LEAD_FIELDS", list(rows[0].keys()) == LEAD_FIELDS)
    check("row kept the company", rows[0]["CompanyName"] == SAMPLE["CompanyName"])

    # Re-saving the same company must update, not duplicate.
    repo.create_or_update({**SAMPLE, "Email": "new@sentinel-couriers.example"})
    rows2 = list(csv.DictReader((Path(tmp) / "clientalio_leads.csv").open(encoding="utf-8")))
    check("second save updated in place", len(rows2) == 1)
    check("email was updated", rows2[0]["Email"] == "new@sentinel-couriers.example")
    check("LeadId stayed stable", rows2[0]["LeadId"] == rows[0]["LeadId"])

    check("find_duplicates matches by website",
          repo.find_duplicates(SAMPLE["Website"], None, "") is not None)

print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
raise SystemExit(0 if ok else 1)