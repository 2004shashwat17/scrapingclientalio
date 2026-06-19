import csv
import re
from pathlib import Path
from typing import Any

from email_validator import EmailNotValidError, validate_email

DATA_DIR = Path(__file__).resolve().parent / "data"
LEADS_FILE = DATA_DIR / "leads.csv"
OUTPUT_FILES = {
    "agency_founders.csv": "agency_founders.csv",
    "saas_founders.csv": "saas_founders.csv",
    "coaches.csv": "coaches.csv",
    "consultants.csv": "consultants.csv",
    "personal_branding.csv": "personal_branding.csv",
    "recruitment.csv": "recruitment.csv",
    "designers.csv": "designers.csv",
    "freelancers.csv": "freelancers.csv",
    "ignored.csv": "ignored.csv",
}

STATUS_FIELDS = [
    "LinkedInFollowed",
    "LinkedInConnected",
    "LinkedInMessaged",
    "InstagramFollowed",
    "InstagramMessaged",
    "EmailSent",
    "EmailOpened",
    "EmailReplied",
    "DemoBooked",
    "Customer",
]

BASE_FIELDS = [
    "LeadId",
    "CompanyName",
    "Website",
    "Industry",
    "Email",
    "Phone",
    "LinkedIn",
    "Facebook",
    "Instagram",
    "Twitter",
    "YouTube",
    "ContactPage",
    "HasTestimonials",
    "HasVideoTestimonials",
    "HasCaseStudies",
    "HasGoogleReviews",
    "LeadScore",
    "Priority",
    "Category",
]

OUTPUT_FIELDS = BASE_FIELDS + STATUS_FIELDS

MEDIA_PATTERNS = [
    "news",
    "magazine",
    "press",
    "journal",
    "insider",
    "daily",
    "economictimes",
    "businesstoday",
    "timesnow",
    "livemint",
    "businessworld",
    "thehindu",
    "forbes",
    "investopedia",
    "wiki",
    "wikihow",
    "britannica",
    "media",
    "network",
]

GOVERNMENT_PATTERNS = [
    "gov.",
    "govt",
    "nic.",
    "government",
    "electoral",
    "publicauthority",
    "publicservice",
    "civilservice",
]

EDUCATION_PATTERNS = [
    "edu",
    "university",
    "college",
    "academy",
    "school",
    "training",
    "learning",
    "course",
    "certification",
    "mba",
    "degree",
    "coursera",
    "udemy",
    "khanacademy",
    "skillshare",
    "edumilestones",
    "careerlauncher",
    "mbaskool",
    "apus",
]

DICTIONARY_PATTERNS = [
    "dictionary",
    "thesaurus",
    "word",
    "lexicon",
    "merriam",
    "cambridge",
]

LARGE_ENTERPRISE_PATTERNS = [
    "google",
    "amazon",
    "microsoft",
    "ibm",
    "aws",
    "apple",
    "facebook",
    "meta",
    "oracle",
    "linkedin",
    "salesforce",
    "adobe",
    "intel",
    "sap",
    "accenture",
    "deloitte",
]

JOB_PORTAL_PATTERNS = [
    "jobs",
    "job",
    "career",
    "hiring",
    "shine",
    "foundit",
    "wellfound",
    "indeed",
    "monster",
    "glassdoor",
    "naukri",
    "timesjobs",
    "linkedin.com/jobs",
]

MARKETPLACE_PATTERNS = [
    "for sale",
    "forsale",
    "marketplace",
    "businessforsale",
    "smergers",
    "tobuz",
    "yelu",
    "bizforsale",
    "buy",
    "sell",
    "auction",
    "classified",
]

SERVICE_KEYWORDS = [
    "consult",
    "agency",
    "marketing",
    "brand",
    "design",
    "development",
    "strategy",
    "coach",
    "startup",
    "recruit",
    "talent",
    "social",
    "seo",
    "growth",
]

CATEGORY_FILE_MAP = {
    "Agency Founder": "agency_founders.csv",
    "Growth Agency Founder": "agency_founders.csv",
    "Digital Marketing Agency": "agency_founders.csv",
    "SEO Agency": "agency_founders.csv",
    "Web Development Agency": "agency_founders.csv",
    "UI/UX Agency": "designers.csv",
    "SaaS Founder": "saas_founders.csv",
    "Business Coach": "coaches.csv",
    "Career Coach": "coaches.csv",
    "Executive Coach": "coaches.csv",
    "Branding Consultant": "consultants.csv",
    "Growth Consultant": "consultants.csv",
    "HR Consultant": "consultants.csv",
    "Recruitment Agency": "recruitment.csv",
    "Personal Branding Expert": "personal_branding.csv",
    "LinkedIn Ghostwriter": "personal_branding.csv",
    "Product Leader": "consultants.csv",
    "Freelancer": "freelancers.csv",
    "Ignore": "ignored.csv",
}


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    value = str(value).strip().lower()
    return value in {"true", "1", "yes", "y"}


def normalize_text(value: str) -> str:
    return str(value or "").strip().lower()


