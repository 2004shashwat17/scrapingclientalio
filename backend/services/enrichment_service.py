"""Fill in whatever a search card could not provide, from progressively better sources.

Chain, cheapest first, stopping as soon as the lead is complete enough:
  1. Card    - whatever Google Maps already gave us.
  2. Website - found via Google when the card has none; crawl home + contact pages.
  3. Snippet - harvest email/phone out of Google result snippets.
  4. Social  - Facebook/LinkedIn/WhatsApp when no website exists.

Nothing here raises: a lead that cannot be enriched is still returned with
whatever the card did provide.
"""

import logging
import re

from backend.crawlers.contact_extraction import (
    SOURCE_CONFIDENCE,
    ContactCandidate,
    extract_contact_candidates,
    extract_text_candidates,
    infer_phone_region,
    is_valid_email,
    normalize_email,
    normalize_phone,
    phone_from_whatsapp_url,
    select_contacts,
)
from backend.crawlers.google_web_search import GoogleWebSearch, company_search_queries
from backend.crawlers.utils import (
    is_blacklisted_domain,
    parse_domain,
)

logger = logging.getLogger("clientalio.enrich")

# Hosts that are listings/aggregators, never the company's own site.
DIRECTORY_DOMAINS = {
    "clutch.co", "goodfirms.co", "sortlist.com", "themanifest.com", "linkedin.com",
    "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com",
    "justdial.com", "sulekha.com", "yelp.com", "g2.com", "capterra.com",
    "trustpilot.com", "upwork.com", "designrush.com", "google.com", "wikipedia.org",
    "indiamart.com", "tradeindia.com", "amazon.in", "flipkart.com", "olx.in",
}

# A lead needs at least one of these plus one contact route to be worth keeping.
MIN_USEFUL_FIELDS = ["Email", "Phone", "Website"]

CONTACT_FIELDS = {
    "Email", "Phone", "AllEmails", "AllPhones",
    "PhoneSource", "PhoneConfidence", "EmailSource", "EmailConfidence",
}


def is_directory_url(url: str) -> bool:
    domain = parse_domain(url).removeprefix("www.")
    return any(directory in domain for directory in DIRECTORY_DOMAINS)


def company_name_matches(candidate: str, target: str) -> bool:
    """Loose containment check so we don't attach the wrong company's website."""
    left = re.sub(r"[^a-z0-9]", "", (candidate or "").lower())
    right = re.sub(r"[^a-z0-9]", "", (target or "").lower())
    if not left or not right:
        return False
    if left == right:
        return True
    shorter, longer = sorted((left, right), key=len)
    return len(shorter) >= 5 and shorter in longer


LEAD_FIELDS = [
    "CompanyName", "Website", "Headquarters", "CitiesServed", "Industry",
    "FleetSizePublic", "Employees", "RevenuePublic", "DecisionMakers",
    "LinkedInURL", "Email", "Phone", "AllEmails", "AllPhones",
    "PhoneSource", "PhoneConfidence", "EmailSource", "EmailConfidence",
    "CRMTMSUsedPublic", "DeliveryVolumePublic", "ExistingPODSolution", "Notes",
]


def _candidates_from_fields(record: dict, region: str, default_source: str) -> tuple[list, list]:
    """Re-validate contact fields from a card/crawl dict that carries no candidate list."""
    phones: list[ContactCandidate] = []
    emails: list[ContactCandidate] = []
    phone_source = record.get("PhoneSource") or default_source
    email_source = record.get("EmailSource") or default_source
    all_phones = [part.strip() for part in str(record.get("AllPhones") or "").split(",")]
    all_emails = [part.strip() for part in str(record.get("AllEmails") or "").split(",")]
    for raw in [record.get("Phone")] + all_phones:
        phone = normalize_phone(raw, region) if raw else None
        if phone:
            source = phone_source if raw == record.get("Phone") else "visible_text"
            phones.append(ContactCandidate(phone, source, SOURCE_CONFIDENCE.get(source, 0.5)))
    for raw in [record.get("Email")] + all_emails:
        email = normalize_email(raw) if raw else None
        if email and is_valid_email(email):
            source = email_source if raw == record.get("Email") else "visible_text"
            emails.append(ContactCandidate(email, source, SOURCE_CONFIDENCE.get(source, 0.5)))
    return phones, emails


