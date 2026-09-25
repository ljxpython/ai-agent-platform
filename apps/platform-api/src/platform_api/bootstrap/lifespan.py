from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from starlette.concurrency import run_in_threadpool

from platform_api.config import Settings
from platform_api.core.db import build_engine, build_session_factory, create_core_tables
from platform_api.modules.identity.service import IdentityService


def _verify_thread_access_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    columns = (
        {column["name"] for column in inspector.get_columns("thread_access")}
        if inspector.has_table("thread_access")
        else set()
    )
    if not {"provisioning_status", "reserved_at"} <= columns:
        raise RuntimeError(
            "Platform database schema is outdated; apply Alembic revision 20260925_0005 before starting platform-api"
        )


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
            await run_in_threadpool(_verify_thread_access_schema, engine)
            if settings.bootstrap_admin_enabled:
                service = IdentityService(
                    settings=settings, session_factory=session_factory
                )
                await run_in_threadpool(service.ensure_bootstrap_admin)
        yield
    finally:
        if engine is not None:
            await run_in_threadpool(engine.dispose)
        app.state.db_engine = None
        app.state.db_session_factory = None
