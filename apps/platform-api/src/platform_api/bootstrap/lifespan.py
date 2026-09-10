from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from platform_api.config import Settings
from platform_api.core.db import build_engine, build_session_factory, create_core_tables
from platform_api.modules.identity.service import IdentityService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings

    engine = None
    try:
        if settings.platform_db_enabled:
            engine = build_engine(settings.database_url or "")
            app.state.db_engine = engine
            session_factory = build_session_factory(engine)
            app.state.db_session_factory = session_factory
            if settings.platform_db_auto_create:
                await run_in_threadpool(create_core_tables, engine)
            if settings.bootstrap_admin_enabled:
                service = IdentityService(settings=settings, session_factory=session_factory)
                await run_in_threadpool(service.ensure_bootstrap_admin)
        yield
    finally:
        if engine is not None:
            await run_in_threadpool(engine.dispose)
        app.state.db_engine = None
        app.state.db_session_factory = None
