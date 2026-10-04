"""Phone/email extraction and validation for lead contact data.

Contacts are only read from places that actually carry contact data (tel:/mailto:
links, schema.org, labelled contact blocks, cleaned visible text) - never from raw
HTML, scripts or attributes - and every candidate must pass `phonenumbers` /
`email_validator` validation plus generic placeholder/garbage rules.
"""

import json
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

import phonenumbers
from bs4 import BeautifulSoup
from email_validator import EmailNotValidError, validate_email

DEFAULT_REGION = "IN"

SOURCE_CONFIDENCE = {
    "tel_link": 0.98,
    "mailto_link": 0.98,
    "schema_org": 0.97,
    "google_maps": 0.95,
    "whatsapp_link": 0.90,
    "contact_page": 0.90,
    "visible_contact_text": 0.80,
    "search_snippet_contact": 0.80,
    "visible_text": 0.50,
    "search_snippet": 0.50,
}

# Only candidates at or above this confidence may become the primary Phone/Email.
PRIMARY_MIN_CONFIDENCE = 0.80

# Mirrors the Lead Capture API field limits.
MAX_ALL_EMAILS = 256
MAX_ALL_PHONES = 128


@dataclass(frozen=True)
class ContactCandidate:
    value: str
    source: str
    confidence: float


def candidate(value: str, source: str) -> ContactCandidate:
    return ContactCandidate(value, source, SOURCE_CONFIDENCE[source])


# --------------------------------------------------------------------------- phones

# Integer overflow / max-int values that leak out of JS and databases.
_NUMERIC_CONSTANTS = (
    "2147483647", "2147483648", "4294967295", "4294967296",
    "9007199254740991", "9223372036854775807", "65535",
)
_PHONE_TEXT_RE = re.compile(r"^[+\d][\d\s\-().\u2013/]*\d$")
_FAX_RE = re.compile(r"\bfax\b\.?\s*(?:no\.?|number)?\s*[:\-]?\s*\+?[\d][\d\s\-().]{5,}", re.I)
_LABEL_WINDOW = 60
_CONTACT_LABEL_RE = re.compile(
    r"\b(contact|call|phone|tel|telephone|mobile|mob|cell|reach us|helpline|hotline|"
    r"whatsapp|toll[\s-]?free|landline|e-?mail|mail us|write to us)\b",
    re.I,
)
_NON_PHONE_LABEL_RE = re.compile(
    r"\b(id|order|invoice|ref|reference|gst|gstin|cin|pan|tan|reg|registration|"
    r"account|a/c|ifsc|pin|pincode|zip|sku|isbn|serial|ticket|tracking|awb|"
    r"since|est|copyright|version|v)\b\.?\s*(?:no\.?|number|#)?\s*[:\-#]?\s*$|©\s*$",
    re.I,
)


def _has_ascending_run(digits: str, length: int = 7) -> bool:
    run = 1
    for prev, cur in zip(digits, digits[1:]):
        run = run + 1 if int(cur) == int(prev) + 1 else 1
        if run >= length:
            return True
    return False


def _is_date(year: int, month: int, day: int) -> bool:
    return 1900 <= year <= 2099 and 1 <= month <= 12 and 1 <= day <= 31


def _looks_like_date(digits: str) -> bool:
    if len(digits) == 8:
        ymd = _is_date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
        dmy = _is_date(int(digits[4:]), int(digits[2:4]), int(digits[:2]))
        mdy = _is_date(int(digits[4:]), int(digits[:2]), int(digits[2:4]))
        return ymd or dmy or mdy
    if len(digits) in (12, 14):  # YYYYMMDDhhmm[ss]
        return _is_date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    return False


def _looks_like_timestamp(digits: str) -> bool:
    if len(digits) == 10:
        return 1_000_000_000 <= int(digits) <= 2_100_000_000
    if len(digits) == 13:
        return 1_000_000_000_000 <= int(digits) <= 2_100_000_000_000
    return False


def _is_garbage_digits(digits: str) -> bool:
    if not digits:
        return True
    if len(set(digits)) == 1 or re.search(r"(\d)\1{7,}", digits):
        return True
    if len(digits) >= 8 and len(set(digits)) <= 2:
        return True
    if any(constant in digits for constant in _NUMERIC_CONSTANTS):
        return True
    return _has_ascending_run(digits)


def is_placeholder_phone(raw: str) -> bool:
    """Generic garbage rules: repeated digits, sequences, IDs, dates, timestamps."""
    text = str(raw or "").strip()
    digits = re.sub(r"\D", "", text)
    if _is_garbage_digits(digits):
        return True
    # A bare run of digits (no +, no trunk 0, no separators) is far more likely an
    # ID, date or timestamp than a phone number.
    if digits == text and not text.startswith("0"):
        if _looks_like_timestamp(digits) or _looks_like_date(digits):
            return True
    return False


