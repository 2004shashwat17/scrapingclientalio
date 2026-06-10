from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from backend.models.base import Base


class Lead(Base):
    __tablename__ = "leads"

    LeadId = Column(Integer, primary_key=True, index=True)
    CompanyName = Column(String(256), nullable=False)
    Website = Column(String(512), nullable=False, unique=True)
    Industry = Column(String(128), nullable=True)
    Email = Column(String(256), nullable=True)
    Phone = Column(String(128), nullable=True)
    LinkedIn = Column(String(512), nullable=True)
    Facebook = Column(String(512), nullable=True)
    Instagram = Column(String(512), nullable=True)
    Twitter = Column(String(512), nullable=True)
    YouTube = Column(String(512), nullable=True)
    ContactPage = Column(String(512), nullable=True)
    HasTestimonials = Column(Boolean, default=False)
    HasVideoTestimonials = Column(Boolean, default=False)
    HasCaseStudies = Column(Boolean, default=False)
    HasGoogleReviews = Column(Boolean, default=False)
    LeadScore = Column(Integer, default=0)
    Priority = Column(String(32), default="Low Priority")
    CreatedDate = Column(DateTime, default=datetime.utcnow)
