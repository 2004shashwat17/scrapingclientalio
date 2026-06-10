from pydantic import BaseModel, HttpUrl


class CrawlRequest(BaseModel):
    website: HttpUrl
