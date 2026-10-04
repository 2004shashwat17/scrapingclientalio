"""Phone/email validation, normalization, dedup and HTML extraction. Offline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.crawlers.contact_extraction import (
    extract_contact_candidates,
    infer_phone_region,
    is_placeholder_email,
    is_placeholder_phone,
    is_valid_email,
    is_valid_phone,
    merge_candidates,
    normalize_email,
    normalize_phone,
    select_contacts,
)

ok = True


def check(label, condition):
    global ok
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    ok = ok and bool(condition)


# 1. Garbage numbers seen in the real CSV must never validate.
GARBAGE_PHONES = [
    "20260713", "20260922", "2147483647", "99999999993", "0000000062",
    "33330003333", "12321233", "1712580978", "55001708708", "046838847847847",
    "20260421", "27062023", "1059616331", "+12001227", "05452430722676",
    "9999999999", "1234567890", "+91 12345 67890", "0000000000", "4294967295",
]
for raw in GARBAGE_PHONES:
    check(f"phone rejected: {raw}", normalize_phone(raw, "IN") is None and not is_valid_phone(raw, "IN"))

for raw in ["9999999999", "0000000062", "2147483647", "1712580978", "20260713", "33330003333"]:
    check(f"placeholder phone detected: {raw}", is_placeholder_phone(raw))

# 2. Valid Indian numbers normalize to E.164.
VALID_PHONES = {
    "+919876543210": "+919876543210",
    "08088321887": "+918088321887",
    "+918088321887": "+918088321887",
    "099009 92060": "+919900992060",
    "080883 21887": "+918088321887",
    "080 8832 1887": "+918088321887",
    "+91 (80) 8832-1887": "+918088321887",
    "tel:+91-99009-92060": "+919900992060",
    "0091 99009 92060": "+919900992060",
    "020 6720 0000": "+912067200000",
}
for raw, expected in VALID_PHONES.items():
    check(f"phone {raw!r} -> {expected}", normalize_phone(raw, "IN") == expected)

# 3. Differently formatted copies of one number collapse to one.
phones, _ = extract_contact_candidates(
    '<a href="tel:080883 21887">Call</a><p>Phone: +918088321887</p><p>Tel: 080 8832 1887</p>',
    region="IN",
)
check("phone variants deduplicated", [p.value for p in phones] == ["+918088321887"])
check("dedup keeps highest-confidence source", phones[0].source == "tel_link")

# 4. Emails.
BAD_EMAILS = [
    "google@3x.png", "you@company.com", "name@company.com", "someone@somewhere.com",
    "hello@company.com", "artboard-1-copy-8@4x.png", "image@2x.png", "logo@4x.png",
    "icon@2x.webp", "style@media.css", "a1b2c3d4e5f60718293a4b5c6d7e8f90@sentry.io",
    "abc@sentry-next.wixpress.com", "info@example.com", "your.email@domain.com",
    "john.doe@acme.in", "noreply@acme.in", "xxx@xxx.com", "user@yourdomain.com",
    "test@acme.in", "firstname.lastname@acme.co.in",
]
for raw in BAD_EMAILS:
    check(f"email rejected: {raw}", not is_valid_email(raw))

for raw in ["you@company.com", "name@company.com", "someone@somewhere.com", "hello@company.com"]:
    check(f"placeholder email detected: {raw}", is_placeholder_email(raw))

GOOD_EMAILS = ["sales@acme.in", "ravi.kumar@acme.co.in", "info@techasoft.com", "acme.logistics@gmail.com"]
for raw in GOOD_EMAILS:
    check(f"email accepted: {raw}", is_valid_email(raw))

check("email normalized + lowercased", normalize_email("mailto:Sales@Company.IN?subject=Hi") == "sales@company.in")

_, emails = extract_contact_candidates(
    '<a href="mailto:Sales@Acme.in">Mail</a><p>Email: sales@acme.in</p><p>SALES@ACME.IN</p>',
    website="https://acme.in",
)
check("emails deduplicated case-insensitively", [e.value for e in emails] == ["sales@acme.in"])

# 5. HTML extraction ignores scripts, styles, image names, attributes and IDs.
HTML = """
<html><head>
<script type="application/ld+json">
 {"@context":"https://schema.org","@type":"LocalBusiness","telephone":"+91 80 4718 2290",
  "email":"hello@acme.in","review":{"@type":"Review","author":{"@type":"Person","telephone":"9845011122"}}}
