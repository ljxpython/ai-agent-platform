"""Purpose-bound HMAC readers; ordinary delegation JWTs grant no access."""

import hashlib
import hmac
import json
import os
import time

import psycopg
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import ValidationError

from runtime_service.observability.usage_analytics import (
    AggregateQuery,
    RunsQuery,
    query_aggregate,
    query_runs,
)

router = APIRouter(prefix="/internal/usage", tags=["usage-analytics"])


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


async def _verified_body(request):
    if request.query_params:
        raise HTTPException(400, {"code": "invalid_usage_analytics_query"})
    secret = os.getenv("PLATFORM_RUNTIME_DELEGATION_SECRET", "").encode()
    if len(secret) < 32:
        raise HTTPException(503, {"code": "usage_query_not_configured"})
    names = ("x-usage-query-timestamp", "x-usage-query-signature")
    if any(len(request.headers.getlist(name)) != 1 for name in names):
        raise HTTPException(401, {"code": "usage_query_unauthorized"})
    stamp, signature = (request.headers[name] for name in names)
    if (
        len(stamp) > 12
        or not stamp.isascii()
        or not stamp.isdecimal()
        or abs(time.time() - int(stamp)) > 30
        or not signature.isascii()
        or len(signature) != 71
    ):
        raise HTTPException(401, {"code": "usage_query_unauthorized"})
    body = bytearray()
    async for part in request.stream():
        body.extend(part)
        if len(body) > 65536:
            raise HTTPException(413, {"code": "usage_query_body_too_large"})
    canonical = f"usage-query/v1\n{stamp}\nPOST\n{request.url.path}\n".encode() + body
    expected = "sha256=" + hmac.new(secret, canonical, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(401, {"code": "usage_query_unauthorized"})
    return bytes(body)


async def _query(request, response, model, execute):
    body = await _verified_body(request)
    response.headers["Cache-Control"] = "no-store"
    try:
        json.loads(body, object_pairs_hook=_unique_keys)
        query = model.model_validate_json(body)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(400, {"code": "invalid_usage_analytics_query"}) from exc
    try:
        return await execute(query)
    except ValueError as exc:
        code = (
            "usage_aggregate_range_exceeded"
            if str(exc) in {"unsafe_usage_total", "usage_aggregate_range_exceeded"}
            else "invalid_usage_analytics_query"
        )
        raise HTTPException(
            422 if code == "usage_aggregate_range_exceeded" else 400, {"code": code}
        ) from exc
    except (
        psycopg.OperationalError,
        psycopg.errors.QueryCanceled,
        psycopg.errors.LockNotAvailable,
        KeyError,
    ) as exc:
        raise HTTPException(503, {"code": "usage_backend_unavailable"}) from exc


@router.post("/aggregate")
async def aggregate_endpoint(request: Request, response: Response):
    return await _query(request, response, AggregateQuery, query_aggregate)


@router.post("/runs/query")
async def runs_endpoint(request: Request, response: Response):
    return await _query(request, response, RunsQuery, query_runs)
