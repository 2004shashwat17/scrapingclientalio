#!/usr/bin/env python3
"""Push data/leads.csv rows to the Lead Capture API, one lead per request.

Endpoint: POST {base_url}/api/v1/Lead/LeadCapture

Named targets (--target):
    deployed  https://apiclientalio.azurewebsites.net   production Azure App Service
    local     http://localhost:5023                     local dev, plain HTTP (preferred)
    local-https https://localhost:7293                  local dev over the dev cert

A raw URL can also be passed to --target/--base-url. Multiple targets may be
given; leads are sent to each in turn. Per-lead results are written to a
separate file per target so the runs stay independent.

The endpoint returns HTTP 200 even on business failures, so every response is
branched on the `success` field of the APIResponse envelope, not on the status
code alone.

Usage:
    python push_leads_to_api.py --dry-run
    python push_leads_to_api.py --target local --limit 20
    python push_leads_to_api.py --target deployed local --delay 1.5 --resume

Note: the deployed build may predate the 18 newer payload fields; unknown JSON
properties are dropped silently by ASP.NET Core, so enrichment fields can be
accepted without error yet not persist until the API is redeployed.
"""

import argparse
import csv
import json
import time
from pathlib import Path

import requests
from email_validator import EmailNotValidError, validate_email

DATA_DIR = Path(__file__).resolve().parent / "data"
LEADS_FILE = DATA_DIR / "leads.csv"
RESULTS_FILE = DATA_DIR / "lead_push_results.csv"

API_PATH = "/api/v1/Lead/LeadCapture"

# Named environments. Keep in sync with Properties/launchSettings.json.
TARGETS = {
    "deployed": "https://apiclientalio.azurewebsites.net",
    "local": "http://localhost:5023",
    "local-https": "https://localhost:7293",
}
DEFAULT_TARGET = "deployed"

# CSV column -> LeadCaptureRequest field. Columns not listed here (LeadId,
# CreatedDate) are server-managed and never sent.
FIELD_MAP = {
    "Email": "email",
    "CompanyName": "companyName",
    "Website": "website",
    "Headquarters": "headquarters",
    "CitiesServed": "citiesServed",
    "Industry": "industry",
    "FleetSizePublic": "fleetSizePublic",
    "Employees": "employees",
    "RevenuePublic": "revenuePublic",
    "DecisionMakers": "decisionMakers",
    "LinkedInURL": "linkedinURL",
    "Phone": "phone",
    "CRMTMSUsedPublic": "crmtmsUsedPublic",
    "DeliveryVolumePublic": "deliveryVolumePublic",
    "ExistingPODSolution": "existingPODSolution",
    "Notes": "notes",
}

# Optional UTM-style fields, settable via CLI so every lead carries attribution.
EXTRA_DEFAULTS = {
    "visitorId": None,
    "landingPage": None,
    "source": None,
    "medium": None,
    "campaign": None,
    "content": None,
    "term": None,
    "referrer": None,
    "productName": "Dropproof",
}

MAX_LENGTHS = {
    "email": 256,
    "companyName": 256,
    "website": 256,
    "headquarters": 128,
    "citiesServed": 512,
    "industry": 128,
    "fleetSizePublic": 128,
    "employees": 128,
    "revenuePublic": 128,
    "decisionMakers": 512,
    "linkedinURL": 256,
    "phone": 32,
    "crmtmsUsedPublic": 128,
    "deliveryVolumePublic": 128,
    "existingPODSolution": 256,
    "notes": 2000,
}

RESULT_FIELDS = ["Email", "Status", "Message", "ErrorType", "AlreadyCompleted"]


def clean(value, field):
    """Strip whitespace and enforce the API's max length by truncation."""
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    limit = MAX_LENGTHS.get(field)
    return value[:limit] if limit else value


