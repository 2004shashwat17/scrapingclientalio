import csv
from pathlib import Path
from typing import Any

from backend.utils.email_sender import build_outreach_email, is_valid_email

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

OUTPUT_FILE = Path("email_outreach.csv")
OUTPUT_HEADERS = [
    "LeadId",
    "CompanyName",
    "Website",
    "Industry",
    "Category",
    "Email",
    "LinkedIn",
    "Facebook",
    "Instagram",
    "Twitter",
    "YouTube",
    "ContactPage",
    "TemplateKey",
    "Subject",
    "Body",
    "PersonalizedIntro",
    "LinkedInFollow",
    "LinkedInConnect",
    "InstagramFollow",
    "SendEmail",
]


def read_rows(file_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not file_path.exists():
        return rows
    with file_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(row)
    return rows


def build_output_rows() -> list[dict[str, Any]]:
    output_rows: list[dict[str, Any]] = []
    seen = set()

    for filename in CATEGORY_FILES:
        file_path = Path(filename)
        for row in read_rows(file_path):
            email = row.get("Email", "").strip()
            if not is_valid_email(email):
                continue
            key = (email.lower(), row.get("Website", "").strip().lower())
            if key in seen:
                continue
            seen.add(key)

            category = row.get("Category", "")
            company = row.get("CompanyName", "")
            name = company.split("|")[0].strip() if company else ""
            outreach = build_outreach_email(
                name=name or "there",
                recipient_email=email,
                company=company,
                category=category,
            )

            output_rows.append(
                {
                    "LeadId": row.get("LeadId", ""),
                    "CompanyName": company,
                    "Website": row.get("Website", ""),
                    "Industry": row.get("Industry", ""),
                    "Category": category,
                    "Email": email,
                    "LinkedIn": row.get("LinkedIn", ""),
                    "Facebook": row.get("Facebook", ""),
                    "Instagram": row.get("Instagram", ""),
                    "Twitter": row.get("Twitter", ""),
                    "YouTube": row.get("YouTube", ""),
                    "ContactPage": row.get("ContactPage", ""),
                    "TemplateKey": outreach["template_key"],
                    "Subject": outreach["subject"],
                    "Body": outreach["body"],
                    "PersonalizedIntro": outreach["personalized_intro"],
                    "LinkedInFollow": bool(row.get("LinkedIn", "").strip()),
                    "LinkedInConnect": bool(row.get("LinkedIn", "").strip()),
                    "InstagramFollow": bool(row.get("Instagram", "").strip()),
                    "SendEmail": True,
                }
            )
    return output_rows


def write_output(rows: list[dict[str, Any]]) -> None:
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = build_output_rows()
    write_output(rows)
    print(f"Generated {len(rows)} outreach rows in {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
