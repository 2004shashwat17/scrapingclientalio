"""Checks that every email/phone is captured, not just the best one."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.crawlers.utils import collect_all_contacts, extract_emails, extract_phones

ok = True


def check(label, condition):
    global ok
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    ok = ok and bool(condition)


# 1. Several contacts on a page must all survive.
html = """
<footer>
  <p>Call +91 98111 12345 or 020 6720 0000</p>
  <a href="mailto:info@acme.com">info</a>
  <a href="mailto:sales@acme.com">sales</a>
  <a href="mailto:ravi@acme.com">ravi</a>
  <a href="mailto:customercare.india@dhl.com">care</a>
  <p>+91 98111 12345</p>
</footer>
"""
emails = extract_emails(html)
phones = extract_phones(html)

check("all 4 emails extracted", len(emails) == 4)
check("multiple phones extracted", len(phones) >= 2)

all_emails, all_phones = collect_all_contacts(
    emails, phones, "https://acme.com",
    primary_email="info@acme.com", primary_phone="+91 98111 12345",
)
check("every email kept", all(e in all_emails for e in emails))
check("every phone kept", all(p in all_phones for p in phones))
check("primary email listed first", all_emails.startswith("info@acme.com"))
# Phones are stored in their normalised form (+919811112345), not the raw text.
check("primary phone listed first", all_phones.startswith("+919811112345"))

# 2. Duplicates must not be repeated.
# Case-insensitive duplicates must not be repeated.
dupes = collect_all_contacts(
    ["ravi@acme.com", "Ravi@Acme.com", "sales@acme.com"], [], None, "ravi@acme.com", None
)
check("duplicate emails collapsed", dupes[0] == "ravi@acme.com, sales@acme.com")

# 3. Over-long lists are trimmed on a word boundary, never mid-address.
many = [f"person{i}@site{i}.com" for i in range(60)]
trimmed = collect_all_contacts(many, [], None, many[0], None)[0]
check("long list trimmed", len(trimmed) <= 256)
check("trimmed at a comma", trimmed.endswith(".com"))

# 4. It must survive the CSV round-trip.
import backend.storage.csv_store as csv_store
with tempfile.TemporaryDirectory() as tmp:
    csv_store.DATA_DIR = Path(tmp)
    repo = csv_store.LeadStore("clientalio")
    repo.save({
        "CompanyName": "Acme", "Email": "info@acme.com", "Phone": "+919811112345",
        "AllEmails": all_emails, "AllPhones": all_phones,
    })
    row = repo.list(limit=10)[0]
    check("all emails stored in Email column", row["Email"] == all_emails)
    check("all phones stored in Phone column", row["Phone"] == all_phones)
    check("primary email listed first in Email", row["Email"].startswith("info@acme.com"))
    check("no AllEmails/AllPhones columns", "AllEmails" not in csv_store.LEAD_FIELDS
          and "AllPhones" not in csv_store.LEAD_FIELDS)
    check("duplicate detection uses primary email",
          repo.find_duplicates("https://other.example", "info@acme.com", "Other") is not None)

# 5. The push payload carries the extras in Notes.
from push_leads_to_api import append_all_contacts
payload = append_all_contacts(
    {"email": "info@acme.com", "phone": "+91 98111 12345", "notes": "Source keyword: x"},
    {"AllEmails": "info@acme.com, sales@acme.com, ravi@acme.com",
     "AllPhones": "+91 98111 12345, 020 6720 0000"},
)
check("extra emails in notes", "sales@acme.com" in payload["notes"])
check("extra phones in notes", "020 6720 0000" in payload["notes"])
check("primary not duplicated in notes", "info@acme.com," not in payload["notes"])
check("original notes preserved", payload["notes"].startswith("Source keyword: x"))

# 6. A comma-separated Email/Phone row still sends one email + one phone to the API.
from push_leads_to_api import build_payload
api = build_payload({"Email": "info@acme.com, sales@acme.com",
                     "Phone": "+919811112345, +912067200000"}, {})
check("API email is the primary", api["email"] == "info@acme.com")
check("API phone is the primary", api["phone"] == "+919811112345")
check("other contacts go to notes", "sales@acme.com" in api["notes"] and "+912067200000" in api["notes"])

print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
raise SystemExit(0 if ok else 1)