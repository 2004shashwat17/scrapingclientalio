import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.utils.settings import settings

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(settings.data_dir)
if not DATA_DIR.is_absolute():
    DATA_DIR = BASE_DIR / DATA_DIR
DATA_DIR = DATA_DIR.resolve()
LEADS_FILE = DATA_DIR / "leads.csv"
CRAWL_LOG_FILE = DATA_DIR / "crawl_log.csv"
FAILED_SITES_FILE = DATA_DIR / "failed_sites.csv"

LEAD_FIELDS = [
    "LeadId",
    "CompanyName",
    "Industry",
    "Website",
    "Location",
    "Address",
    "DecisionMakerName",
    "Designation",
    "Email",
    "EmailType",
    "Phone",
    "LinkedIn",
    "Facebook",
    "Instagram",
    "Twitter",
    "YouTube",
    "ContactPage",
    "SourceKeyword",
    "HasTestimonials",
    "HasVideoTestimonials",
    "HasCaseStudies",
    "HasGoogleReviews",
    "LeadScore",
    "Priority",
    "CreatedDate",
]

CRAWL_LOG_FIELDS = ["Website", "Status", "Message", "CreatedDate"]
FAILED_SITE_FIELDS = ["Website", "Status", "Message", "CreatedDate"]


def _ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path, headers in (
        (LEADS_FILE, LEAD_FIELDS),
        (CRAWL_LOG_FILE, CRAWL_LOG_FIELDS),
        (FAILED_SITES_FILE, FAILED_SITE_FIELDS),
    ):
        if not path.exists():
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=headers)
                writer.writeheader()
            continue

        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            existing_header = next(reader, None)

        if existing_header is None:
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=headers)
                writer.writeheader()
            continue

        if existing_header != headers:
            with path.open("r", newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle, fieldnames=existing_header)
                rows = [row for row in reader]
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=headers)
                writer.writeheader()
                for row in rows:
                    writer.writerow({field: row.get(field, "") for field in headers})


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "LeadId": _parse_int(row.get("LeadId")),
        "CompanyName": row.get("CompanyName", ""),
        "Industry": row.get("Industry", ""),
        "Website": row.get("Website", ""),
        "Location": row.get("Location", ""),
        "Address": row.get("Address", ""),
        "DecisionMakerName": row.get("DecisionMakerName", ""),
        "Designation": row.get("Designation", ""),
        "Email": row.get("Email", ""),
        "EmailType": row.get("EmailType", ""),
        "Phone": row.get("Phone", ""),
        "LinkedIn": row.get("LinkedIn", ""),
        "Facebook": row.get("Facebook", ""),
        "Instagram": row.get("Instagram", ""),
        "Twitter": row.get("Twitter", ""),
        "YouTube": row.get("YouTube", ""),
        "ContactPage": row.get("ContactPage", ""),
        "SourceKeyword": row.get("SourceKeyword", ""),
        "HasTestimonials": _parse_bool(row.get("HasTestimonials")),
        "HasVideoTestimonials": _parse_bool(row.get("HasVideoTestimonials")),
        "HasCaseStudies": _parse_bool(row.get("HasCaseStudies")),
        "HasGoogleReviews": _parse_bool(row.get("HasGoogleReviews")),
        "LeadScore": _parse_int(row.get("LeadScore")),
        "Priority": row.get("Priority", "Low Priority"),
        "CreatedDate": row.get("CreatedDate", ""),
    }


def _read_csv(file_path: Path, headers: list[str]) -> list[dict[str, Any]]:
    _ensure_data_files()
    with file_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader]