def normalize_phone(raw: str, region: str | None = None, strict: bool = False) -> str | None:
    """Return the E.164 form of a valid phone number, or None.

    `strict` is used for low-confidence free-text matches and additionally rejects
    bare unformatted digit runs that only parse as landlines.
    """
    if raw is None:
        return None
    text = unquote(str(raw)).strip()
    text = re.sub(r"^(?:tel|callto|phone|sms)\s*:\s*/*", "", text, flags=re.I).strip()
    text = re.sub(r"\s*(?:ext|extn|x)\.?\s*\d{1,6}$", "", text, flags=re.I).strip()
    if not text or len(text) > 32 or not _PHONE_TEXT_RE.match(text):
        return None
    digits = re.sub(r"\D", "", text)
    if not 7 <= len(digits) <= 17 or is_placeholder_phone(text):
        return None
    try:
        number = phonenumbers.parse(text, None if text.startswith("+") else (region or DEFAULT_REGION))
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(number):
        return None
    if _is_garbage_digits(str(number.national_number)):
        return None
    if strict and digits == text and not text.startswith("0"):
        if phonenumbers.number_type(number) == phonenumbers.PhoneNumberType.FIXED_LINE:
            return None
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def is_valid_phone(raw: str, region: str | None = None) -> bool:
    return normalize_phone(raw, region) is not None


def phone_from_whatsapp_url(url: str) -> str | None:
    """wa.me/919876543210 or api.whatsapp.com/send?phone=919876543210 -> E.164."""
    parsed = urlparse(url or "")
    host = parsed.netloc.lower()
    digits = ""
    if host.endswith("wa.me"):
        digits = parsed.path.strip("/").split("/")[0]
    elif "whatsapp.com" in host:
        digits = (parse_qs(parsed.query).get("phone") or [""])[0]
    digits = re.sub(r"\D", "", digits)
    return normalize_phone(f"+{digits}") if digits else None


def phones_in_text(text: str, region: str | None = None) -> list[tuple[str, bool]]:
    """Validated E.164 numbers in cleaned text, each flagged if a contact label precedes it.

    Bare unformatted digit runs (e.g. 7621835252) are only accepted next to a
    contact label; numbers right after ID/order/GST-style labels are dropped.
    """
    text = _FAX_RE.sub(" ", text or "")
    found: dict[str, bool] = {}
    try:
        matcher = phonenumbers.PhoneNumberMatcher(
            text, region or DEFAULT_REGION, leniency=phonenumbers.Leniency.VALID
        )
        for match in matcher:
            before = text[max(0, match.start - _LABEL_WINDOW):match.start]
            if _NON_PHONE_LABEL_RE.search(before[-25:]):
                continue
            labelled = bool(_CONTACT_LABEL_RE.search(before))
            formatted = not match.raw_string.isdigit()
            if not (labelled or formatted):
                continue
            normalized = normalize_phone(match.raw_string, region, strict=not labelled)
            if normalized:
                found[normalized] = found.get(normalized, False) or labelled
    except Exception:
        pass
    return list(found.items())


# --------------------------------------------------------------------------- emails

_EMAIL_TEXT_RE = re.compile(
    r"(?<![\w.%+\-])[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,24}(?![\w\-])"
)
_FILE_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "svg", "webp", "bmp", "ico", "tif", "tiff", "avif",
    "heic", "css", "scss", "less", "js", "mjs", "cjs", "ts", "tsx", "jsx", "json",
    "xml", "map", "woff", "woff2", "ttf", "eot", "otf", "mp4", "webm", "mov", "avi",
    "mp3", "wav", "ogg", "pdf", "zip", "gz", "rar", "txt", "csv", "php", "asp",
    "aspx", "jsp", "html", "htm", "vue", "svelte",
}
_PLACEHOLDER_DOMAIN_LABELS = {
    "example", "domain", "yourdomain", "mydomain", "somedomain", "company",
    "yourcompany", "mycompany", "companyname", "yourcompanyname", "somewhere",
    "website", "yourwebsite", "mywebsite", "yoursite", "mysite", "test", "testing",
    "sample", "email", "youremail", "placeholder", "dummy", "xyz", "abc", "acme-corp",
    "localhost", "invalid",
}
_BLOCKED_EMAIL_DOMAINS = (
    "sentry.io", "wixpress.com", "sentry-next.wixpress.com", "example.com",
    "example.org", "example.net", "email.tld", "domain.tld",
)
_PLACEHOLDER_LOCALS = {
    "you", "your", "yourname", "your.name", "your_name", "youremail", "your.email",
    "name", "fullname", "firstname", "first.name", "firstname.lastname", "first.last",
    "lastname", "last.name", "surname", "name.surname", "johndoe", "john.doe",
    "jane.doe", "janedoe", "john.smith", "johnsmith", "user", "username", "someone",
    "somebody", "email", "emailaddress", "mail", "example", "sample", "test", "testing",
    "demo", "abc", "xyz", "foo", "bar", "foobar", "me", "myname", "my.name",
    "placeholder", "dummy", "null", "undefined", "none", "address",
}
_NO_REPLY_RE = re.compile(r"^(?:no-?reply|do-?not-?reply|donotreply|mailer-daemon|postmaster)", re.I)
_SECOND_LEVEL_SUFFIXES = {"co", "com", "org", "net", "ac", "gov", "edu", "gen", "firm", "ind"}


