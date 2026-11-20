"""Local boundary checks; never send raw text to a model to decide exportability."""

import hashlib
import json
import re
import unicodedata

from platform_api.core.errors import BadRequestError

SECRET_PATTERNS = (
    re.compile(r"\bsk-[a-z0-9_-]{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+\S+", re.IGNORECASE),
)

KV_SECRET = re.compile(
    r"(?i)\b(api[_ -]?key|authorization|password|secret|access_token|refresh_token|private_key|token)\s*[:=]\s*(\S+)"
)

EXCLUDED_SECRET_VALUES = {
    "none",
    "null",
    "true",
    "false",
    "str",
    "int",
    "bool",
    "float",
    "dict",
    "list",
    "tuple",
    "set",
    "undefined",
    "nil",
}


def is_secret_present(value: str) -> bool:
    clean = value.replace('"', "").replace("'", "")
    for pattern in SECRET_PATTERNS:
        if pattern.search(clean):
            return True
    for match in KV_SECRET.finditer(clean):
        val = match.group(2).strip().rstrip(",;}]")
        # Exclude language constructs: function or method calls
        if "(" in val or ")" in val:
            continue
        # Exclude type annotations and language literals
        if val.lower() in EXCLUDED_SECRET_VALUES:
            continue
        # Exclude attribute references (e.g. self.token, req.auth, ctx.val)
        if re.match(r"^[a-zA-Z_]\w*\.[a-zA-Z_]\w*$", val):
            continue
        return True
    return False


class _SecretDetector:
    def search(self, text: str):
        if is_secret_present(text):
            return True
        return None


SECRET = _SecretDetector()
PII = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|(?<!\d)1[3-9]\d{9}(?!\d)|(?<!\d)\d{17}[\dXx](?!\d)"
)


def require_synthetic(value: str, *, max_bytes: int = 250_000) -> None:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Cf")
    if len(value.encode()) > max_bytes or clean_synthetic(value) != normalized:
        raise BadRequestError(
            code="evaluation_synthetic_invalid",
            message="请仅提交不含个人信息或密钥的合成说明和文件。",
        )


def clean_synthetic(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = "".join(c for c in value if unicodedata.category(c) != "Cf")
    if SECRET.search(value):
        raise BadRequestError(
            code="evaluation_export_secret",
            message="材料疑似包含秘密，请在源侧移除后重新提交。",
        )
    substitutions = {}

    def replace(match):
        return substitutions.setdefault(
            match[0], f"[REDACTED_{len(substitutions) + 1}]"
        )

    return PII.sub(replace, value)


def require_safe_material(value: str) -> None:
    """Authoring may use business material, but never unreviewed identifiers or secrets."""
    prepare_business_material(value)
    try:
        require_synthetic(value)
    except BadRequestError as exc:
        if exc.code == "evaluation_synthetic_invalid":
            raise BadRequestError(
                code="evaluation_material_invalid",
                message="资料过大或包含个人标识，请脱敏后再提交；来源会话可通过“转为评测集”自动处理常见标识。",
            ) from None
        raise


def prepare_business_material(value, *, max_bytes: int = 250_000):
    """Redact consistent personal identifiers before persisting an exported copy."""
    if len(json.dumps(value, ensure_ascii=False, default=str).encode()) > max_bytes:
        raise BadRequestError(
            code="evaluation_material_too_large",
            message=f"会话资料超过{max_bytes // 1000}KB，请缩小范围。",
        )
    count = 0
    secret_keys = {
        "password",
        "api_key",
        "apikey",
        "authorization",
        "access_token",
        "refresh_token",
        "secret",
        "private_key",
        "token",
    }

    def visit(part):
        nonlocal count
        if isinstance(part, dict):
            for key, content in part.items():
                if (
                    str(key).lower().replace("-", "_") in secret_keys
                    and isinstance(content, str)
                    and content.strip()
                ):
                    raise BadRequestError(
                        code="evaluation_export_secret",
                        message="资料包含凭据字段，请在源侧移除后重新转换。",
                    )
            return {visit(key): visit(content) for key, content in part.items()}
        if isinstance(part, list):
            return [visit(content) for content in part]
        if not isinstance(part, str):
            return part
        normalized = unicodedata.normalize("NFKC", part)
        normalized = "".join(c for c in normalized if unicodedata.category(c) != "Cf")
        # Quoted JSON keys in tool output must not bypass the credential check.
        if SECRET.search(normalized.replace('"', "").replace("'", "")):
            raise BadRequestError(
                code="evaluation_export_secret",
                message="材料疑似包含密钥，请在源侧移除后重新转换。",
            )

        # Match normalized identifiers without rewriting the source's punctuation or code.
        characters, positions = [], []
        for index, character in enumerate(part):
            for normalized_character in unicodedata.normalize("NFKC", character):
                if unicodedata.category(normalized_character) != "Cf":
                    characters.append(normalized_character)
                    positions.append(index)
        pieces, start = [], 0
        for match in PII.finditer("".join(characters)):
            count += 1
            pieces.append(part[start : positions[match.start()]])
            pieces.append(
                "[个人标识_" + hashlib.sha256(match[0].encode()).hexdigest()[:12] + "]"
            )
            start = positions[match.end() - 1] + 1
        return "".join([*pieces, part[start:]])

    result = visit(value)
    return result, {
        "policy": "business-material-v1",
        "redacted_occurrences": count,
        "notice": "常见邮箱、手机号和身份证号已替换；密钥拦截。自动检查不能覆盖所有敏感内容，请复核资料范围。",
    }
