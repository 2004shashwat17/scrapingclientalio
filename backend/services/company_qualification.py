"""Qualification rules for DropProof's fleet-operator prospect audience."""

import re
from urllib.parse import urlparse


_JOB_AND_DIRECTORY_HOSTS = {
    "indeed.com", "glassdoor.com", "monster.com", "naukri.com", "shine.com",
    "linkedin.com", "facebook.com", "instagram.com", "justdial.com", "yelp.com",
    "crunchbase.com", "clutch.co", "goodfirms.co", "g2.com", "capterra.com",
    "apollo.io", "zoominfo.com",
}
_JOB_TITLE_RE = re.compile(r"\b(?:jobs?|careers?|vacancies|hiring|recruitment|job listings?)\b", re.I)
_OPERATOR_RE = re.compile(
    r"\b(?:logistics|courier|couriers|trucking|truck(?:ing)?|freight|cargo|fleet|"
    r"transport(?:ation)?|delivery|distribution|bus operator|school bus|passenger transport|"
    r"vehicle rental|car rental|taxi|cab service|3pl|third[ -]party logistics|last[ -]mile|"
    r"moving company|haulage|dispatch|waste collection|construction equipment)\b",
    re.I,
)
_COMPETITOR_PRODUCT_RE = re.compile(
    r"\b(?:transport management|fleet management|transportation management|"
    r"route optimization|route planning|dispatch management|telematics|gps tracking)\s+"
    r"(?:software|platform|system|solution|technology)\b|"
    r"\b(?:tms|fms)\s+(?:software|platform|system|solution)\b",
    re.I,
)
_VENDOR_RE = re.compile(
    r"\b(?:software (?:company|provider|vendor|developer)|saas provider|"
    r"we (?:build|develop|provide|offer|sell)\b|our (?:software|platform|product)\b)",
    re.I,
)
_KNOWN_COMPETITOR_RE = re.compile(
    r"\b(?:fleetx|loconav|wheelseye|fareye|shipsy|locus(?:\.sh)?|freight tiger|"
    r"trackobit|fleetroot|fleetable|intangles|pando(?:\.ai)?)\b",
    re.I,
)


def _host_is_listing(host: str) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in _JOB_AND_DIRECTORY_HOSTS)


def qualify_dropproof_company(company_name: str, website: str = "", evidence: str = "") -> tuple[bool, str]:
    """Accept verified fleet/transport operators, rejecting listings and TMS/FMS vendors.

    No company-size ceiling is applied. The source keyword is intentionally not
    considered positive evidence because it describes the search, not the company.
    """
    name = (company_name or "").strip()
    host = urlparse(website if "://" in (website or "") else f"//{website or ''}").netloc.lower()
    host = host.removeprefix("www.").split(":", 1)[0]
    if not name:
        return False, "missing company name"
    if _host_is_listing(host):
        return False, "directory or job-listing domain"
    if _JOB_TITLE_RE.search(name):
        return False, "job listing or recruitment result"

    combined = f"{name}\n{evidence or ''}"
    if _KNOWN_COMPETITOR_RE.search(name) and (
        _VENDOR_RE.search(combined) or _COMPETITOR_PRODUCT_RE.search(combined)
    ):
        return False, "known TMS/FMS or fleet-software competitor"
    if _COMPETITOR_PRODUCT_RE.search(name):
        return False, "TMS/FMS or fleet-software competitor"
    if _COMPETITOR_PRODUCT_RE.search(combined) and _VENDOR_RE.search(combined):
        return False, "TMS/FMS or fleet-software vendor"
    if not _OPERATOR_RE.search(combined):
        return False, "no verified transport or fleet-operator evidence"
    return True, "transport/fleet operator evidence found"
