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
GENERIC_EMAIL_PREFIXES = [
    "info",
    "hello",
    "contact",
    "sales",
    "support",
    "help",
    "admin",
    "team",
    "office",
    "business",
    "marketing",
    "enquiry",
    "inquiry",
    "customerservice",
    "customersupport",
]

DECISION_MAKER_PRIORITIES = [
    "Founder",
    "Co-Founder",
    "CEO",
    "Owner",
    "Managing Director",
    "Director",
    "President",
]

LOCATION_PATTERNS = [
    re.compile(r"\bheadquarters\b[:\-]?\s*(?P<location>.+)", re.I),
    re.compile(r"\bhq\b[:\-]?\s*(?P<location>.+)", re.I),
    re.compile(r"\bbased in\b[:\-]?\s*(?P<location>.+)", re.I),
    re.compile(r"\blocated in\b[:\-]?\s*(?P<location>.+)", re.I),
    re.compile(r"\blocated at\b[:\-]?\s*(?P<location>.+)", re.I),
    re.compile(r"\boffice in\b[:\-]?\s*(?P<location>.+)", re.I),
]

PERSON_NAME_PATTERN = re.compile(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+){1,4}\b")

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
        "customer-service",
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
    "services": [
        "services",
        "our-services",
        "what-we-do",
        "solutions",
        "offerings",
        "service",
        "consulting",
        "practice",
        "capabilities",
        "expertise",
        "professionals",
    ],
    "products": [
        "products",
        "our-products",
        "solutions",
        "offerings",
        "platform",
        "software",
        "app",
        "tools",
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
    "team": [
        "team",
        "our-team",
        "leadership",
        "leadership-team",
        "management",
        "about-us/team",
    ],
    "leadership": [
        "leadership",
        "our-leadership",
        "leadership-team",
        "management",
    ],
}

BUSINESS_MARKERS = [
    "our services",
    "our products",
    "what we do",
    "solutions",
    "service",
    "product",
    "consulting",
    "agency",
    "firm",
    "practice",
    "company",
    "clients",
    "book a call",
    "schedule a call",
    "get a quote",
    "request a proposal",
]

BUSINESS_REJECT_MARKERS = [
    "news",
    "blog",
    "article",
    "press",
    "forum",
    "reddit",
    "wikipedia",
    "definitions",
    "investopedia",
    "magazine",
    "careers",
    "job",
    "jobs",
    "help",
    "support",
    "faq",
    "terms",
    "privacy",
    "cookie",
    "policy",
    "login",
    "register",
    "signup",
    "sign-up",
    "cart",
    "checkout",
]

EXCLUDED_DOMAINS = [
    "wikipedia.org",
    "forbes.com",
    "hubspot.com",
    "investopedia.com",
    "medium.com",
    "reddit.com",
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "twitter.com",
    "x.com",
    "glassdoor.com",
    "indeed.com",
    "quora.com",
    "g2.com",
    "capterra.com",
    "crunchbase.com",
    "amazon.com",
]


def _normalize_text(text: str) -> str:
    return str(text or "").lower()


def is_blacklisted_domain(domain: str) -> bool:
    domain = domain.lower().lstrip("www.")
    return any(blocked in domain for blocked in EXCLUDED_DOMAINS)


