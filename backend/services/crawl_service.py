import logging
from backend.crawlers.website_crawler import WebsiteCrawler
from backend.repositories.crawl_log_repository import CrawlLogRepository
from backend.services.lead_service import LeadService

logger = logging.getLogger("clientalio.crawl")


class CrawlService:
    def __init__(self):
        self.crawl_repo = CrawlLogRepository()
        self.lead_service = LeadService()
        self.crawler = WebsiteCrawler()

    def execute_crawl(self, website: str, industry: str | None = None, source_keyword: str | None = None, address: str | None = None) -> dict:
        try:
            crawl_data = self.crawler.crawl(
                website,
                industry=industry,
                source_keyword=source_keyword,
                address=address,
            )
            saved = self.lead_service.save_lead(crawl_data)
            self.crawl_repo.create(website, "Success", "Crawl completed")
            return saved
        except Exception as exc:
            logger.exception("Crawl failed: %s", exc)
            self.crawl_repo.create(website, "Failed", str(exc))
            raise
