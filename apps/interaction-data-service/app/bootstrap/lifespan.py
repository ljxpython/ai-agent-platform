from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from app.config import Settings
from app.db.init_db import create_core_tables
from app.db.session import build_engine, build_session_factory
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Reserved seam for future shared resources such as DB engines or HTTP clients.
    settings: Settings = app.state.settings

    if settings.interaction_db_enabled:
        app.state.db_engine = build_engine(settings)
        app.state.db_session_factory = build_session_factory(app.state.db_engine)
        if settings.interaction_db_auto_create:
            create_core_tables(app.state.db_engine)

    try:
        yield
    finally:
        if settings.interaction_db_enabled:
            app.state.db_engine.dispose()
