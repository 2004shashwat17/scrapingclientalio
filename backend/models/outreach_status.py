from sqlalchemy import Boolean, Column, DateTime, Integer, String
from datetime import datetime
from backend.models.base import Base


class OutreachStatus(Base):
    __tablename__ = "outreachstatus"

    Id = Column(Integer, primary_key=True, index=True)
    LeadId = Column(Integer, nullable=False)
    Contacted = Column(Boolean, default=False)
    ResponseReceived = Column(Boolean, default=False)
    Notes = Column(String(2048), nullable=True)
    LastContactDate = Column(DateTime, default=datetime.utcnow)
