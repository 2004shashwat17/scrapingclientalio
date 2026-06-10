import logging
from urllib.parse import urlparse

from backend.crawlers.search_discovery import SearchDiscovery
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
        providers = []
        if settings.serper_api_key:
            providers.append("serper")
        if settings.brave_search_api_key:
            providers.append("brave")
        providers.append("bing")

        domains = self.discovery.discover(
            query,
            limit=limit,
            country=country,
            industry=industry,
            providers=providers,
        )
        results: list[dict] = []
        for domain in domains:
            if is_directory_site(domain):
                logger.info("Skipping directory listing site: %s", domain)
                continue

            print("FOUND DOMAIN:", domain)
            if self.lead_repo.find_duplicates(domain, None, domain) is not None:
                logger.info("Skipping duplicate site: %s", domain)
                continue

            try:
                saved = self.crawl_service.execute_crawl(domain, industry=industry or query)
                print("SAVED:", saved)
                results.append({
                    "LeadId": saved["LeadId"],
                    "CompanyName": saved["CompanyName"],
                    "Website": saved["Website"],
                    "Industry": saved["Industry"],
                    "LeadScore": saved["LeadScore"],
                    "Priority": saved["Priority"],
                })
            except Exception as exc:
                print("FAILED:", domain, exc)
                logger.warning("Failed to crawl %s: %s", domain, exc)
        return results
