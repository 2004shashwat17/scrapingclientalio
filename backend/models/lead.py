from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String
from backend.models.base import Base


class Lead(Base):
    __tablename__ = "leads"

    LeadId = Column(Integer, primary_key=True, index=True)
    CompanyName = Column(String(256), nullable=False)
    Website = Column(String(512), nullable=False, unique=True)
    Headquarters = Column(String(256), nullable=True)
    CitiesServed = Column(String(512), nullable=True)
    Industry = Column(String(128), nullable=True)
    FleetSizePublic = Column(String(128), nullable=True)
    Employees = Column(String(128), nullable=True)
    RevenuePublic = Column(String(128), nullable=True)
    DecisionMakers = Column(String(256), nullable=True)
    LinkedInURL = Column(String(512), nullable=True)
    Email = Column(String(256), nullable=True)
    Phone = Column(String(128), nullable=True)
    CRMTMSUsedPublic = Column(String(256), nullable=True)
    DeliveryVolumePublic = Column(String(256), nullable=True)
    ExistingPODSolution = Column(String(256), nullable=True)
    Notes = Column(String(1024), nullable=True)
    CreatedDate = Column(DateTime, default=datetime.utcnow)
