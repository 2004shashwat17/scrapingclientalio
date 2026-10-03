"""Live check of Google Maps card discovery (the first stage of the pipeline).

Verifies the selectors still match the real page after the captcha refactor:
a fresh browser, no cookie history and no consent decision.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.crawlers.search_discovery import SearchDiscovery
from backend.utils.settings import settings

QUERY = "courier companies in Pune India"

print(f"headless={settings.headless} profile={settings.browser_profile_dir}\n")

discovery = SearchDiscovery()
try:
    cards = discovery.discover(QUERY, limit=3)
    print(f"\nCARDS RETURNED: {len(cards)}")
    for card in cards:
        print("  name    :", (card.get("CompanyName") or "")[:50])
        print("  website :", (card.get("Website") or "(none)")[:60])
        print("  phone   :", card.get("Phone") or "(none)")
        print("  location:", (card.get("Location") or "")[:50])
        print("  email   :", card.get("Email") or "(none)")
        print()
finally:
    discovery.close()