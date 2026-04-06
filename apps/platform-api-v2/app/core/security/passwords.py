from __future__ import annotations

import base64
import hashlib
import hmac
import os

PBKDF2_ITERATIONS = 210_000


def hash_password(raw_password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        raw_password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    encoded_salt = base64.b64encode(salt).decode("ascii")
    encoded_digest = base64.b64encode(digest).decode("ascii")
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${encoded_salt}${encoded_digest}"


def verify_password(raw_password: str, password_hash: str) -> bool:
    parts = password_hash.split("$", 3)
    if len(parts) != 4:
        return False
    algorithm, iterations_str, encoded_salt, encoded_digest = parts
    if algorithm != "pbkdf2_sha256":
        return False
    try:
        iterations = int(iterations_str)
        salt = base64.b64decode(encoded_salt.encode("ascii"))
        expected = base64.b64decode(encoded_digest.encode("ascii"))
    except (TypeError, ValueError):
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        raw_password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)