def is_business_content(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    if any(marker in lower for marker in BUSINESS_REJECT_MARKERS):
        return False
    return any(marker in lower for marker in BUSINESS_MARKERS)


def has_business_pages(page_urls: dict[str, str | None]) -> bool:
    has_contact = bool(page_urls.get("contact"))
    has_about = bool(page_urls.get("about"))
    has_service = bool(page_urls.get("services")) or bool(page_urls.get("products"))
    return has_contact and has_about and has_service


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


def is_generic_email(email: str) -> bool:
    email = clean_email(email)
    local = email.split("@", 1)[0].lower()
    return any(local.startswith(prefix) for prefix in GENERIC_EMAIL_PREFIXES)


def domain_matches_site(email: str, website: str | None = None) -> bool:
    if not website:
        return False
    email_domain = email.split("@", 1)[-1].lower()
    site_domain = parse_domain(website).lower()
    return email_domain == site_domain or email_domain.endswith(f".{site_domain}") or site_domain.endswith(f".{email_domain}")


def choose_best_email(emails: list[str], website: str | None = None) -> tuple[str | None, str | None, int]:
    best_personal = None
    best_personal_score = 0
    best_generic = None
    best_generic_score = 0
    best_overall = None
    best_overall_score = 0

    for email in emails:
        score = email_confidence(email, website)
        if score > best_overall_score:
            best_overall_score = score
            best_overall = email
        if domain_matches_site(email, website) and not is_generic_email(email):
            if score > best_personal_score:
                best_personal_score = score
                best_personal = email
        if domain_matches_site(email, website) and is_generic_email(email):
            if score > best_generic_score:
                best_generic_score = score
                best_generic = email

    if best_personal:
        return best_personal, "Personal Business", best_personal_score
    if best_generic:
        return best_generic, "Generic", best_generic_score
    if best_overall:
        email_type = "Generic" if is_generic_email(best_overall) else "Personal Business"
        return best_overall, email_type, best_overall_score
    return None, None, 0


def extract_location(text: str) -> str:
    lower = text.lower()
    for pattern in LOCATION_PATTERNS:
        match = pattern.search(text)
        if match:
            location = match.group("location").strip()
            location = re.sub(r"[\n\r]+", " ", location)
            return location[:200].strip()

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        lower_line = line.lower()
        if any(keyword in lower_line for keyword in ["headquarter", "hq", "based in", "located in", "located at", "office in", "serving"]):
            if len(line) > 10:
                return line[:200].strip()

    for line in lines:
        if "," in line and any(char.isdigit() for char in line):
            return line[:200].strip()
    return ""


def extract_person_name(text: str) -> str | None:
    matches = PERSON_NAME_PATTERN.findall(text)
    for name in matches:
        lower = name.lower()
        if any(keyword.lower() in lower for keyword in DECISION_MAKER_PRIORITIES):
            continue
        if len(name.split()) >= 2:
            return name
    return None


def extract_decision_maker(text: str) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    filtered = [line for line in lines if not line.startswith("<") and not line.startswith("script") and not line.startswith("meta") and not line.startswith("link") and not line.startswith("noscript")]
    for title in DECISION_MAKER_PRIORITIES:
        title_lower = title.lower()
        for index, line in enumerate(filtered):
            if title_lower in line.lower():
                candidate = line
                name = extract_person_name(candidate)
                if name:
                    return name, title
                if index > 0:
                    name = extract_person_name(filtered[index - 1])
                    if name:
                        return name, title
                if index + 1 < len(filtered):
                    name = extract_person_name(filtered[index + 1])
                    if name:
                        return name, title
                simplified = re.sub(re.escape(title), "", candidate, flags=re.I)
                name = extract_person_name(simplified)
                if name:
                    return name, title
    return None, None


def choose_best_business_email(emails: list[str], website: str | None = None, decision_maker_name: str | None = None) -> tuple[str | None, str | None, int]:
    if not website:
        return choose_best_email(emails, website)

    website_domain = parse_domain(website).lower()
    candidates = [email for email in emails if is_valid_email(email)]
    if not candidates:
        return None, None, 0

    if decision_maker_name:
        first_name = decision_maker_name.split()[0].lower()
        for email in candidates:
            local, domain = email.split("@", 1)
            if domain.lower() == website_domain and local.lower() == first_name:
                score = email_confidence(email, website)
                return email, "Founder", score

    for prefix in ["info", "contact", "hello"]:
        for email in candidates:
            local, domain = email.split("@", 1)
            if domain.lower() == website_domain and local.lower() == prefix:
                score = email_confidence(email, website)
                return email, "Generic", score

    return choose_best_email(candidates, website)


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


BUSINESS_MARKERS = [
    "our services",
    "our products",
    "what we do",
    "solutions",
    "service",
    "product",
    "consulting",
    "agency",
    "firm",
    "practice",
    "company",
    "clients",
    "book a call",
    "schedule a call",
    "get a quote",
    "request a proposal",
]

BUSINESS_REJECT_MARKERS = [
    "news",
    "blog",
    "article",
    "press",
    "forum",
    "reddit",
    "wikipedia",
    "definitions",
    "investopedia",
    "magazine",
    "careers",
    "job",
    "jobs",
    "help",
    "support",
    "faq",
    "terms",
    "privacy",
    "cookie",
    "policy",
    "login",
    "register",
    "signup",
    "sign-up",
    "cart",
    "checkout",
]

EXCLUDED_DOMAINS = [
    "wikipedia.org",
    "forbes.com",
    "hubspot.com",
    "investopedia.com",
    "medium.com",
    "reddit.com",
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "twitter.com",
    "x.com",
    "glassdoor.com",
    "indeed.com",
    "quora.com",
    "g2.com",
    "capterra.com",
    "crunchbase.com",
    "amazon.com",
]


def _normalize_text(text: str) -> str:
    return str(text or "").lower()


def is_blacklisted_domain(domain: str) -> bool:
    domain = domain.lower().lstrip("www.")
    return any(blocked in domain for blocked in EXCLUDED_DOMAINS)


def is_business_content(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    if any(marker in lower for marker in BUSINESS_REJECT_MARKERS):
        return False
    return any(marker in lower for marker in BUSINESS_MARKERS)


def is_business_website(text: str, at_least_one_service_link: bool) -> bool:
    if not text:
        return False
    lower = text.lower()
    if any(marker in lower for marker in BUSINESS_REJECT_MARKERS):
        return False
    if any(marker in lower for marker in BUSINESS_MARKERS):
        return True
    return at_least_one_service_link