</script>
<script>var ts=1712580978; var max=2147483647; var img="google@3x.png"; window.id="9845099887";</script>
<style>.a{width:20260713px}</style>
</head><body data-id="9876501234">
<img src="/img/artboard-1-copy-8@4x.png" alt="logo" data-phone="9845066778">
<svg><text>9845000111</text></svg>
<a href="tel:099009 92060">Call us</a>
<a href="mailto:Sales@Acme.in">Mail us</a>
<footer>
 <p><i class="fa fa-phone"></i> 080883 21887</p>
 <p>Founded 2014 | Order no 9845012345 | ID 7621835252 | GSTIN 29ABCDE1234F1Z5</p>
 <p>Email: you@company.com</p>
 <p>Fax: 080 2222 3456</p>
 <p>Rated 4.8 from 2,345 reviews. Updated 20260713.</p>
</footer>
</body></html>
"""
phones, emails = extract_contact_candidates(HTML, page_label="homepage", region="IN", website="https://acme.in")
phone_values = [p.value for p in phones]
email_values = [e.value for e in emails]
check("tel: link captured", "+919900992060" in phone_values)
check("schema.org telephone captured", "+918047182290" in phone_values)
check("icon-labelled footer phone captured", "+918088321887" in phone_values)
check("only genuine phones captured", sorted(phone_values) == sorted(["+919900992060", "+918047182290", "+918088321887"]))
check("mailto + schema emails captured", sorted(email_values) == ["hello@acme.in", "sales@acme.in"])
sources = {p.value: p.source for p in phones}
check("phone sources recorded", sources["+919900992060"] == "tel_link" and sources["+918047182290"] == "schema_org")

# 6. Primary vs All fields.
contacts = select_contacts(phones, emails, "https://acme.in")
check("primary phone is the tel: link", contacts["Phone"] == "+919900992060")
check("PhoneSource / PhoneConfidence set", contacts["PhoneSource"] == "tel_link" and contacts["PhoneConfidence"] == "0.98")
check("primary email is the mailto", contacts["Email"] == "sales@acme.in" and contacts["EmailSource"] == "mailto_link")
check("AllPhones only E.164 values", all(p.startswith("+") for p in contacts["AllPhones"].split(", ")))
check("AllPhones has no duplicates", len(set(contacts["AllPhones"].split(", "))) == 3)

# Low-confidence fallback values may appear in All* but never as the primary.
fallback_phones, fallback_emails = extract_contact_candidates(
    "<p>Our partners: +91 99000 11122 and team@partner.co.in</p>", region="IN", website="https://acme.in"
)
fallback = select_contacts(fallback_phones, fallback_emails, "https://acme.in")
check("fallback phone not primary", fallback["Phone"] == "" and fallback["AllPhones"] == "+919900011122")
check("fallback email not primary", fallback["Email"] == "" and fallback["AllEmails"] == "team@partner.co.in")

# Contact page text counts as a contact source.
cp_phones, _ = extract_contact_candidates("<p>Bengaluru office +91 99000 11122</p>", page_label="ContactPage", region="IN")
check("contact page source", cp_phones and cp_phones[0].source == "contact_page")

# 7. merge keeps the best source for a duplicated value.
from backend.crawlers.contact_extraction import ContactCandidate
merged = merge_candidates([
    ContactCandidate("+919900992060", "visible_text", 0.5),
    ContactCandidate("+919900992060", "google_maps", 0.95),
])
check("merge picks highest confidence", len(merged) == 1 and merged[0].source == "google_maps")

# 8. Region detection.
check("region from address", infer_phone_region("https://acme.com", "Bengaluru, Karnataka, India") == "IN")
check("region from ccTLD", infer_phone_region("https://acme.co.uk", "") == "GB")
check("generic ccTLD falls back to default", infer_phone_region("https://acme.io", "") == "IN")

print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
raise SystemExit(0 if ok else 1)
