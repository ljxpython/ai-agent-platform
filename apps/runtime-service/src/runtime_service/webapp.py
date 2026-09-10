"""Agent Server application lifespan owned by Runtime Service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header

from runtime_service.auth.platform import authenticate

from runtime_service.observability import close_langfuse, initialize_langfuse


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_langfuse()
    try:
        yield
    finally:
        close_langfuse(timeout_seconds=5.0)


app = FastAPI(lifespan=lifespan)

@app.get("/internal/capabilities/tools")
async def tool_catalog(authorization: str | None = Header(default=None)) -> dict:
    """Runtime owns tool capabilities; the platform owns project grants."""
    await authenticate(authorization)
    from runtime_service.services.demo.showcase_demo.agent import _TOOL_PERMISSIONS

    permissions = {"read_reference": "runtime.tool.read", **_TOOL_PERMISSIONS}
    return {"tools": [
        {"tool_key": name, "name": name, "source": "runtime",
         "permissions": [permission]}
        for name, permission in sorted(permissions.items())
    ]}


__all__ = ["app", "lifespan"]
