from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl


class LeadBase(BaseModel):
    CompanyName: str
    Website: HttpUrl
    Headquarters: Optional[str] = None
    CitiesServed: Optional[str] = None
    Industry: Optional[str] = None
    FleetSizePublic: Optional[str] = None
    Employees: Optional[str] = None
    RevenuePublic: Optional[str] = None
    DecisionMakers: Optional[str] = None
    LinkedInURL: Optional[HttpUrl] = None
    # Comma-separated list; first value is the primary email.
    Email: Optional[str] = None
    Phone: Optional[str] = None
    CRMTMSUsedPublic: Optional[str] = None
    DeliveryVolumePublic: Optional[str] = None
    ExistingPODSolution: Optional[str] = None
    Notes: Optional[str] = None


class LeadCreate(LeadBase):
    pass


class LeadResponse(LeadBase):
    LeadId: int
    CreatedDate: datetime

    class Config:
        from_attributes = True