def build_payload(row, extra):
    """Map a CSV row to a LeadCaptureRequest body. Returns None if no valid email."""
    payload = {}
    for column, field in FIELD_MAP.items():
        value = clean(row.get(column), field)
        if value is not None:
            payload[field] = value

    for field, value in extra.items():
        if value:
            payload[field] = value

    email = payload.get("email")
    if not email:
        return None
    try:
        # check_deliverability=False: syntax only, no DNS/MX round-trip.
        payload["email"] = validate_email(email, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        return None
    return payload


def load_done_emails(path):
    if not path.exists():
        return set()
    done = set()
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("Status") in {"success", "invalid_email"} and row.get("Email"):
                done.add(row["Email"].strip().lower())
    return done


def append_result(handle, record):
    writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
    if handle.tell() == 0:
        writer.writeheader()
    writer.writerow(record)


def post_lead(session, url, payload, retries):
    """Return (status, message, error_type, already_completed)."""
    for attempt in range(retries + 1):
        try:
            response = session.post(url, json=payload, timeout=30)
        except requests.RequestException as exc:
            if attempt == retries:
                return "error", f"Network error: {exc}", "Network", ""
            time.sleep(2 ** attempt)
            continue

        if not response.ok:
            if response.status_code >= 500 and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            return "error", f"HTTP {response.status_code}", f"HTTP{response.status_code}", ""

        try:
            body = response.json()
        except ValueError:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            return "error", "Non-JSON response", "Parse", ""

        # HTTP 200 is not success: branch on the envelope's success flag.
        if body.get("success"):
            data = body.get("data") or {}
            already = str(bool(data.get("alreadyCompleted"))).lower()
            return "success", body.get("message") or "", body.get("errortype") or "None", already

        message = body.get("message") or "Lead capture failed."
        if attempt < retries:
            time.sleep(2 ** attempt)
            continue
        return "error", message, body.get("errortype") or "None", ""

    return "error", "Exhausted retries", "Retry", ""


def results_path_for(base_path: Path, label: str) -> Path:
    """One results file per target so local and deployed runs stay independent."""
    return base_path.with_name(f"{base_path.stem}_{label}{base_path.suffix}")


def resolve_targets(args) -> list:
    """Return [(label, base_url)] for the requested targets, preserving order."""
    requested = [item for group in (args.target or []) for item in group] or [DEFAULT_TARGET]
    if args.base_url:
        requested = [args.base_url]
    targets = []
    for item in requested:
        if item in TARGETS:
            targets.append((item, TARGETS[item]))
        elif "://" in item:
            label = item.split("://", 1)[1].replace("/", "_").replace(":", "_")
            targets.append((label, item.rstrip("/")))
        else:
            raise SystemExit(
                f"Unknown target '{item}'. Choose from: {', '.join(TARGETS)}, or pass a full URL."
            )
    return targets


def preflight(session, label, base_url) -> bool:
    """Probe the API root so an unreachable target fails before any lead is sent."""
    try:
        response = session.get(f"{base_url.rstrip('/')}/", timeout=10)
        print(f"[{label}] preflight {base_url} -> HTTP {response.status_code}")
        return True
    except requests.RequestException as exc:
        print(f"[{label}] preflight FAILED for {base_url}: {exc}")
        return False


def print_dry_run(rows, extra) -> dict:
    """Build and print payloads without sending or touching the results file."""
    counters = {"success": 0, "error": 0, "invalid_email": 0, "skipped": 0}
    for index, row in enumerate(rows, start=1):
        raw_email = (row.get("Email") or "").strip()
        payload = build_payload(row, extra)
        if payload is None:
            counters["invalid_email"] += 1
            print(f"[{index}/{len(rows)}] invalid_email  {raw_email or '<blank>'}")
            continue
        counters["success"] += 1
        print(f"[{index}/{len(rows)}] ok             {json.dumps(payload, ensure_ascii=False)}")
    return counters


def run_target(args, label, base_url, rows, extra) -> dict:
    """Push every row to one target. Returns that target's counters."""
    results_file = results_path_for(args.results_file, label)
    url = base_url.rstrip("/") + API_PATH
    done = load_done_emails(results_file) if args.resume else set()
    counters = {"success": 0, "error": 0, "invalid_email": 0, "skipped": 0}

    print(f"\n=== {label} -> {url} (results: {results_file.name}) ===")

    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "clientalio-lead-pusher/1.0",
    })

    if not args.dry_run and not preflight(session, label, base_url):
        return counters

    if args.dry_run:
        return print_dry_run(rows, extra)

    with results_file.open("a", newline="", encoding="utf-8") as results:
        for index, row in enumerate(rows, start=1):
            raw_email = (row.get("Email") or "").strip()
            if raw_email and raw_email.lower() in done:
                counters["skipped"] += 1
                continue

            payload = build_payload(row, extra)
            if payload is None:
                counters["invalid_email"] += 1
                append_result(results, {
                    "Email": raw_email, "Status": "invalid_email",
                    "Message": "Missing or invalid email", "ErrorType": "Validation",
                    "AlreadyCompleted": "",
                })
                results.flush()
                print(f"[{index}/{len(rows)}] invalid_email  {raw_email or '<blank>'}")
                continue

            status, message, error_type, already = post_lead(session, url, payload, args.retries)
            counters[status] += 1
            append_result(results, {
                "Email": payload["email"], "Status": status, "Message": message,
                "ErrorType": error_type, "AlreadyCompleted": already,
            })
            results.flush()
            print(f"[{index}/{len(rows)}] {status:<12} {payload['email']} - {message}")
            if args.delay:
                time.sleep(args.delay)

    return counters


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--target", action="append", nargs="+", metavar="NAME_OR_URL",
        help=f"Environment to post to; repeatable. One of: {', '.join(TARGETS)}, or a full URL. Default: {DEFAULT_TARGET}",
    )
    parser.add_argument("--base-url", default=None, help="Override --target with a single URL")
    parser.add_argument("--leads-file", type=Path, default=LEADS_FILE)
    parser.add_argument("--results-file", type=Path, default=RESULTS_FILE)
    parser.add_argument("--limit", type=int, default=0, help="0 = all rows")
    parser.add_argument("--delay", type=float, default=0.3, help="Seconds between requests")
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--resume", action="store_true", help="Skip emails already recorded as done")
    parser.add_argument("--dry-run", action="store_true", help="Build payloads, do not send")
    parser.add_argument("--visitor-id")
    parser.add_argument("--landing-page")
    parser.add_argument("--source")
    parser.add_argument("--medium")
    parser.add_argument("--campaign")
    parser.add_argument("--content")
    parser.add_argument("--term")
    parser.add_argument("--referrer")
    parser.add_argument("--product-name", default=EXTRA_DEFAULTS["productName"])
    args = parser.parse_args()

    if not args.leads_file.exists():
        print(f"Leads file not found: {args.leads_file}")
        return 1

    extra = {
        "visitorId": args.visitor_id,
        "landingPage": args.landing_page,
        "source": args.source,
        "medium": args.medium,
        "campaign": args.campaign,
        "content": args.content,
        "term": args.term,
        "referrer": args.referrer,
        "productName": args.product_name,
    }

    with args.leads_file.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if args.limit:
        rows = rows[: args.limit]

    totals = {"success": 0, "error": 0, "invalid_email": 0, "skipped": 0}
    for label, base_url in resolve_targets(args):
        counters = run_target(args, label, base_url, rows, extra)
        for key, value in counters.items():
            totals[key] += value

    print("\nTotals:", ", ".join(f"{k}={v}" for k, v in totals.items()))
    return 1 if totals["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())