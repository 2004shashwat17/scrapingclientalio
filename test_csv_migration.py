"""Regression test for the CSV schema migration.

A migration bug once added a duplicate header row on every run, because
DictReader was given explicit fieldnames and therefore read the header as data.
"""

import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import backend.storage.csv_store as csv_store

ok = True


def check(label, condition):
    global ok
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    ok = ok and bool(condition)


OLD_HEADER = [
    "LeadId", "CompanyName", "Website", "Headquarters", "CitiesServed", "Industry",
    "FleetSizePublic", "Employees", "RevenuePublic", "DecisionMakers", "LinkedInURL",
    "Email", "Phone", "CRMTMSUsedPublic", "DeliveryVolumePublic",
    "ExistingPODSolution", "Notes", "CreatedDate",
]

with tempfile.TemporaryDirectory() as tmp:
    csv_store.DATA_DIR = Path(tmp)
    leads = Path(tmp) / "clientalio_leads.csv"

    # Write a file in the OLD schema, as an existing deployment would have.
    with leads.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OLD_HEADER)
        writer.writeheader()
        for i in range(1, 6):
            writer.writerow({
                "LeadId": i, "CompanyName": f"Company {i}",
                "Website": f"https://c{i}.example", "Email": f"a{i}@c{i}.example",
                "Phone": f"+9198111{i:04d}", "Notes": f"note {i}",
            })

    def header_count():
        with leads.open(encoding="utf-8") as handle:
            return sum(1 for line in handle if line.startswith("LeadId,"))

    check("starts with one header", header_count() == 1)

    csv_store._ensure_data_files()
    check("still one header after migration", header_count() == 1)

    # Running it repeatedly must not keep appending headers.
    for _ in range(3):
        csv_store._ensure_data_files()
    check("idempotent across 4 runs", header_count() == 1)

    rows = list(csv.DictReader(leads.open(encoding="utf-8")))
    check("all 5 data rows kept", len(rows) == 5)
    check("new columns present", "AllEmails" in rows[0] and "AllPhones" in rows[0])
    check("no row is a header row", rows[0]["CompanyName"] == "Company 1")
    check("emails preserved", rows[0]["Email"] == "a1@c1.example")
    check("phones preserved", rows[0]["Phone"] == "+91981110001")
    check("no data lost to the new columns", rows[2]["Notes"] == "note 3")

print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
raise SystemExit(0 if ok else 1)