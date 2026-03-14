from __future__ import annotations

from fastapi import HTTPException, Request


def require_db_session_factory(request: Request):
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="database_not_enabled")
    return session_factory
