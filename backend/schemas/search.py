from typing import Optional
from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 200
    country: Optional[str] = None
    industry: Optional[str] = None
