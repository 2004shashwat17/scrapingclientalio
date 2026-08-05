from backend.repositories.lead_repository import LeadRepository


class LeadService:
    def __init__(self):
        self.repository = LeadRepository()

    def list_leads(self, offset: int = 0, limit: int = 200):
        return self.repository.list(offset=offset, limit=limit)

    def get_lead(self, lead_id: int):
        return self.repository.get_by_id(lead_id)

    def save_lead(self, payload: dict):
        return self.repository.create_or_update(payload)