def _write_csv(file_path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    _ensure_data_files()
    with file_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _append_csv(file_path: Path, row: dict[str, Any], headers: list[str]) -> None:
    _ensure_data_files()
    with file_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writerow(row)


class LeadStore:
    def __init__(self) -> None:
        _ensure_data_files()

    def list(self, offset: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        raw = _read_csv(LEADS_FILE, LEAD_FIELDS)
        parsed = [_parse_row(row) for row in raw]
        return parsed[offset : offset + limit]

    def get_by_id(self, lead_id: int) -> dict[str, Any] | None:
        for row in _read_csv(LEADS_FILE, LEAD_FIELDS):
            parsed = _parse_row(row)
            if parsed["LeadId"] == lead_id:
                return parsed
        return None

    def find_duplicates(self, website: str, email: str | None, company_name: str) -> dict[str, Any] | None:
        for row in _read_csv(LEADS_FILE, LEAD_FIELDS):
            parsed = _parse_row(row)
            if parsed["Website"] == website:
                return parsed
            if email and parsed["Email"] == email:
                return parsed
            if parsed["CompanyName"] == company_name:
                return parsed
        return None

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = _read_csv(LEADS_FILE, LEAD_FIELDS)
        parsed_rows = [_parse_row(row) for row in rows]
        existing = None
        for row in parsed_rows:
            if row["Website"] == payload.get("Website") or (
                payload.get("Email") and row["Email"] == payload.get("Email")
            ) or row["CompanyName"] == payload.get("CompanyName"):
                existing = row
                break

        if existing:
            updated = {
                **existing,
                **{k: v for k, v in payload.items() if v is not None},
                "LeadId": existing["LeadId"],
                "CreatedDate": existing["CreatedDate"],
            }
            new_rows = [updated if row["LeadId"] == existing["LeadId"] else row for row in parsed_rows]
            _write_csv(LEADS_FILE, [_serialize_lead(row) for row in new_rows], LEAD_FIELDS)
            return updated

        next_id = max((row["LeadId"] for row in parsed_rows), default=0) + 1
        now = datetime.utcnow().isoformat()
        lead = {
            "LeadId": next_id,
            "CompanyName": payload.get("CompanyName", ""),
            "Industry": payload.get("Industry", ""),
            "Website": payload.get("Website", ""),
            "Location": payload.get("Location", ""),
            "Address": payload.get("Address", ""),
            "DecisionMakerName": payload.get("DecisionMakerName", ""),
            "Designation": payload.get("Designation", ""),
            "Email": payload.get("Email", ""),
            "EmailType": payload.get("EmailType", ""),
            "Phone": payload.get("Phone", ""),
            "LinkedIn": payload.get("LinkedIn", ""),
            "Facebook": payload.get("Facebook", ""),
            "Instagram": payload.get("Instagram", ""),
            "Twitter": payload.get("Twitter", ""),
            "YouTube": payload.get("YouTube", ""),
            "ContactPage": payload.get("ContactPage", ""),
            "SourceKeyword": payload.get("SourceKeyword", ""),
            "HasTestimonials": payload.get("HasTestimonials", False),
            "HasVideoTestimonials": payload.get("HasVideoTestimonials", False),
            "HasCaseStudies": payload.get("HasCaseStudies", False),
            "HasGoogleReviews": payload.get("HasGoogleReviews", False),
            "LeadScore": payload.get("LeadScore", 0),
            "Priority": payload.get("Priority", "Low Priority"),
            "CreatedDate": now,
        }
        _append_csv(LEADS_FILE, _serialize_lead(lead), LEAD_FIELDS)
        return lead


def _serialize_lead(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "LeadId": row.get("LeadId", ""),
        "CompanyName": row.get("CompanyName", ""),
        "Industry": row.get("Industry", ""),
        "Website": row.get("Website", ""),
        "Location": row.get("Location", ""),
        "Address": row.get("Address", ""),
        "DecisionMakerName": row.get("DecisionMakerName", ""),
        "Designation": row.get("Designation", ""),
        "Email": row.get("Email", ""),
        "EmailType": row.get("EmailType", ""),
        "Phone": row.get("Phone", ""),
        "LinkedIn": row.get("LinkedIn", ""),
        "Facebook": row.get("Facebook", ""),
        "Instagram": row.get("Instagram", ""),
        "Twitter": row.get("Twitter", ""),
        "YouTube": row.get("YouTube", ""),
        "ContactPage": row.get("ContactPage", ""),
        "SourceKeyword": row.get("SourceKeyword", ""),
        "HasTestimonials": bool(row.get("HasTestimonials", False)),
        "HasVideoTestimonials": bool(row.get("HasVideoTestimonials", False)),
        "HasCaseStudies": bool(row.get("HasCaseStudies", False)),
        "HasGoogleReviews": bool(row.get("HasGoogleReviews", False)),
        "LeadScore": row.get("LeadScore", 0),
        "Priority": row.get("Priority", "Low Priority"),
        "CreatedDate": row.get("CreatedDate", ""),
    }


class CrawlLogStore:
    def __init__(self) -> None:
        _ensure_data_files()

    def create(self, website: str, status: str, message: str | None = None) -> dict[str, Any]:
        created_date = datetime.utcnow().isoformat()
        row = {
            "Website": website,
            "Status": status,
            "Message": message or "",
            "CreatedDate": created_date,
        }
        _append_csv(CRAWL_LOG_FILE, row, CRAWL_LOG_FIELDS)
        if status.lower() == "failed":
            _append_csv(FAILED_SITES_FILE, row, FAILED_SITE_FIELDS)
        return row


def ensure_csv_storage() -> None:
    _ensure_data_files()