def normalize_website(value: str) -> str:
    website = str(value or "").strip()
    if website.startswith("http://") or website.startswith("https://"):
        return website.rstrip("/ ")
    if website and not website.startswith("http"):
        return f"https://{website.rstrip('/ ')}"
    return website


def website_domain(website: str) -> str:
    try:
        from urllib.parse import urlparse

        parsed = urlparse(normalize_website(website))
        return parsed.netloc.lower().lstrip("www.")
    except Exception:
        return normalize_text(website)


def is_valid_email(email: str) -> bool:
    if not email:
        return False
    try:
        validate_email(email, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False


def contains_any(source: str, patterns: list[str]) -> bool:
    source = normalize_text(source)
    for pattern in patterns:
        if pattern in source:
            return True
    return False


def is_news_or_media(row: dict[str, Any]) -> bool:
    combined = " ".join(
        [row.get("CompanyName", ""), row.get("Website", ""), row.get("Industry", "")]
    )
    return contains_any(combined, MEDIA_PATTERNS)


def is_government(row: dict[str, Any]) -> bool:
    return contains_any(row.get("Website", "") + " " + row.get("CompanyName", ""), GOVERNMENT_PATTERNS)


def is_educational(row: dict[str, Any]) -> bool:
    return contains_any(row.get("Website", "") + " " + row.get("CompanyName", ""), EDUCATION_PATTERNS)


def is_dictionary(row: dict[str, Any]) -> bool:
    combined = normalize_text(row.get("CompanyName", "") + " " + row.get("Website", ""))
    return contains_any(combined, DICTIONARY_PATTERNS)


def is_wikipedia(row: dict[str, Any]) -> bool:
    website = normalize_text(row.get("Website", ""))
    name = normalize_text(row.get("CompanyName", ""))
    return "wikipedia" in website or "wikipedia" in name


def is_large_enterprise(row: dict[str, Any]) -> bool:
    return contains_any(row.get("Website", "") + " " + row.get("CompanyName", ""), LARGE_ENTERPRISE_PATTERNS)


def is_job_portal(row: dict[str, Any]) -> bool:
    website = normalize_text(row.get("Website", ""))
    company = normalize_text(row.get("CompanyName", ""))
    if any(pattern in website for pattern in JOB_PORTAL_PATTERNS):
        return True
    if any(pattern in company for pattern in JOB_PORTAL_PATTERNS):
        return True
    return False


def is_marketplace(row: dict[str, Any]) -> bool:
    return contains_any(row.get("CompanyName", "") + " " + row.get("Website", ""), MARKETPLACE_PATTERNS)


def is_removed(row: dict[str, Any]) -> bool:
    if is_wikipedia(row):
        return True
    if is_dictionary(row):
        return True
    if is_government(row):
        return True
    if is_educational(row):
        return True
    if is_large_enterprise(row):
        return True
    if is_job_portal(row):
        return True
    if is_marketplace(row):
        return True
    if is_news_or_media(row):
        return True
    return False


def is_service_business_model(row: dict[str, Any]) -> bool:
    combined = normalize_text(
        " ".join([row.get("CompanyName", ""), row.get("Website", ""), row.get("Industry", "")])
    )
    return any(keyword in combined for keyword in SERVICE_KEYWORDS)


def calculate_lead_score(row: dict[str, Any]) -> int:
    score = 0
    if row.get("HasTestimonials"):
        score += 25
    if row.get("HasVideoTestimonials"):
        score += 20
    if row.get("HasCaseStudies"):
        score += 15
    if row.get("HasGoogleReviews"):
        score += 10
    if row.get("LinkedIn"):
        score += 10
    if row.get("Email") and is_valid_email(row["Email"]):
        score += 10
    if is_service_business_model(row):
        score += 10
    if is_large_enterprise(row) or is_news_or_media(row) or is_government(row) or is_educational(row):
        score -= 20
    return max(0, score)


def translate_priority(score: int) -> str:
    if score >= 80:
        return "Hot Lead"
    if score >= 60:
        return "Warm Lead"
    if score >= 40:
        return "Medium Lead"
    return "Low Priority"


def assign_category(row: dict[str, Any]) -> str:
    combined = normalize_text(
        " ".join([row.get("CompanyName", ""), row.get("Website", ""), row.get("Industry", "")])
    )

    if "saas" in combined or "software as a service" in combined or "software company" in combined:
        return "SaaS Founder"
    if "linkedin ghostwriter" in combined or "linkedin content" in combined or "linkedin writer" in combined:
        return "LinkedIn Ghostwriter"
    if "personal branding" in combined or "personal brand" in combined:
        return "Personal Branding Expert"
    if "executive coach" in combined or "leadership coach" in combined or "ceo coach" in combined:
        return "Executive Coach"
    if "career coach" in combined or "career counselling" in combined or "career counseling" in combined:
        return "Career Coach"
    if "business coach" in combined or "life coach" in combined or "coach" in combined:
        return "Business Coach"
    if "branding consultant" in combined or ("branding" in combined and "consult" in combined):
        return "Branding Consultant"
    if "hr consultant" in combined or "human resources" in combined or "hr" in combined:
        return "HR Consultant"
    if "recruitment" in combined or "recruit" in combined or "staffing" in combined or "talent agency" in combined:
        return "Recruitment Agency"
    if "growth agency" in combined or "growth consulting" in combined or "growth consultant" in combined:
        return "Growth Agency Founder"
    if "agency founder" in combined or "marketing agency" in combined or "creative agency" in combined:
        return "Agency Founder"
    if "digital marketing" in combined or "marketing agency" in combined or "social media" in combined or "advertising" in combined:
        return "Digital Marketing Agency"
    if "seo" in combined or "search engine optimization" in combined or "search engine optimisation" in combined:
        return "SEO Agency"
    if "ui/ux" in combined or "user experience" in combined or "user interface" in combined:
        return "UI/UX Agency"
    if "web development" in combined or "website design" in combined or "web design" in combined:
        return "Web Development Agency"
    if "product leader" in combined or "product manager" in combined or "product strategy" in combined:
        return "Product Leader"
    if "freelancer" in combined or "freelance" in combined or "solopreneur" in combined or "independent consultant" in combined:
        return "Freelancer"
    if "consultant" in combined:
        return "Growth Consultant"
    if "founder" in combined or "startup" in combined:
        return "Agency Founder"
    return "Ignore"


def build_row(row: dict[str, Any], category: str, score: int) -> dict[str, Any]:
    output = {
        "LeadId": row.get("LeadId", ""),
        "CompanyName": row.get("CompanyName", ""),
        "Website": row.get("Website", ""),
        "Industry": row.get("Industry", ""),
        "Email": row.get("Email", ""),
        "Phone": row.get("Phone", ""),
        "LinkedIn": row.get("LinkedIn", ""),
        "Facebook": row.get("Facebook", ""),
        "Instagram": row.get("Instagram", ""),
        "Twitter": row.get("Twitter", ""),
        "YouTube": row.get("YouTube", ""),
        "ContactPage": row.get("ContactPage", ""),
        "HasTestimonials": row.get("HasTestimonials", False),
        "HasVideoTestimonials": row.get("HasVideoTestimonials", False),
        "HasCaseStudies": row.get("HasCaseStudies", False),
        "HasGoogleReviews": row.get("HasGoogleReviews", False),
        "LeadScore": score,
        "Priority": translate_priority(score),
        "Category": category,
    }
    output.update({field: False for field in STATUS_FIELDS})
    return output


def read_leads() -> list[dict[str, Any]]:
    if not LEADS_FILE.exists():
        raise FileNotFoundError(f"Lead file not found: {LEADS_FILE}")

    rows: list[dict[str, Any]] = []
    with LEADS_FILE.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            parsed = {
                "LeadId": row.get("LeadId", ""),
                "CompanyName": row.get("CompanyName", ""),
                "Website": normalize_website(row.get("Website", "")),
                "Industry": row.get("Industry", ""),
                "Email": row.get("Email", ""),
                "Phone": row.get("Phone", ""),
                "LinkedIn": row.get("LinkedIn", ""),
                "Facebook": row.get("Facebook", ""),
                "Instagram": row.get("Instagram", ""),
                "Twitter": row.get("Twitter", ""),
                "YouTube": row.get("YouTube", ""),
                "ContactPage": row.get("ContactPage", ""),
                "HasTestimonials": parse_bool(row.get("HasTestimonials")),
                "HasVideoTestimonials": parse_bool(row.get("HasVideoTestimonials")),
                "HasCaseStudies": parse_bool(row.get("HasCaseStudies")),
                "HasGoogleReviews": parse_bool(row.get("HasGoogleReviews")),
            }
            rows.append(parsed)
    return rows


def write_csv(file_path: Path, rows: list[dict[str, Any]]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def run() -> None:
    leads = read_leads()
    seen_domains: set[str] = set()
    categorized: dict[str, list[dict[str, Any]]] = {filename: [] for filename in OUTPUT_FILES.values()}
    totals = {filename: 0 for filename in OUTPUT_FILES.values()}

    for row in leads:
        domain = website_domain(row["Website"])
        if domain and domain in seen_domains:
            continue
        seen_domains.add(domain)

        category = assign_category(row)
        score = calculate_lead_score(row)
        if score <= 50:
            category = "Ignore"

        if is_removed(row):
            category = "Ignore"

        output_file = CATEGORY_FILE_MAP.get(category, "ignored.csv")
        output_row = build_row(row, category, score)
        categorized[output_file].append(output_row)
        totals[output_file] += 1

    for filename, rows in categorized.items():
        write_csv(Path(filename), rows)

    print("Processed lead exports:")
    for filename, count in totals.items():
        print(f"  {filename}: {count}")

    print("Done. Files written:")
    for filename in OUTPUT_FILES.values():
        print(f"  {Path(filename).resolve()}")


if __name__ == "__main__":
    run()
