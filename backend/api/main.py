import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.api.routers import search, crawl, leads, export
from backend.storage import ensure_csv_storage
from backend.utils.logging import logger


def create_app() -> FastAPI:
    app = FastAPI(title="Clientalio Lead Generation Platform")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(search.router, prefix="/api")
    app.include_router(crawl.router, prefix="/api")
    app.include_router(leads.router, prefix="/api")
    app.include_router(export.router, prefix="/api")

    if os.path.isdir(os.path.join(os.path.dirname(__file__), "../../frontend")):
        app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "../../frontend"), html=True), name="frontend")

    @app.on_event("startup")
    def on_startup() -> None:
        logger.info("Ensuring CSV storage exists")
        ensure_csv_storage()

    return app


app = create_app()
