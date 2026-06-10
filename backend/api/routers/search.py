from fastapi import APIRouter, HTTPException
from backend.schemas.search import SearchRequest
from backend.services.search_service import SearchService

router = APIRouter()


@router.post("/search")
def search_leads(payload: SearchRequest):
    try:
        results = SearchService().search_and_save(
            query=payload.query,
            limit=payload.limit,
            country=payload.country,
            industry=payload.industry,
        )
        return {"count": len(results), "results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
