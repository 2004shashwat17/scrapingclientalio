from fastapi import APIRouter, HTTPException
from backend.schemas.crawl import CrawlRequest
from backend.services.crawl_service import CrawlService

router = APIRouter()


@router.post("/crawl")
def crawl_website(payload: CrawlRequest):
    try:
        saved = CrawlService().execute_crawl(str(payload.website))
        return {"status": "success", "lead": saved}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
