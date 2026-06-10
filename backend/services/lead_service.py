from backend.repositories.lead_repository import LeadRepository
from backend.services.scoring_service import calculate_lead_score, translate_priority


class LeadService:
    def __init__(self):
        self.repository = LeadRepository()

    def list_leads(self, offset: int = 0, limit: int = 200):
        return self.repository.list(offset=offset, limit=limit)

    def get_lead(self, lead_id: int):
        return self.repository.get_by_id(lead_id)

    def save_lead(self, payload: dict):
        score = calculate_lead_score(payload.get("Industry"), {
            "HasTestimonials": payload.get("HasTestimonials", False),
            "HasVideoTestimonials": payload.get("HasVideoTestimonials", False),
            "HasCaseStudies": payload.get("HasCaseStudies", False),
            "HasGoogleReviews": payload.get("HasGoogleReviews", False),
        })
        payload["LeadScore"] = score
        payload["Priority"] = translate_priority(score)
        return self.repository.create_or_update(payload)
