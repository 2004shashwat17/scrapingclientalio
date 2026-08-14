from __future__ import annotations

import logging
from urllib.parse import urlparse

from backend.crawlers.search_discovery import SearchDiscovery
from backend.crawlers.utils import is_blacklisted_domain, parse_domain
from backend.repositories.lead_repository import LeadRepository
from backend.services.crawl_service import CrawlService
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
    domain = parsed.netloc.lower().removeprefix("www.")
    return any(directory in domain for directory in DIRECTORY_DOMAINS)


class SearchService:
    def __init__(self):
        self.discovery = SearchDiscovery()
        self.crawl_service = CrawlService()
        self.lead_repo = LeadRepository()

    def search_and_save(self, query: str, limit: int = 200, country: str | None = None, industry: str | None = None) -> list[dict]:
        businesses = self.discovery.discover(
            query,
            limit=limit,
            country=country,
            industry=industry,
        )
        results: list[dict] = []
        visited: set[str] = set()
        for business in businesses:
            website = business.get("Website")
            if not website:
                continue
            domain = parse_domain(website)
            if domain in visited:
                continue
            visited.add(domain)
            if is_directory_site(website):
                logger.info("Skipping directory listing site: %s", website)
                continue
            if is_blacklisted_domain(website):
                logger.info("Skipping blacklisted domain: %s", website)
                continue

            print("FOUND BUSINESS:", business.get("CompanyName"), website)
            if self.lead_repo.find_duplicates(website, None, business.get("CompanyName", "")) is not None:
                logger.info("Skipping duplicate site: %s", website)
                continue

            try:
                saved = self.crawl_service.execute_crawl(
                    website,
                    industry=industry or query,
                    source_keyword=query,
                    address=business.get("Address", "") or business.get("Location", ""),
                )
                print("SAVED:", saved)
                results.append({
                    "LeadId": saved["LeadId"],
                    "CompanyName": saved["CompanyName"],
                    "Website": saved["Website"],
                    "Headquarters": saved.get("Headquarters", ""),
                    "CitiesServed": saved.get("CitiesServed", ""),
                    "Industry": saved["Industry"],
                    "FleetSizePublic": saved.get("FleetSizePublic", ""),
                    "Employees": saved.get("Employees", ""),
                    "RevenuePublic": saved.get("RevenuePublic", ""),
                    "DecisionMakers": saved.get("DecisionMakers", ""),
                    "LinkedInURL": saved.get("LinkedInURL", ""),
                    "Email": saved.get("Email", ""),
                    "Phone": saved.get("Phone", ""),
                    "CRMTMSUsedPublic": saved.get("CRMTMSUsedPublic", ""),
                    "DeliveryVolumePublic": saved.get("DeliveryVolumePublic", ""),
                    "ExistingPODSolution": saved.get("ExistingPODSolution", ""),
                    "Notes": saved.get("Notes", ""),
                })
            except Exception as exc:
                print("FAILED:", website, exc)
                logger.warning("Failed to crawl %s: %s", website, exc)
        return results
