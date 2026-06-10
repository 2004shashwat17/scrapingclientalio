from backend.models.outreach_status import OutreachStatus
from sqlalchemy.orm import Session


class OutreachRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_lead(self, lead_id: int) -> OutreachStatus | None:
        return self.db.query(OutreachStatus).filter(OutreachStatus.LeadId == lead_id).one_or_none()

    def create_or_update(self, lead_id: int, contacted: bool, response_received: bool, notes: str | None, last_contact_date):
        existing = self.get_by_lead(lead_id)
        if existing:
            existing.Contacted = contacted
            existing.ResponseReceived = response_received
            existing.Notes = notes
            existing.LastContactDate = last_contact_date
            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        status = OutreachStatus(
            LeadId=lead_id,
            Contacted=contacted,
            ResponseReceived=response_received,
            Notes=notes,
            LastContactDate=last_contact_date,
        )
        self.db.add(status)
        self.db.commit()
        self.db.refresh(status)
        return status
