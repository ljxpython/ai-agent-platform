from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from platform_api.bootstrap.lifespan import lifespan
from platform_api.config import load_settings
from platform_api.core.errors import register_exception_handlers
from platform_api.entrypoints.http.router import api_router
from platform_api.entrypoints.http.middleware import (
    register_audit_log_middleware,
    register_auth_context_middleware,
    register_request_context_middleware,
)


def create_app() -> FastAPI:
    load_dotenv()
    settings = load_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url="/redoc" if settings.api_docs_enabled else None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    register_auth_context_middleware(app, settings)
    register_request_context_middleware(app)
    register_audit_log_middleware(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)
    return app