def normalize_email(raw: str) -> str | None:
    if raw is None:
        return None
    text = unquote(str(raw)).strip()
    if text.lower().startswith("mailto:"):
        text = text[7:]
    text = text.split("?", 1)[0].strip().strip("<>\"'()[]{},;:").rstrip(".").lower()
    if not text or re.search(r"\s", text) or text.count("@") != 1:
        return None
    return text


def _registrable_label(domain: str) -> str:
    labels = domain.split(".")
    if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL_SUFFIXES:
        return labels[-3]
    return labels[-2] if len(labels) >= 2 else labels[0]


def is_placeholder_email(raw: str) -> bool:
    email = normalize_email(raw)
    if not email:
        return True
    local, domain = email.split("@", 1)
    if local in _PLACEHOLDER_LOCALS or re.fullmatch(r"(.)\1*", local):
        return True
    if _NO_REPLY_RE.match(local):
        return True
    if re.fullmatch(r"[0-9a-f]{16,}", local):  # Sentry/Wix DSN keys
        return True
    if any(domain == blocked or domain.endswith("." + blocked) for blocked in _BLOCKED_EMAIL_DOMAINS):
        return True
    if _registrable_label(domain) in _PLACEHOLDER_DOMAIN_LABELS:
        return True
    if domain.split(".")[0] in {"example", "test", "localhost"}:
        return True
    return False


def is_valid_email(raw: str) -> bool:
    email = normalize_email(raw)
    if not email:
        return False
    local, domain = email.split("@", 1)
    labels = domain.split(".")
    tld = labels[-1]
    if len(labels) < 2 or not tld.isalpha() or not 2 <= len(tld) <= 24 or tld in _FILE_EXTENSIONS:
        return False
    # Retina asset names: logo@2x.png, icon@3x.webp
    if any(re.fullmatch(r"\d+(?:\.\d+)?x", label) for label in labels):
        return False
    if not local or len(local) > 64:
        return False
    try:
        validate_email(email, check_deliverability=False)
    except EmailNotValidError:
        return False
    return not is_placeholder_email(email)


def emails_in_text(text: str) -> list[tuple[str, bool]]:
    """Validated emails in cleaned text, each flagged if a contact label precedes it."""
    found: dict[str, bool] = {}
    for match in _EMAIL_TEXT_RE.finditer(text or ""):
        email = normalize_email(match.group(0))
        if email and is_valid_email(email):
            labelled = bool(_CONTACT_LABEL_RE.search(text[max(0, match.start() - _LABEL_WINDOW):match.start()]))
            found[email] = found.get(email, False) or labelled
    return list(found.items())


# --------------------------------------------------------------------------- HTML

_INVISIBLE_TAGS = [
    "script", "style", "noscript", "svg", "template", "iframe", "canvas", "object",
    "embed", "head", "meta", "link", "picture", "video", "audio", "img",
]
# Elements whose class/id marks them as contact info (often an icon with no text label).
_CONTACT_MARKER_SELECTOR = (
    "address, [itemprop=address], [class*=contact i], [id*=contact i], [class*=phone i], "
    "[id*=phone i], [class*=mobile i], [class*=whatsapp i], [class*=fa-envelope i], "
    "[class*=email i], [class*=-call i], [class*=call- i]"
)
_SKIP_SCHEMA_TYPES = {"person", "review", "rating", "aggregaterating", "breadcrumblist",
                      "imageobject", "videoobject", "product", "offer", "event"}


def visible_text(soup: BeautifulSoup) -> str:
    return soup.get_text(" ", strip=True)


