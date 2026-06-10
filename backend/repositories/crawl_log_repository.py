from backend.storage.csv_store import CrawlLogStore


class CrawlLogRepository:
    def __init__(self):
        self.store = CrawlLogStore()

    def create(self, website: str, status: str, message: str | None = None) -> dict:
        return self.store.create(website, status, message)
