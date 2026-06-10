from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String
from backend.models.base import Base


class CrawlLog(Base):
    __tablename__ = "crawllogs"

    Id = Column(Integer, primary_key=True, index=True)
    Website = Column(String(512), nullable=False)
    Status = Column(String(64), nullable=False)
    Message = Column(String(2048), nullable=True)
    CreatedDate = Column(DateTime, default=datetime.utcnow)