def _clean_soup(html: str) -> BeautifulSoup:
    """Drop everything a visitor cannot read and tag contact-marked elements with a label."""
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(_INVISIBLE_TAGS):
        tag.decompose()
    for tag in soup.select("[hidden], [style*='display:none' i], [style*='display: none' i]"):
        tag.decompose()
    for tag in soup.select(_CONTACT_MARKER_SELECTOR):
        tag.insert(0, " contact: ")
    return soup


def _schema_values(node, phones: list[str], emails: list[str]) -> None:
    if isinstance(node, list):
        for item in node:
            _schema_values(item, phones, emails)
        return
    if not isinstance(node, dict):
        return
    types = node.get("@type")
    types = types if isinstance(types, list) else [types]
    if any(str(t).lower() in _SKIP_SCHEMA_TYPES for t in types if t):
        return
    for key, value in node.items():
        key = str(key).lower()
        if key == "telephone":
            phones.extend(v for v in (value if isinstance(value, list) else [value]) if isinstance(v, str))
        elif key == "email":
            emails.extend(v for v in (value if isinstance(value, list) else [value]) if isinstance(v, str))
        elif isinstance(value, (dict, list)):
            _schema_values(value, phones, emails)


def _structured_contacts(soup: BeautifulSoup) -> tuple[list[str], list[str]]:
    phones: list[str] = []
    emails: list[str] = []
    for tag in soup.find_all("script", type=re.compile(r"ld\+json", re.I)):
        raw = (tag.string or tag.get_text() or "").strip().rstrip(";")
        try:
            _schema_values(json.loads(raw), phones, emails)
        except Exception:
            continue
    for tag in soup.select("[itemprop=telephone]"):
        phones.append(tag.get("content") or tag.get_text(" ", strip=True))
    for tag in soup.select("[itemprop=email]"):
        emails.append(tag.get("content") or tag.get("href") or tag.get_text(" ", strip=True))
    return phones, emails


def _email_domain_matches(email: str, website: str | None) -> bool:
    if not website:
        return False
    site = urlparse(website if "//" in website else f"//{website}").netloc.lower().removeprefix("www.")
    domain = email.split("@", 1)[-1]
    return bool(site) and (domain == site or domain.endswith("." + site) or site.endswith("." + domain))


def extract_contact_candidates(
    html: str, page_label: str = "page", region: str | None = None, website: str | None = None,
) -> tuple[list[ContactCandidate], list[ContactCandidate]]:
    """Return (phone candidates, email candidates) from one HTML page."""
    if not html:
        return [], []
    phones: list[ContactCandidate] = []
    emails: list[ContactCandidate] = []
    raw_soup = BeautifulSoup(html, "html.parser")

    for anchor in raw_soup.find_all(["a", "area"], href=True):
        href = anchor["href"].strip()
        lower = href.lower()
        if lower.startswith(("tel:", "callto:")):
            phone = normalize_phone(href, region)
            if phone:
                phones.append(candidate(phone, "tel_link"))
        elif lower.startswith("mailto:"):
            for part in unquote(href[7:]).split("?", 1)[0].split(","):
                email = normalize_email(part)
                if email and is_valid_email(email):
                    emails.append(candidate(email, "mailto_link"))
        elif "wa.me/" in lower or "whatsapp.com/send" in lower:
            phone = phone_from_whatsapp_url(href)
            if phone:
                phones.append(candidate(phone, "whatsapp_link"))

    schema_phones, schema_emails = _structured_contacts(raw_soup)
    for raw in schema_phones:
        phone = normalize_phone(raw, region)
        if phone:
            phones.append(candidate(phone, "schema_org"))
    for raw in schema_emails:
        email = normalize_email(raw)
        if email and is_valid_email(email):
            emails.append(candidate(email, "schema_org"))

    soup = _clean_soup(html)
    text = visible_text(soup)
    on_contact_page = page_label.lower() in {"contact", "contactpage", "contact_page"}
    for phone, labelled in phones_in_text(text, region):
        source = "contact_page" if on_contact_page else ("visible_contact_text" if labelled else "visible_text")
        phones.append(candidate(phone, source))
    for email, labelled in emails_in_text(text):
        # The company's own-domain address printed on its site counts as contact text.
        labelled = labelled or _email_domain_matches(email, website)
        source = "contact_page" if on_contact_page else ("visible_contact_text" if labelled else "visible_text")
        emails.append(candidate(email, source))

    return merge_candidates(phones), merge_candidates(emails)


