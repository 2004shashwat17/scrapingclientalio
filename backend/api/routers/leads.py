from fastapi import APIRouter, HTTPException, Query
from backend.services.lead_service import LeadService
from backend.schemas.lead import LeadResponse

router = APIRouter()


@router.get("/leads", response_model=list[LeadResponse])
def get_leads(offset: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000)):
    return LeadService().list_leads(offset=offset, limit=limit)


@router.get("/lead/{lead_id}", response_model=LeadResponse)
def get_lead(lead_id: int):
    lead = LeadService().get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead
