"""Purpose-bound internal requests; replay consumption belongs to the database."""

import hashlib
import hmac
import json
import time
from uuid import UUID, uuid4


def encode(secret, path, payload):
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    stamp, nonce = str(int(time.time())), str(uuid4())
    canonical = f"gateway-budget/v1\n{stamp}\n{nonce}\nPOST\n{path}\n".encode() + body
    signature = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()
    return body, {
        "content-type": "application/json",
        "x-budget-time": stamp,
        "x-budget-nonce": nonce,
        "x-budget-signature": signature,
    }


def verify(secret, path, headers, body):
    names = ("x-budget-time", "x-budget-nonce", "x-budget-signature")
    if len(secret) < 32 or len(body) > 262144:
        raise ValueError("budget_signature_invalid")
    if hasattr(headers, "getlist") and any(len(headers.getlist(n)) != 1 for n in names):
        raise ValueError("budget_signature_invalid")
    stamp, nonce, signature = (headers.get(n, "") for n in names)
    if (
        not stamp.isascii()
        or not stamp.isdecimal()
        or len(stamp) > 12
        or abs(time.time() - int(stamp)) > 30
        or str(UUID(nonce)) != nonce
    ):
        raise ValueError("budget_signature_invalid")
    canonical = f"gateway-budget/v1\n{stamp}\n{nonce}\nPOST\n{path}\n".encode() + body
    expected = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("budget_signature_invalid")
    return nonce


def decode(body):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    return json.loads(body, object_pairs_hook=unique)