def extract_text_candidates(
    text: str, region: str | None = None, labelled_source: str = "search_snippet_contact",
    fallback_source: str = "search_snippet",
) -> tuple[list[ContactCandidate], list[ContactCandidate]]:
    """Candidates from plain text (e.g. search snippets); labelled matches rank higher."""
    phones = [candidate(p, labelled_source if labelled else fallback_source)
              for p, labelled in phones_in_text(text, region)]
    emails = [candidate(e, labelled_source if labelled else fallback_source)
              for e, labelled in emails_in_text(text)]
    return merge_candidates(phones), merge_candidates(emails)


# --------------------------------------------------------------------------- selection

COUNTRY_HINTS = {
    "india": "IN", "united states": "US", "usa": "US", "united kingdom": "GB", "uk": "GB",
    "england": "GB", "australia": "AU", "canada": "CA", "singapore": "SG",
    "united arab emirates": "AE", "uae": "AE", "dubai": "AE", "germany": "DE",
    "new zealand": "NZ", "south africa": "ZA", "ireland": "IE", "france": "FR",
    "netherlands": "NL", "malaysia": "MY", "saudi arabia": "SA", "qatar": "QA",
}
# ccTLDs commonly used as generic domains, so they say nothing about the country.
_GENERIC_CCTLDS = {"co", "io", "ai", "me", "tv", "ly", "gg", "to", "fm", "cc", "ws", "so", "sh", "is", "it"}


def infer_phone_region(website: str | None = None, address: str | None = None, default: str = DEFAULT_REGION) -> str:
    lowered = (address or "").lower()
    for hint, region in COUNTRY_HINTS.items():
        if re.search(rf"\b{re.escape(hint)}\b", lowered):
            return region
    host = urlparse(website if website and "//" in website else f"//{website or ''}").netloc.lower()
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    if tld == "uk":
        return "GB"
    if len(tld) == 2 and tld not in _GENERIC_CCTLDS and tld.upper() in phonenumbers.SUPPORTED_REGIONS:
        return tld.upper()
    return default


def merge_candidates(candidates: list[ContactCandidate]) -> list[ContactCandidate]:
    """Deduplicate on the normalized value, keeping the highest-confidence source."""
    best: dict[str, ContactCandidate] = {}
    for item in candidates:
        current = best.get(item.value)
        if current is None or item.confidence > current.confidence:
            best[item.value] = item
    return sorted(best.values(), key=lambda item: -item.confidence)


_PREFERRED_LOCALS = ("info", "contact", "hello", "sales", "enquiry", "inquiry", "business", "support")


def _email_rank(item: ContactCandidate, website: str | None, decision_maker_name: str | None):
    local = item.value.split("@", 1)[0]
    first_name = (decision_maker_name or "").split(" ")[0].lower()
    return (
        _email_domain_matches(item.value, website),
        item.confidence,
        bool(first_name) and local == first_name,
        local.startswith(_PREFERRED_LOCALS),
    )


def _join_limited(values: list[str], limit: int) -> str:
    joined = ""
    for value in values:
        candidate_text = f"{joined}, {value}" if joined else value
        if len(candidate_text) > limit:
            break
        joined = candidate_text
    return joined


def select_contacts(
    phone_candidates: list[ContactCandidate], email_candidates: list[ContactCandidate],
    website: str | None = None, decision_maker_name: str | None = None,
) -> dict[str, str]:
    """Pick primary Phone/Email (high confidence only) and build AllPhones/AllEmails."""
    phones = merge_candidates(phone_candidates)
    emails = merge_candidates(email_candidates)
    emails.sort(key=lambda item: _email_rank(item, website, decision_maker_name), reverse=True)

    primary_phone = next((p for p in phones if p.confidence >= PRIMARY_MIN_CONFIDENCE), None)
    primary_email = next((e for e in emails if e.confidence >= PRIMARY_MIN_CONFIDENCE), None)

    def ordered(items, primary):
        values = [item.value for item in items]
        if primary:
            values.remove(primary.value)
            values.insert(0, primary.value)
        return values

    return {
        "Phone": primary_phone.value if primary_phone else "",
        "PhoneSource": primary_phone.source if primary_phone else "",
        "PhoneConfidence": f"{primary_phone.confidence:.2f}" if primary_phone else "",
        "AllPhones": _join_limited(ordered(phones, primary_phone), MAX_ALL_PHONES),
        "Email": primary_email.value if primary_email else "",
        "EmailSource": primary_email.source if primary_email else "",
        "EmailConfidence": f"{primary_email.confidence:.2f}" if primary_email else "",
        "AllEmails": _join_limited(ordered(emails, primary_email), MAX_ALL_EMAILS),
    }
