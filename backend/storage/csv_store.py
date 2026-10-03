import csv
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from backend.utils.settings import PRODUCTS, settings

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(settings.data_dir)
if not DATA_DIR.is_absolute():
    DATA_DIR = BASE_DIR / DATA_DIR
DATA_DIR = DATA_DIR.resolve()
CRAWL_LOG_FILE = DATA_DIR / "crawl_log.csv"
FAILED_SITES_FILE = DATA_DIR / "failed_sites.csv"


def get_leads_file(product_key: str | None = None) -> Path:
    """Resolve the leads CSV for a product, e.g. data/clientalio_leads.csv."""
    key = product_key or settings.active_product
    product = PRODUCTS.get(key, PRODUCTS["clientalio"])
    return DATA_DIR / product["leads_file"]


def set_active_product(product_key: str) -> None:
    """Switch which product's leads CSV the store reads and writes."""
    if product_key not in PRODUCTS:
        raise ValueError(f"Unknown product '{product_key}'. Choose from: {', '.join(PRODUCTS)}")
    settings.active_product = product_key

LEAD_FIELDS = [
    "LeadId",
    "CompanyName",
    "Website",
    "Headquarters",
    "CitiesServed",
    "Industry",
    "FleetSizePublic",
    "Employees",
    "RevenuePublic",
    "DecisionMakers",
    "LinkedInURL",
    "Email",
    "Phone",
    "CRMTMSUsedPublic",
    "DeliveryVolumePublic",
    "ExistingPODSolution",
    "Notes",
    "CreatedDate",
]

CRAWL_LOG_FIELDS = ["Website", "Status", "Message", "CreatedDate"]
FAILED_SITE_FIELDS = ["Website", "Status", "Message", "CreatedDate"]


def _ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path, headers in (
        *[(get_leads_file(key), LEAD_FIELDS) for key in PRODUCTS],
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


def _parse_optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _parse_optional_email(value: Any) -> str | None:
    text = _parse_optional_text(value)
    if text:
        return unquote(text).strip() or None
    return None


def _parse_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "LeadId": _parse_int(row.get("LeadId")),
        "CompanyName": row.get("CompanyName", ""),
        "Website": row.get("Website", ""),
        "Headquarters": _parse_optional_text(row.get("Headquarters")),
        "CitiesServed": _parse_optional_text(row.get("CitiesServed")),
        "Industry": _parse_optional_text(row.get("Industry")),
        "FleetSizePublic": _parse_optional_text(row.get("FleetSizePublic")),
        "Employees": _parse_optional_text(row.get("Employees")),
        "RevenuePublic": _parse_optional_text(row.get("RevenuePublic")),
        "DecisionMakers": _parse_optional_text(row.get("DecisionMakers")),
        "LinkedInURL": _parse_optional_text(row.get("LinkedInURL")),
        "Email": _parse_optional_email(row.get("Email")),
        "Phone": _parse_optional_text(row.get("Phone")),
        "CRMTMSUsedPublic": _parse_optional_text(row.get("CRMTMSUsedPublic")),
        "DeliveryVolumePublic": _parse_optional_text(row.get("DeliveryVolumePublic")),
        "ExistingPODSolution": _parse_optional_text(row.get("ExistingPODSolution")),
        "Notes": _parse_optional_text(row.get("Notes")),
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
    def __init__(self, product_key: str | None = None) -> None:
        _ensure_data_files()
        self.product_key = product_key or settings.active_product
        self.leads_file = get_leads_file(self.product_key)

    def list(self, offset: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        raw = _read_csv(self.leads_file, LEAD_FIELDS)
        parsed = [_parse_row(row) for row in raw]
        return parsed[offset : offset + limit]

    def get_by_id(self, lead_id: int) -> dict[str, Any] | None:
        for row in _read_csv(self.leads_file, LEAD_FIELDS):
            parsed = _parse_row(row)
            if parsed["LeadId"] == lead_id:
                return parsed
        return None

    def find_duplicates(self, website: str, email: str | None, company_name: str) -> dict[str, Any] | None:
        for row in _read_csv(self.leads_file, LEAD_FIELDS):
            parsed = _parse_row(row)
            if parsed["Website"] == website:
                return parsed
            if email and parsed["Email"] == email:
                return parsed
            if parsed["CompanyName"] == company_name:
                return parsed
        return None

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = _read_csv(self.leads_file, LEAD_FIELDS)
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
            _write_csv(self.leads_file, [_serialize_lead(row) for row in new_rows], LEAD_FIELDS)
            return updated

        next_id = max((row["LeadId"] for row in parsed_rows), default=0) + 1
        now = datetime.utcnow().isoformat()
        lead = {
            "LeadId": next_id,
            "CompanyName": payload.get("CompanyName", ""),
            "Website": payload.get("Website", ""),
            "Headquarters": payload.get("Headquarters", ""),
            "CitiesServed": payload.get("CitiesServed", ""),
            "Industry": payload.get("Industry", ""),
            "FleetSizePublic": payload.get("FleetSizePublic", ""),
            "Employees": payload.get("Employees", ""),
            "RevenuePublic": payload.get("RevenuePublic", ""),
            "DecisionMakers": payload.get("DecisionMakers", ""),
            "LinkedInURL": payload.get("LinkedInURL", ""),
            "Email": payload.get("Email", ""),
            "Phone": payload.get("Phone", ""),
            "CRMTMSUsedPublic": payload.get("CRMTMSUsedPublic", ""),
            "DeliveryVolumePublic": payload.get("DeliveryVolumePublic", ""),
            "ExistingPODSolution": payload.get("ExistingPODSolution", ""),
            "Notes": payload.get("Notes", ""),
            "CreatedDate": now,
        }
        _append_csv(self.leads_file, _serialize_lead(lead), LEAD_FIELDS)
        return lead


def _serialize_lead(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "LeadId": row.get("LeadId", ""),
        "CompanyName": row.get("CompanyName", ""),
        "Website": row.get("Website", ""),
        "Headquarters": row.get("Headquarters", ""),
        "CitiesServed": row.get("CitiesServed", ""),
        "Industry": row.get("Industry", ""),
        "FleetSizePublic": row.get("FleetSizePublic", ""),
        "Employees": row.get("Employees", ""),
        "RevenuePublic": row.get("RevenuePublic", ""),
        "DecisionMakers": row.get("DecisionMakers", ""),
        "LinkedInURL": row.get("LinkedInURL", ""),
        "Email": row.get("Email", ""),
        "Phone": row.get("Phone", ""),
        "CRMTMSUsedPublic": row.get("CRMTMSUsedPublic", ""),
        "DeliveryVolumePublic": row.get("DeliveryVolumePublic", ""),
        "ExistingPODSolution": row.get("ExistingPODSolution", ""),
        "Notes": row.get("Notes", ""),
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
