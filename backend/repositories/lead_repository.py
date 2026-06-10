from backend.storage.csv_store import LeadStore


class LeadRepository:
    def __init__(self):
        self.store = LeadStore()

    def get_by_id(self, lead_id: int) -> dict | None:
        return self.store.get_by_id(lead_id)

    def find_duplicates(self, website: str, email: str | None, company_name: str) -> dict | None:
        return self.store.find_duplicates(website, email, company_name)

    def list(self, offset: int = 0, limit: int = 200) -> list[dict]:
        return self.store.list(offset=offset, limit=limit)

    def create_or_update(self, payload: dict) -> dict:
        return self.store.save(payload)
