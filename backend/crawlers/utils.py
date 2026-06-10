import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"\+?[0-9][0-9 \-().]{6,}[0-9]")

EMAIL_REJECT_PATTERNS = [
    re.compile(r"^test@", re.I),
    re.compile(r"^example@", re.I),
    re.compile(r"^noreply@", re.I),
    re.compile(r"^no-?reply@", re.I),
    re.compile(r"@example\.", re.I),
    re.compile(r"@test\.", re.I),
    re.compile(r"@invalid\.", re.I),
]

PREFERRED_EMAIL_PREFIXES = [
    "info",
    "hello",
    "sales",
    "contact",
    "business",
    "marketing",
    "team",
    "support",
    "help",
    "admin",
]

REJECT_PHONES = {
    "+0000000000",
    "+000000000",
    "+1234567890",
    "1234567890",
    "0000000000",
}

SOCIAL_PATTERNS = {
    "LinkedIn": re.compile(r"linkedin\.com/(?:company|showcase)(?:/|$)", re.I),
    "Facebook": re.compile(r"facebook\.com/", re.I),
    "Instagram": re.compile(r"instagram\.com/", re.I),
    "Twitter": re.compile(r"twitter\.com/|x\.com/", re.I),
    "YouTube": re.compile(r"youtube\.com/|youtu\.be/", re.I),
    "TikTok": re.compile(r"tiktok\.com/", re.I),
    "Pinterest": re.compile(r"pinterest\.com/", re.I),
}

SOCIAL_PROOF_KEYWORDS = {
    "HasTestimonials": [
        "testimonial",
        "testimonials",
        "client-testimonials",
        "customer-testimonials",
        "what-clients-say",
        "what-customers-say",
        "feedback",
        "customer-feedback",
        "wall-of-love",
        "walloflove",
        "love-from-customers",
    ],
    "HasReviews": [
        "reviews",
        "review",
        "trusted-by",
        "trustedby",
        "our-clients",
        "our clients",
        "client-story",
        "client-stories",
        "customer-story",
        "customer-stories",
        "customer-success",
        "google-review",
        "google-reviews",
        "google rating",
        "google-rating",
        "review us on google",
        "reviews on google",
    ],
    "HasCaseStudies": [
        "case-study",
        "case-studies",
        "casestudy",
        "casestudies",
        "success-story",
        "success-stories",
        "results",
        "our-work",
        "portfolio",
        "projects",
        "work",
        "client-work",
        "achievements",
        "client-results",
    ],
    "HasVideoTestimonials": [
        "video-testimonial",
        "video-testimonials",
        "customer-video",
        "client-video",
        "video-review",
        "video-reviews",
        "youtube",
        "vimeo",
        "watch-story",
        "watch-video",
    ],
    "HasGoogleReviews": [
        "google-review",
        "google-reviews",
        "google rating",
        "google-rating",
        "review us on google",
        "reviews on google",
    ],
}

BEST_PAGE_KEYWORDS = {
    "contact": [
        "contact",
        "contact-us",
        "contactus",
        "get-in-touch",
        "reach-us",
        "reachus",
        "talk-to-us",
        "talktous",
        "support",
        "help",
        "customer-support",
        "sales",
        "connect",
        "enquiry",
        "inquiry",
        "book-call",
        "schedule-call",
        "book-demo",
        "request-demo",
        "request-a-demo",
        "demo",
        "meeting",
        "consultation",
        "free-consultation",
    ],
    "about": [
        "about",
        "about-us",
        "aboutus",
        "our-story",
        "our-company",
        "company",
        "who-we-are",
        "team",
        "our-team",
        "leadership",
        "founder",
        "founders",
        "management",
    ],
    "testimonials": [
        "testimonial",
        "testimonials",
        "client-testimonials",
        "customer-testimonials",
        "what-clients-say",
        "what-customers-say",
        "reviews",
        "review",
        "feedback",
        "customer-feedback",
        "success-story",
        "success-stories",
        "customer-story",
        "customer-stories",
        "client-story",
        "client-stories",
        "wall-of-love",
        "walloflove",
        "love-from-customers",
    ],
    "reviews": [
        "review",
        "reviews",
        "rating",
        "trusted-by",
        "trustedby",
        "google-review",
        "google-reviews",
        "review-us-on-google",
        "reviews-on-google",
    ],
    "case_studies": [
        "case-study",
        "case-studies",
        "casestudy",
        "casestudies",
        "success-story",
        "success-stories",
        "results",
        "our-work",
        "portfolio",
        "projects",
        "work",
        "client-work",
        "achievements",
        "client-results",
    ],
}


