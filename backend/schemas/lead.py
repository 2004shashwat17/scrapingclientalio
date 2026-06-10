from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl, EmailStr


class LeadBase(BaseModel):
    CompanyName: str
    Website: HttpUrl
    Industry: Optional[str] = None
    Email: Optional[EmailStr] = None
    Phone: Optional[str] = None
    LinkedIn: Optional[HttpUrl] = None
    Facebook: Optional[HttpUrl] = None
    Instagram: Optional[HttpUrl] = None
    Twitter: Optional[HttpUrl] = None
    YouTube: Optional[HttpUrl] = None
    ContactPage: Optional[HttpUrl] = None
    HasTestimonials: bool = False
    HasVideoTestimonials: bool = False
    HasCaseStudies: bool = False
    HasGoogleReviews: bool = False


class LeadCreate(LeadBase):
    pass


class LeadResponse(LeadBase):
    LeadId: int
    LeadScore: int
    Priority: str
    CreatedDate: datetime

    class Config:
        from_attributes = True
