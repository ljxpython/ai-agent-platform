from __future__ import annotations

from app.api import router as api_router
from app.bootstrap.lifespan import lifespan
from app.config import load_settings
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    load_dotenv()
    settings = load_settings()

    app = FastAPI(
        title="Interaction Data Service",
        version=settings.service_version,
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url="/redoc" if settings.api_docs_enabled else None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.include_router(api_router)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.service_cors_allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/_service/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name}

    return app