def normalize_url(base_url: str, path: str) -> str:
    if not path:
        return base_url
    return urljoin(base_url, path)


def parse_domain(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def clean_email(email: str) -> str:
    email = email.strip().lower()
    if email.startswith("mailto:"):
        email = email.split("mailto:", 1)[1].split("?")[0]
    return email


def is_valid_email(email: str) -> bool:
    email = clean_email(email)
    if not EMAIL_PATTERN.match(email):
        return False
    for pattern in EMAIL_REJECT_PATTERNS:
        if pattern.search(email):
            return False
    return True


def email_confidence(email: str, website: str | None = None) -> int:
    email = clean_email(email)
    if not is_valid_email(email):
        return 0
    score = 50
    local, domain = email.split("@", 1)
    if website:
        site_domain = parse_domain(website)
        if domain == site_domain or domain.endswith(f".{site_domain}") or site_domain.endswith(f".{domain}"):
            score += 40
    if any(local.startswith(prefix) for prefix in PREFERRED_EMAIL_PREFIXES):
        score += 30
    if domain in {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com"}:
        score -= 30
    return max(0, min(score, 100))


def extract_emails(text: str) -> list[str]:
    emails = {clean_email(email) for email in EMAIL_PATTERN.findall(text)}
    soup = BeautifulSoup(text, "lxml")
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if href.lower().startswith("mailto:"):
            email = clean_email(href)
            if email:
                emails.add(email)
    return [email for email in emails if is_valid_email(email)]


def choose_best_email(emails: list[str], website: str | None = None) -> tuple[str | None, int]:
    best_email = None
    best_score = 0
    for email in emails:
        score = email_confidence(email, website)
        if score > best_score:
            best_score = score
            best_email = email
    return best_email, best_score


def choose_best_phone(phones: list[str]) -> tuple[str | None, int]:
    best_phone = None
    best_score = 0
    for phone in phones:
        score = phone_confidence(phone)
        if score > best_score:
            best_score = score
            best_phone = phone
    return best_phone, best_score


def clean_phone(phone: str) -> str | None:
    digits = re.sub(r"[^0-9+]+", "", phone)
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if not digits:
        return None
    if digits in REJECT_PHONES:
        return None
    normalized = digits
    count = len(re.sub(r"[^0-9]", "", normalized))
    if count < 7 or count > 15:
        return None
    return normalized


def is_valid_phone(phone: str) -> bool:
    return clean_phone(phone) is not None


def phone_confidence(phone: str) -> int:
    cleaned = clean_phone(phone)
    if not cleaned:
        return 0
    digits = re.sub(r"[^0-9]", "", cleaned)
    score = 50
    if cleaned.startswith("+") and len(digits) >= 10:
        score += 30
    if 10 <= len(digits) <= 12:
        score += 20
    if any(cleaned.startswith(prefix) for prefix in ["+1", "+44", "+61", "+91", "+49"]):
        score += 10
    return min(score, 100)


def extract_phones(text: str) -> list[str]:
    found = PHONE_PATTERN.findall(text)
    phones = set()
    for phone in found:
        cleaned = clean_phone(phone)
        if cleaned:
            phones.add(cleaned)
    return list(phones)


def find_social_links(soup: BeautifulSoup) -> dict[str, str | None]:
    result = {name: None for name in SOCIAL_PATTERNS}
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith("#"):
            continue
        for network, pattern in SOCIAL_PATTERNS.items():
            if pattern.search(href):
                if not result[network]:
                    result[network] = href
    return result


def find_page_urls(base_url: str, soup: BeautifulSoup) -> dict[str, str | None]:
    pages = {key: None for key in BEST_PAGE_KEYWORDS}
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].lower()
        text = anchor.get_text(separator=" ", strip=True).lower()
        href_text = " ".join(filter(None, [text, href]))
        for page_type, keywords in BEST_PAGE_KEYWORDS.items():
            if pages[page_type] is not None:
                continue
            if any(keyword in href_text for keyword in keywords):
                pages[page_type] = normalize_url(base_url, anchor["href"])
    return pages


def detect_social_proof(text: str) -> dict[str, bool]:
    lower = text.lower()
    return {flag: any(keyword in lower for keyword in keywords) for flag, keywords in SOCIAL_PROOF_KEYWORDS.items()}
