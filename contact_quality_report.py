"""Before/after contact-data quality report for a leads CSV.

    .venv/bin/python contact_quality_report.py                      # re-validate existing CSV values
    .venv/bin/python contact_quality_report.py --recrawl 10         # also re-crawl 10 sites live

Read-only: the leads CSV is never modified.
"""

import argparse
import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.crawlers.contact_extraction import (  # noqa: E402
    infer_phone_region,
    is_valid_email,
    normalize_email,
    normalize_phone,
)
from backend.storage.csv_store import get_leads_file  # noqa: E402


def split_values(value: str) -> list[str]:
    return [part.strip() for part in (value or "").replace(";", ",").split(",") if part.strip()]


def revalidate(rows: list[dict]) -> None:
    stats = dict.fromkeys([
        "before_phone", "before_email", "before_both", "after_phone", "after_email", "after_both",
        "phones_seen", "phones_invalid", "phones_dupe", "emails_seen", "emails_invalid", "emails_dupe",
    ], 0)
    accepted_phones, rejected_phones, accepted_emails, rejected_emails = {}, set(), set(), set()

    for row in rows:
        region = infer_phone_region(row.get("Website"), row.get("Headquarters"))
        had_phone, had_email = bool(row.get("Phone", "").strip()), bool(row.get("Email", "").strip())
        stats["before_phone"] += had_phone
        stats["before_email"] += had_email
        stats["before_both"] += had_phone and had_email

        valid_phones: list[str] = []
        for raw in split_values(row.get("Phone", "")) + split_values(row.get("AllPhones", "")):
            raw = raw.strip()
            if not raw:
                continue
            stats["phones_seen"] += 1
            phone = normalize_phone(raw, region)
            if not phone:
                stats["phones_invalid"] += 1
                rejected_phones.add(raw.replace("\n", " "))
            elif phone in valid_phones:
                stats["phones_dupe"] += 1
            else:
                valid_phones.append(phone)
                accepted_phones[raw] = phone

        valid_emails: list[str] = []
        for raw in split_values(row.get("Email", "")) + split_values(row.get("AllEmails", "")):
            raw = raw.strip()
            if not raw:
                continue
            stats["emails_seen"] += 1
            email = normalize_email(raw)
            if not email or not is_valid_email(email):
                stats["emails_invalid"] += 1
                rejected_emails.add(raw)
            elif email in valid_emails:
                stats["emails_dupe"] += 1
            else:
                valid_emails.append(email)
                accepted_emails.add(email)

        stats["after_phone"] += bool(valid_phones)
        stats["after_email"] += bool(valid_emails)
        stats["after_both"] += bool(valid_phones) and bool(valid_emails)

    total = len(rows) or 1
    print("\n=== Re-validation of existing CSV values ===")
    print(f"{'metric':<38}{'before':>10}{'after':>10}")
    print(f"{'total leads':<38}{len(rows):>10}{len(rows):>10}")
    print(f"{'leads with phone':<38}{stats['before_phone']:>10}{stats['after_phone']:>10}")
    print(f"{'leads with email':<38}{stats['before_email']:>10}{stats['after_email']:>10}")
    print(f"{'leads with both':<38}{stats['before_both']:>10}{stats['after_both']:>10}")
    before_usable = sum(1 for r in rows if r.get("Phone", "").strip() or r.get("Email", "").strip())
    after_usable = sum(
        1 for r in rows
        if any(normalize_phone(v, infer_phone_region(r.get("Website"), r.get("Headquarters")))
               for v in split_values(r.get("Phone", "")) + split_values(r.get("AllPhones", "")))
        or any(is_valid_email(v) for v in split_values(r.get("Email", "")) + split_values(r.get("AllEmails", "")))
    )
    print(f"{'% leads with usable contact':<38}{100 * before_usable / total:>9.1f}%{100 * after_usable / total:>9.1f}%")
    print(f"\nphone values seen: {stats['phones_seen']}, invalid removed: {stats['phones_invalid']}, "
          f"duplicates removed: {stats['phones_dupe']}")
    print(f"email values seen: {stats['emails_seen']}, invalid removed: {stats['emails_invalid']}, "
          f"duplicates removed: {stats['emails_dupe']}")

    print("\nAccepted phones (raw -> E.164):")
    for raw, phone in list(accepted_phones.items())[:10]:
        print(f"  {raw!r:<28} -> {phone}")
    print("Rejected phone candidates:")
    for raw in sorted(rejected_phones)[:15]:
        print(f"  {raw!r}")
    print("Accepted emails:")
    for email in sorted(accepted_emails)[:10]:
        print(f"  {email}")
    print("Rejected email candidates:")
    for raw in sorted(rejected_emails)[:15]:
        print(f"  {raw!r}")


def recrawl(rows: list[dict], count: int, seed: int) -> None:
    from backend.crawlers.website_crawler import WebsiteCrawler

    crawler = WebsiteCrawler()
    sample = random.Random(seed).sample([r for r in rows if r.get("Website")], min(count, len(rows)))
    totals = {"old_phone": 0, "new_phone": 0, "old_email": 0, "new_email": 0, "old_all_p": 0, "new_all_p": 0,
              "old_all_e": 0, "new_all_e": 0, "failed": 0}
    print(f"\n=== Live re-crawl of {len(sample)} sample websites (new extractor) ===")
    for row in sample:
        website = row["Website"]
        try:
            new = crawler.crawl(website, address=row.get("Headquarters"))
        except Exception as exc:
            totals["failed"] += 1
            print(f"\n{row.get('CompanyName')} <{website}>  crawl failed: {str(exc)[:80]}")
            continue
        totals["old_phone"] += bool(row.get("Phone"))
        totals["new_phone"] += bool(new.get("Phone"))
        totals["old_email"] += bool(row.get("Email"))
        totals["new_email"] += bool(new.get("Email"))
        totals["old_all_p"] += len(split_values(row.get("AllPhones", "")))
        totals["new_all_p"] += len(split_values(new.get("AllPhones", "")))
        totals["old_all_e"] += len(split_values(row.get("AllEmails", "")))
        totals["new_all_e"] += len(split_values(new.get("AllEmails", "")))
        print(f"\n{row.get('CompanyName')} <{website}>")
        print(f"  BEFORE Phone={row.get('Phone', '')!r} AllPhones={row.get('AllPhones', '')[:90]!r}")
        print(f"  AFTER  Phone={new['Phone']!r} ({new['PhoneSource']} {new['PhoneConfidence']}) "
              f"AllPhones={new['AllPhones']!r}")
        print(f"  BEFORE Email={row.get('Email', '')!r} AllEmails={row.get('AllEmails', '')[:90]!r}")
        print(f"  AFTER  Email={new['Email']!r} ({new['EmailSource']} {new['EmailConfidence']}) "
              f"AllEmails={new['AllEmails']!r}")
    print("\nRe-crawl totals (crawled sites only; Maps-card phones are not part of a website crawl):")
    for key, value in totals.items():
        print(f"  {key:<10} {value}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--product", default="clientalio")
    parser.add_argument("--recrawl", type=int, default=0, help="Live re-crawl N sample websites")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    path = get_leads_file(args.product)
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    print(f"Leads file: {path} ({len(rows)} rows)")
    revalidate(rows)
    if args.recrawl:
        recrawl(rows, args.recrawl, args.seed)


if __name__ == "__main__":
    main()
