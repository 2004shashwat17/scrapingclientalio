"""Checks for the Maps card address parser (no browser needed)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.crawlers.search_discovery import SearchDiscovery, _looks_like_address

ok = True


def check(label, condition):
    global ok
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    ok = ok and bool(condition)


discovery = SearchDiscovery.__new__(SearchDiscovery)  # no browser needed

# The real failure: Google UI chrome was being read as the address.
chrome_only = "\n".join(["DHL Express (India) Pvt. Ltd", "Courier service", "Saved",
                         "Directions", "Send to phone", "Share"])
check("UI-only text yields no address", discovery._find_address(chrome_only) == "")

labelled = "\n".join([
    "Unique Air Express",
    "Saved",
    "Address: 3rd Floor, Imperium Building, Marol Maroshi Rd, Andheri East, Mumbai 400093",
])
check("reads the line after an Address label",
      discovery._find_address(labelled).startswith("3rd Floor, Imperium"))

unlabelled = "\n".join([
    "Reliable International Courier Services",
    "Saved",
    "Shop 12, Sector 18, Gurugram, Haryana 122015",
])
check("falls back to an address-shaped line",
      discovery._find_address(unlabelled) == "Shop 12, Sector 18, Gurugram, Haryana 122015")

check("'Saved' rejected", not _looks_like_address("Saved"))
check("'Directions' rejected", not _looks_like_address("Directions"))
check("a real address accepted", _looks_like_address("12 MG Road, Pune 411001"))
# Regressions caught on a live Maps run:
check("rating '4.6' rejected", not _looks_like_address("4.6"))
check("review count rejected", not _looks_like_address("1,234"))
check("company name with 'st' inside rejected",
      not _looks_like_address("Unique Air Express, International Courier & Logistics"))

print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
raise SystemExit(0 if ok else 1)