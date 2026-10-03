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

from backend.crawlers.google_web_search import GoogleWebSearch, company_search_queries
from backend.crawlers.utils import (
    choose_best_business_email,
    choose_best_phone,
    extract_emails,
    extract_phones,
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

SNIPPET_EMAIL = re.compile(r"[\w.\-+]+@[\w\-]+\.[\w.\-]{2,}")
SNIPPET_PHONE = re.compile(r"\+?[0-9][0-9\s\-().]{6,}[0-9]")


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
    "LinkedInURL", "Email", "Phone", "CRMTMSUsedPublic",
    "DeliveryVolumePublic", "ExistingPODSolution", "Notes",
]
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
        lead = {field: (card.get(field) or "") for field in LEAD_FIELDS}
        lead["CompanyName"] = lead.get("CompanyName") or card.get("CompanyName", "")
        lead["Industry"] = lead.get("Industry") or industry or ""
        lead["Website"] = lead.get("Website") or card.get("Website", "")
        lead["Phone"] = lead.get("Phone") or card.get("Phone", "")
        lead["Headquarters"] = (
            lead.get("Headquarters") or card.get("Location", "") or card.get("Address", "")
        )
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
                if field == "Notes" or not value:
                    continue
                if not lead.get(field):
                    lead[field] = value
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
                url for label, url in page_urls.items()
                if label in {"contact", "about", "team"} and url
            ] or [website]

            blob = ""
            for url in targets:
                try:
                    blob += "\n" + self.crawler.fetch(url)
                except Exception:
                    logger.debug("Could not fetch %s", url)

            if not lead.get("Email"):
                best, _, _ = choose_best_business_email(extract_emails(blob), website)
                if best:
                    lead["Email"] = best
                    if "Contact page" not in sources:
                        sources.append("Contact page")
            if not lead.get("Phone"):
                phone, _ = choose_best_phone(extract_phones(blob))
                if phone:
                    lead["Phone"] = phone
        except Exception as exc:
            logger.debug("Contact scrape failed for %s: %s", website, exc)

    def _enrich_from_snippets(self, lead: dict, results: list[dict], sources: list[str]) -> None:
        """Harvest emails/phones that Google itself printed in the result snippets."""
        blob = "\n".join(f"{r.get('title', '')} {r.get('snippet', '')}" for r in results)
        if not lead.get("Email"):
            candidates = [e for e in SNIPPET_EMAIL.findall(blob) if "." in e.split("@")[-1]]
            best, _, _ = choose_best_business_email(candidates)
            if best:
                lead["Email"] = best
                sources.append("Email from search snippet")
        if not lead.get("Phone"):
            phone, _ = choose_best_phone(SNIPPET_PHONE.findall(blob))
            if phone:
                lead["Phone"] = phone
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
                    lead["Phone"] = item["url"]
                    sources.append("WhatsApp from search")
                    break

    def _finish(self, lead: dict, sources: list[str]) -> dict:
        """Attach a provenance note and flag whether the lead is worth keeping."""
        found = [field for field in MIN_USEFUL_FIELDS if lead.get(field)]
        notes = f"Discovery: {', '.join(dict.fromkeys(sources))}"
        if len(found) < 2:
            notes += " | Incomplete lead, no website or contact found"
        lead["Notes"] = f"{lead['Notes']} | {notes}" if lead.get("Notes") else notes
        lead["IsUseful"] = len(found) >= 2
        return lead