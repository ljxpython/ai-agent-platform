from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import Settings


class InvalidTokenError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))


def _sign(message: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url_encode(digest)


def _encode(payload: dict[str, Any], secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_part = _b64url_encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    payload_part = _b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    signature = _sign(signing_input, secret)
    return f"{header_part}.{payload_part}.{signature}"


def _decode(token: str, secret: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise InvalidTokenError("invalid token format")
    header_part, payload_part, signature = parts
    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    expected = _sign(signing_input, secret)
    if not hmac.compare_digest(expected, signature):
        raise InvalidTokenError("invalid token signature")
    try:
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise InvalidTokenError("invalid token payload") from exc

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise InvalidTokenError("missing token exp")
    if int(_now().timestamp()) >= exp:
        raise InvalidTokenError("token expired")
    return payload


def create_access_token(*, user_id: str, username: str, settings: Settings) -> str:
    now = _now()
    payload: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(seconds=settings.jwt_access_ttl_seconds)).timestamp()
        ),
    }
    return _encode(payload, settings.jwt_access_secret)


def create_refresh_token(
    *,
    user_id: str,
    username: str,
    settings: Settings,
) -> tuple[str, str]:
    now = _now()
    token_id = uuid.uuid4().hex
    payload: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "type": "refresh",
        "jti": token_id,
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(seconds=settings.jwt_refresh_ttl_seconds)).timestamp()
        ),
    }
    return _encode(payload, settings.jwt_refresh_secret), token_id


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    payload = _decode(token, settings.jwt_access_secret)
    if payload.get("type") != "access":
        raise InvalidTokenError("invalid access token type")
    return payload


def decode_refresh_token(token: str, settings: Settings) -> dict[str, Any]:
    payload = _decode(token, settings.jwt_refresh_secret)
    if payload.get("type") != "refresh":
        raise InvalidTokenError("invalid refresh token type")
    return payload
