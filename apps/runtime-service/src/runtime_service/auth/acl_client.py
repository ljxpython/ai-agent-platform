"""Shared ACL transport, including path-loaded GraphHarbor auth modules."""

import os
from contextlib import asynccontextmanager

import httpx

_acl_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def acl_client_lifespan():
    """Reuse connections for ACL checks for the lifetime of the server."""
    global _acl_client
    async with httpx.AsyncClient(
        timeout=float(os.getenv("PLATFORM_ACL_TIMEOUT_SECONDS", "10.0")),
        trust_env=False,
    ) as client:
        _acl_client = client
        try:
            yield
        finally:
            _acl_client = None


async def post_acl(endpoint: str, payload: dict, headers: dict):
    if _acl_client is not None:
        return await _acl_client.post(endpoint, json=payload, headers=headers)
    # Standalone auth tests/tools may execute without the server lifespan.
    async with httpx.AsyncClient(
        timeout=float(os.getenv("PLATFORM_ACL_TIMEOUT_SECONDS", "10.0")),
        trust_env=False,
    ) as client:
        return await client.post(endpoint, json=payload, headers=headers)
