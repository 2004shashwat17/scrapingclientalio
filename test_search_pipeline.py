"""Drive SearchService.search_and_save with fakes to prove leads really persist.

Covers the whole path: card -> enrichment -> repository -> CSV.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import backend.storage.csv_store as csv_store
from backend.repositories.lead_repository import LeadRepository
from backend.services.search_service import SearchService

CARDS = [
    # Card already has a website and a phone.
    {"CompanyName": "Alpha Couriers", "Website": "https://alpha-couriers.example",
     "Phone": "+91 98111 11111", "Location": "Pune, Maharashtra"},
    # Card with no website: enrichment supplies one.
    {"CompanyName": "Beta Logistics", "Website": "", "Phone": "+91 98111 22222",
     "Location": "Nashik, Maharashtra"},
    # Nothing usable: should be discarded, not saved.
    {"CompanyName": "", "Website": "", "Phone": "", "Location": ""},
]

ENRICHED = {
    "Alpha Couriers": {"Website": "https://alpha-couriers.example",
                       "Email": "info@alpha-couriers.example", "Phone": "+91 98111 11111"},
    "Beta Logistics": {"Website": "https://beta-logistics.example",
                       "Email": "sales@beta-logistics.example", "Phone": "+91 98111 22222"},
}

ok = True


def check(label, condition):
    global ok
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    ok = ok and bool(condition)


with tempfile.TemporaryDirectory() as tmp:
    csv_store.DATA_DIR = Path(tmp)

    service = SearchService()
    service._ensure_session = lambda: None  # no browser in this test
    service.discovery = type("D", (), {"discover": staticmethod(lambda *a, **k: CARDS),
                                       "_session": None, "close": lambda self: None})()
    service.enricher = type(
        "E", (),
        {"enrich": staticmethod(lambda card, **kw: {
            "CompanyName": card.get("CompanyName", ""),
            "Website": (card.get("Website") or ENRICHED.get(card.get("CompanyName", ""), {}).get("Website", "")),
            "Email": ENRICHED.get(card.get("CompanyName", ""), {}).get("Email", ""),
            "Phone": card.get("Phone", ""),
            "Headquarters": card.get("Location", ""),
            "Industry": kw.get("industry", ""),
            "IsUseful": bool(card.get("CompanyName")) and bool(
                card.get("Phone") or ENRICHED.get(card.get("CompanyName", ""), {}).get("Email")
            ),
            "Notes": "Discovery: Maps card",
        })}
    )()
    service.lead_repo = LeadRepository()

    results = service.search_and_save("courier companies in Pune India", limit=10)

    check("saved both real leads", len(results) == 2)
    check("no-website lead was saved too",
          any(r.get("Website") == "https://beta-logistics.example" for r in results))
    check("all saves returned a LeadId", all(r.get("LeadId") for r in results))

    import csv as _csv
    rows = list(_csv.DictReader((Path(tmp) / "clientalio_leads.csv").open(encoding="utf-8")))
    check("exactly 2 rows on disk", len(rows) == 2)
    check("no blank-company row saved", all(r["CompanyName"] for r in rows))
    check("emails persisted", {r["Email"] for r in rows} == {
        "info@alpha-couriers.example", "sales@beta-logistics.example"})

print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
raise SystemExit(0 if ok else 1)