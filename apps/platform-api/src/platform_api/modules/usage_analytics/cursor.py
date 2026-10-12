"""Authenticated encryption keeps filtered-out Run IDs inside the platform."""

import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from platform_api.core.errors import BadRequestError, ServiceUnavailableError


def _cipher(secret):
    if len(secret.encode()) < 32:
        raise ServiceUnavailableError(
            code="usage_query_not_configured",
            message="Usage query authentication is not configured",
        )
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"usage-dashboard-cursor/v1",
    ).derive(secret.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def binding(*, actor, tenant_id, project_id, query):
    filters = query.model_dump(mode="json", by_alias=True, exclude={"cursor", "limit"})
    payload = [
        actor.user_id or actor.subject,
        actor.principal_type,
        actor.credential_id,
        tenant_id,
        project_id,
        filters,
        "last_matching_call_at,run_id:desc",
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def encode_cursor(secret, scope, position, cutoff):
    return (
        _cipher(secret)
        .encrypt(
            json.dumps(
                {
                    "version": 1,
                    "binding": scope,
                    "position": position,
                    "cutoff": cutoff,
                },
                separators=(",", ":"),
            ).encode()
        )
        .decode()
    )


def decode_cursor(secret, scope, value):
    try:
        data = json.loads(_cipher(secret).decrypt(value.encode(), ttl=900))
        if (
            data["version"] != 1
            or data["binding"] != scope
            or set(data) != {"version", "binding", "position", "cutoff"}
        ):
            raise ValueError("Cursor scope mismatch")
        return data["position"], data["cutoff"]
    except (InvalidToken, ValueError, TypeError, KeyError) as exc:
        raise BadRequestError(
            code="invalid_usage_analytics_query",
            message="Usage cursor expired or does not match this query",
        ) from exc
