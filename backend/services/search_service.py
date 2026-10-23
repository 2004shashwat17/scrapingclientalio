import logging
import re
from urllib.parse import urlparse

from backend.crawlers.browser import BrowserSession
from backend.crawlers.search_discovery import SearchDiscovery
from backend.crawlers.utils import is_blacklisted_domain, parse_domain
from backend.repositories.lead_repository import LeadRepository
from backend.services.enrichment_service import EnrichmentService
from backend.services.company_qualification import qualify_dropproof_company
from backend.utils.settings import settings

logger = logging.getLogger("clientalio.search")
DIRECTORY_DOMAINS = {
    "clutch.co",
    "goodfirms.co",
    "sortlist.com",
    "themanifest.com",
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "justdial.com",
    "sulekha.com",
    "yelp.com",
    "g2.com",
    "capterra.com",
    "trustpilot.com",
    "upwork.com",
    "designrush.com",
}


def is_directory_site(url: str) -> bool:
    parsed = urlparse(url)
    domain = parsed.netloc.lower().removeprefix("www.").split(":", 1)[0].rstrip(".")
    return any(domain == directory or domain.endswith("." + directory)
               for directory in DIRECTORY_DOMAINS)


def _company_identity(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()
    normalized = re.sub(r"\b(private limited|pvt ltd|pvt limited|limited|ltd|llp|incorporated|inc|corp|corporation)\b", " ", normalized)
    return " ".join(normalized.split())


class SearchService:
    def __init__(self, on_saved=None):
        self.discovery = SearchDiscovery()
        self.enricher = EnrichmentService()
        self.lead_repo = LeadRepository()
        # Optional callback run with every saved lead (e.g. live API push).
        self.on_saved = on_saved
        # One browser for the whole run; sharing it keeps cookies and the
        # fingerprint consistent, which is what keeps the captcha away.
        self._session: BrowserSession | None = None

    def _ensure_session(self) -> BrowserSession:
        if self._session is None:
            self._session = BrowserSession()
            self._session.start()
            self.discovery._session = self._session
            self.enricher.web_search.set_session(self._session)
        return self._session

    def close(self) -> None:
        """Release the shared browser. Call this at the end of a run."""
        self.discovery.close()
        if self._session is not None:
            self._session.close()
            self._session = None

    def __enter__(self):
        self._ensure_session()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def search_and_save(self, query: str, limit: int = 200, country: str | None = None, industry: str | None = None) -> list[dict]:
        # Open the shared browser before any request so all scraping reuses it.
        self._ensure_session()
        businesses = self.discovery.discover(
            query,
            limit=limit,
            country=country,
            industry=industry,
        )
        results: list[dict] = []
        visited: set[str] = set()
        for business in businesses:
            company_name = business.get("CompanyName", "")
            website = business.get("Website", "")
            location = business.get("Location") or business.get("Address", "")

            # Cards without a website are kept: the enrichment chain looks the
            # company up on Google instead of throwing the lead away.
            domain_identity = parse_domain(website).split(":", 1)[0].rstrip(".") if website else ""
            name_identity = _company_identity(company_name)
            if not domain_identity and not name_identity:
                logger.info("Skipping card with no website and no company name")
                continue
            identities = {f"domain:{domain_identity}"} if domain_identity else set()
            if name_identity:
                identities.add(f"name:{name_identity}")
            if identities & visited:
                continue
            visited.update(identities)

            if website and is_directory_site(website):
                logger.info("Skipping directory listing site: %s", website)
                continue
            if website and is_blacklisted_domain(website):
                logger.info("Skipping blacklisted domain: %s", website)
                continue

            print("FOUND BUSINESS:", company_name, website or "(no website yet)")
            if self.lead_repo.find_duplicates(website or None, None, company_name) is not None:
                logger.info("Skipping duplicate lead: %s", company_name or website)
                continue

            lead = self.enricher.enrich(business, industry=industry or query, source_keyword=query)
            website = lead.get("Website", "")

            if website and is_directory_site(website):
                logger.info("Enriched website is a directory listing, skipping: %s", website)
                continue
            if website and is_blacklisted_domain(website):
                logger.info("Enriched website is blacklisted, skipping: %s", website)
                continue

            if settings.active_product == "dropproof":
                qualified, reason = qualify_dropproof_company(
                    lead.get("CompanyName") or company_name,
                    website,
                    lead.get("_qualification_text", ""),
                )
                if not qualified:
                    logger.info("Skipping unqualified DropProof prospect %s: %s", company_name, reason)
                    continue

            lead["Headquarters"] = lead.get("Headquarters") or location
            if not lead.get("IsUseful", True):
                # Too empty to be worth storing; the card told us nothing usable.
                logger.info("Discarding unusable lead: %s", company_name or "(unnamed)")
                continue

            try:
                saved = self.lead_repo.create_or_update(lead)
            except Exception as exc:
                print("FAILED:", company_name, exc)
                logger.warning("Failed to save lead %s: %s", website or company_name, exc)
                continue

            print("SAVED:", saved.get("CompanyName"), saved.get("Email"))
            results.append(saved)
            if self.on_saved:
                try:
                    self.on_saved(saved)
                except Exception as exc:
                    logger.warning("on_saved hook failed for %s: %s", company_name, exc)

        return results
