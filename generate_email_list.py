import csv
from pathlib import Path
from typing import Any

CATEGORY_FILES = [
    "agency_founders.csv",
    "saas_founders.csv",
    "coaches.csv",
    "consultants.csv",
    "personal_branding.csv",
    "recruitment.csv",
    "designers.csv",
    "freelancers.csv",
]
LEADS_FILE = Path("data/leads.csv")

OUTPUT_FILE = Path("email_list.csv")
OUTPUT_HEADERS = ["Email"]


def is_valid_email(email: str | None) -> bool:
    if not email:
        return False
    email = email.strip()
    return "@" in email and "." in email and " " not in email


def read_rows(file_path: Path) -> list[dict[str, Any]]:
    if not file_path.exists():
        return []
    with file_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader]


def main() -> None:
    seen = set()
    rows = []

    for filename in CATEGORY_FILES:
        path = Path(filename)
        for row in read_rows(path):
            email = str(row.get("Email", "")).strip()
            if not is_valid_email(email):
                continue
            email_lower = email.lower()
            if email_lower in seen:
                continue
            seen.add(email_lower)
            rows.append({"Email": email})

    for row in read_rows(LEADS_FILE):
        email = str(row.get("Email", "")).strip()
        if not is_valid_email(email):
            continue
        email_lower = email.lower()
        if email_lower in seen:
            continue
        seen.add(email_lower)
        rows.append({"Email": email})

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} unique emails in {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