class EnrichmentService:
    """Card -> website -> contact page -> snippets -> social."""

    def __init__(self, crawler=None, web_search: GoogleWebSearch | None = None) -> None:
        self.web_search = web_search or GoogleWebSearch()
        self._crawler = crawler

    @property
    def crawler(self):
        """Imported lazily so enrichment can be unit-tested without a crawler."""
        if self._crawler is None:
            from backend.crawlers.website_crawler import WebsiteCrawler

            self._crawler = WebsiteCrawler()
        return self._crawler

    def enrich(self, card: dict, industry: str | None = None, source_keyword: str | None = None) -> dict:
        """Return a full lead dict, using the card data as the starting point."""
        lead = {field: (card.get(field) or "") for field in LEAD_FIELDS if field not in CONTACT_FIELDS}
        lead["CompanyName"] = lead.get("CompanyName") or card.get("CompanyName", "")
        lead["Industry"] = lead.get("Industry") or industry or ""
        lead["Website"] = lead.get("Website") or card.get("Website", "")
        lead["Headquarters"] = (
            lead.get("Headquarters") or card.get("Location", "") or card.get("Address", "")
        )
        lead["_region"] = infer_phone_region(lead["Website"], lead["Headquarters"])
        lead["_phone_candidates"], lead["_email_candidates"] = _candidates_from_fields(
            card, lead["_region"], "google_maps"
        )
        self._apply_contacts(lead)
        sources: list[str] = ["Maps card"]

        company_name = lead["CompanyName"]
        if not company_name:
            logger.info("Card has no company name, cannot enrich further")
            return self._finish(lead, sources)

        search_results: list[dict] = []
        if not self._has_enough(lead):
            search_results = self._search_for_company(company_name, lead.get("Headquarters"))
            logger.info("Google returned %d results for '%s'", len(search_results), company_name)

            if not lead["Website"]:
                website = self._pick_website(search_results, company_name)
                if website:
                    lead["Website"] = website
                    sources.append("Website found via Google")
                    logger.info("Resolved website for %s: %s", company_name, website)

        if lead["Website"]:
            self._enrich_from_website(lead, industry, source_keyword, sources)
        elif search_results:
            # No website anywhere: mine snippets, then fall back to social profiles.
            self._enrich_from_snippets(lead, search_results, sources)
            self._enrich_from_social(lead, search_results, sources)

        return self._finish(lead, sources)

    def _has_enough(self, lead: dict) -> bool:
        """True once there is a website plus some way to contact the company."""
        return bool(lead.get("Website")) and bool(lead.get("Email") or lead.get("Phone"))

    def _add_candidates(self, lead: dict, phones: list, emails: list) -> None:
        lead["_phone_candidates"] += phones
        lead["_email_candidates"] += emails
        self._apply_contacts(lead)

    def _apply_contacts(self, lead: dict) -> None:
        """Recompute primary/all contact fields from every validated candidate so far."""
        decision_maker = (lead.get("DecisionMakers") or "").split("(")[0].strip()
        lead.update(select_contacts(
            lead["_phone_candidates"], lead["_email_candidates"],
            lead.get("Website") or None, decision_maker or None,
        ))

    def _search_for_company(self, company_name: str, location: str) -> list[dict]:
        for query in company_search_queries(company_name, location):
            results = self.web_search.search(query)
            if results:
                return results
        return []

    def _pick_website(self, results: list[dict], company_name: str) -> str:
        """Best organic result that looks like the company's own website."""
        best = ""
        best_score = -1
        for item in results:
            url = item.get("url", "")
            if not url:
                continue
            domain = parse_domain(url).removeprefix("www.")
            if not domain or is_blacklisted_domain(domain):
                continue
            if is_directory_url(url) or GoogleWebSearch.social_kind(url):
                continue

            score = 0
            if company_name_matches(f"{item.get('title', '')} {url}", company_name):
                score += 5
            if domain.replace("-", "") in re.sub(r"[^a-z0-9]", "", company_name.lower()):
                score += 5
            if url.rstrip("/").count("/") <= 3:
                score += 2  # prefer the homepage over a deep page
            if score > best_score:
                best_score = score
                best = url

        if not best:
            # Last resort: first result that is not a directory or social profile.
            for item in results:
                url = item.get("url", "")
                if url and not is_directory_url(url) and not GoogleWebSearch.social_kind(url):
                    return url
        return best
    def _enrich_from_website(self, lead: dict, industry: str | None,
                         source_keyword: str | None, sources: list[str]) -> None:
        """Full crawl first; the homepage usually carries hero + footer contacts."""
        website = lead["Website"]
        try:
            crawled = self.crawler.crawl(
                website,
                industry=industry,
                source_keyword=source_keyword,
                address=lead.get("Headquarters", ""),
            )
            sources.append("Website crawl")
            for field, value in crawled.items():
                if field == "Notes" or field in CONTACT_FIELDS or field.startswith("_") or not value:
                    continue
                if not lead.get(field):
                    lead[field] = value
            if "_phone_candidates" in crawled:
                self._add_candidates(lead, crawled["_phone_candidates"], crawled["_email_candidates"])
            else:
                self._add_candidates(lead, *_candidates_from_fields(
                    crawled, lead["_region"], "visible_contact_text"
                ))
        except Exception as exc:
            logger.info("Crawl failed for %s: %s", website, exc)
            sources.append("Website crawl failed")

        if not lead.get("Email") or not lead.get("Phone"):
            self._scrape_contact_only(lead, website, sources)

    def _scrape_contact_only(self, lead: dict, website: str, sources: list[str]) -> None:
        """Targeted second pass over contact/about pages for anything still missing."""
        if lead.get("Email") and lead.get("Phone"):
            return
        try:
            from bs4 import BeautifulSoup

            from backend.crawlers.utils import find_page_urls

            html = self.crawler.fetch(website)
            page_urls = find_page_urls(website, BeautifulSoup(html, "lxml"))
            targets = [
                (label, url) for label, url in page_urls.items()
                if label in {"contact", "about", "team"} and url
            ] or [("homepage", website)]

            had_email = bool(lead.get("Email"))
            for label, url in targets:
                try:
                    html = self.crawler.fetch(url)
                except Exception:
                    logger.debug("Could not fetch %s", url)
                    continue
                self._add_candidates(lead, *extract_contact_candidates(
                    html, page_label=label, region=lead["_region"], website=website
                ))
            if lead.get("Email") and not had_email and "Contact page" not in sources:
                sources.append("Contact page")
        except Exception as exc:
            logger.debug("Contact scrape failed for %s: %s", website, exc)

    def _enrich_from_snippets(self, lead: dict, results: list[dict], sources: list[str]) -> None:
        """Harvest emails/phones that Google itself printed in the result snippets."""
        blob = "\n".join(f"{r.get('title', '')} {r.get('snippet', '')}" for r in results)
        had_email, had_phone = bool(lead.get("Email")), bool(lead.get("Phone"))
        self._add_candidates(lead, *extract_text_candidates(blob, lead["_region"]))
        if lead.get("Email") and not had_email:
            sources.append("Email from search snippet")
        if lead.get("Phone") and not had_phone:
            sources.append("Phone from search snippet")
        if not lead.get("Website"):
            website = self._pick_website(results, lead.get("CompanyName", ""))
            if website:
                lead["Website"] = website
                sources.append("Website from search results")

    def _enrich_from_social(self, lead: dict, results: list[dict], sources: list[str]) -> None:
        """No website at all: keep the social profile so the lead is still actionable."""
        if not lead.get("LinkedInURL"):
            for item in results:
                if GoogleWebSearch.social_kind(item.get("url", "")) == "LinkedIn":
                    lead["LinkedInURL"] = item["url"]
                    sources.append("LinkedIn from search")
                    break

        if not lead.get("Phone"):
            for item in results:
                if GoogleWebSearch.social_kind(item.get("url", "")) == "WhatsApp":
                    phone = phone_from_whatsapp_url(item["url"])
                    if phone:
                        self._add_candidates(lead, [ContactCandidate(
                            phone, "whatsapp_link", SOURCE_CONFIDENCE["whatsapp_link"]
                        )], [])
                        sources.append("WhatsApp from search")
                        break

    def _finish(self, lead: dict, sources: list[str]) -> dict:
        """Attach a provenance note and flag whether the lead is worth keeping."""
        self._apply_contacts(lead)
        for key in ("_phone_candidates", "_email_candidates", "_region"):
            lead.pop(key, None)
        found = [field for field in MIN_USEFUL_FIELDS if lead.get(field)]
        notes = f"Discovery: {', '.join(dict.fromkeys(sources))}"
        if len(found) < 2:
            notes += " | Incomplete lead, no website or contact found"
        lead["Notes"] = f"{lead['Notes']} | {notes}" if lead.get("Notes") else notes
        lead["IsUseful"] = len(found) >= 2
        return lead