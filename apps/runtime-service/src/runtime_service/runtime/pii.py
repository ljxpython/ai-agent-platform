"""Deterministic, request-bound PII redaction for Runtime model calls.

The module deliberately has no storage or network side effects.  It rewrites a
request copy immediately before a provider call and keeps the signed execution
scope outside client-controlled configuration.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool
from langgraph.errors import GraphBubbleUp

from runtime_service.runtime.auth import VerifiedDelegation
from runtime_service.runtime.errors import RuntimePrivacyError

PII_REDACTION_ERROR = "runtime.privacy.redaction_failed"
PII_DETECTORS = ("email", "api_key", "national_id", "credit_card", "phone")
_MIN_SECRET_LENGTH = 16
_TOKEN_ALPHABET = "abcdefghijklmnopqrstuvwxyz"


@dataclass(frozen=True, slots=True, repr=False)
class PiiRedactionConfig:
    """Immutable deployment policy; ``token_secret`` is intentionally absent from repr."""

    enabled: bool = False
    token_secret: str | None = None
    detectors: tuple[str, ...] = PII_DETECTORS
    scope: tuple[str, str, str] | None = None

    def __post_init__(self) -> None:
        if (
            type(self.enabled) is not bool
            or not isinstance(self.detectors, tuple)
            or not self.detectors
            or any(not isinstance(name, str) for name in self.detectors)
            or len(set(self.detectors)) != len(self.detectors)
            or any(name not in PII_DETECTORS for name in self.detectors)
            or (
                self.token_secret is not None and not isinstance(self.token_secret, str)
            )
            or (
                self.enabled
                and (
                    not self.token_secret or len(self.token_secret) < _MIN_SECRET_LENGTH
                )
            )
            or (
                self.scope is not None
                and (
                    not isinstance(self.scope, tuple)
                    or len(self.scope) != 3
                    or not all(
                        isinstance(value, str) and value and value == value.strip()
                        for value in self.scope
                    )
                )
            )
        ):
            raise _privacy_failure()

    def __repr__(self) -> str:
        return (
            "PiiRedactionConfig("
            f"enabled={self.enabled!r}, detectors={self.detectors!r}, "
            f"scope={self.scope!r})"
        )

    def scoped(
        self, tenant_id: str, project_id: str, thread_id: str
    ) -> PiiRedactionConfig:
        values = (tenant_id, project_id, thread_id)
        if not all(
            isinstance(value, str) and value and value == value.strip()
            for value in values
        ):
            raise _privacy_failure()
        return replace(self, scope=values)


def _privacy_failure(field: str | None = None) -> RuntimePrivacyError:
    return RuntimePrivacyError(PII_REDACTION_ERROR)


def _parse_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise _privacy_failure("enabled")


def load_pii_redaction_config(
    *,
    scope: tuple[str, str, str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> PiiRedactionConfig:
    """Load the deployment policy without exposing its secret in errors or repr."""

    env = os.environ if environ is None else environ
    enabled = _parse_bool(env.get("RUNTIME_PII_REDACTION_ENABLED"), default=False)
    raw_detectors = env.get("RUNTIME_PII_DETECTORS", ",".join(PII_DETECTORS))
    detectors = tuple(item.strip().lower() for item in raw_detectors.split(","))
    if (
        not detectors
        or any(not item or item not in PII_DETECTORS for item in detectors)
        or len(set(detectors)) != len(detectors)
    ):
        raise _privacy_failure("detectors")
    secret = env.get("RUNTIME_PII_TOKEN_SECRET", "").strip() or None
    if enabled and (secret is None or len(secret) < _MIN_SECRET_LENGTH):
        raise _privacy_failure("token_secret")
    return PiiRedactionConfig(
        enabled=enabled,
        token_secret=secret,
        detectors=tuple(name for name in PII_DETECTORS if name in detectors),
        scope=scope,
    )


def pii_config_for_facts(
    facts: VerifiedDelegation | None, thread_id: str | None
) -> PiiRedactionConfig:
    config = load_pii_redaction_config()
    if not config.enabled:
        return config
    if (
        facts is None
        or not thread_id
        or (facts.scope.thread_id is not None and facts.scope.thread_id != thread_id)
    ):
        raise _privacy_failure()
    return config.scoped(
        facts.principal.tenant_id, facts.principal.project_id, thread_id
    )


def _luhn_valid(value: str) -> bool:
    digits = [int(char) for char in value if char in "0123456789"]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for offset, digit in enumerate(reversed(digits)):
        if offset % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


_CN_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_CN_ID_CHECK_DIGITS = "10X98765432"


def _cn_resident_id_valid(value: str) -> bool:
    body = value[:17]
    if not body.isdigit():
        return False
    try:
        parsed = date(int(body[6:10]), int(body[10:12]), int(body[12:14]))
    except ValueError:
        return False
    if not 1900 <= parsed.year <= 2100:
        return False
    total = sum(
        int(digit) * weight for digit, weight in zip(body, _CN_ID_WEIGHTS, strict=True)
    )
    return _CN_ID_CHECK_DIGITS[total % 11] == value[17].upper()


def _phone_valid(value: str) -> bool:
    return 8 <= len(re.sub(r"[^0-9]", "", value)) <= 15


@dataclass(frozen=True, slots=True)
class _Detector:
    name: str
    pattern: re.Pattern[str]
    validator: Callable[[str], bool] | None = None


_DETECTORS: tuple[_Detector, ...] = (
    _Detector(
        "email",
        re.compile(
            r"(?<![A-Za-z0-9._%+\-])"
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}"
            r"@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){0,10}\.[A-Za-z]{2,63}"
            r"(?![A-Za-z0-9_%+\-])"
        ),
    ),
    _Detector(
        "api_key",
        re.compile(
            r"(?<![A-Za-z0-9_])(?:"
            r"(?:Bearer|Basic)[ \t]+[A-Za-z0-9._~+/=-]{16,}"
            r"|sk-[A-Za-z0-9_-]{20,}"
            r"|AKIA[0-9A-Z]{16}"
            r"|gh[pousr]_[A-Za-z0-9]{30,}"
            r"|github_pat_[A-Za-z0-9_]{20,}"
            r"|xox[baprs]-[A-Za-z0-9-]{10,}"
            r"|AIza[0-9A-Za-z_-]{35}"
            r")(?![A-Za-z0-9_])"
        ),
    ),
    _Detector(
        "national_id",
        re.compile(r"(?<![0-9Xx])[0-9]{17}[0-9Xx](?![0-9Xx])"),
        _cn_resident_id_valid,
    ),
    _Detector(
        "credit_card",
        re.compile(r"(?<![+0-9])(?:[0-9][ -]?){12,18}[0-9](?![0-9])"),
        _luhn_valid,
    ),
    _Detector(
        "phone",
        re.compile(
            r"(?<![0-9])1[3-9][0-9]{9}(?![0-9])"
            r"|(?<![0-9])\+[0-9]{1,3}(?:[ \-]?[0-9]{1,4}){2,6}(?![0-9])"
            r"|(?<![0-9])\([0-9]{3}\)[ \-]?[0-9]{3}[\-.]?[0-9]{4}(?![0-9])"
        ),
        _phone_valid,
    ),
)
_KEY_LABEL = re.compile(
    r"(?i)(?<![A-Za-z0-9_])(?:api[_-]?key|access[_-]?token|client[_-]?secret)"
    r"[\"']?[ \t]*[:=][ \t]*[\"']?(?P<value>[A-Za-z0-9._~+/=-]{16,})"
)
_PLACEHOLDER = re.compile(
    r"\[(?:EMAIL|API_KEY|NATIONAL_ID|CREDIT_CARD|PHONE)_[a-z]{27}\]"
)


def _active_detectors(config: PiiRedactionConfig) -> tuple[_Detector, ...]:
    return tuple(
        detector for detector in _DETECTORS if detector.name in config.detectors
    )


def _placeholder_token(category: str, value: str, config: PiiRedactionConfig) -> str:
    if not config.token_secret or config.scope is None:
        raise _privacy_failure("scope")
    payload = json.dumps(
        {
            "algorithm": "runtime-pii/v1",
            "category": category,
            "scope": config.scope,
            "value": value,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hmac.new(
        config.token_secret.encode("utf-8"), payload, hashlib.sha256
    ).digest()
    number = int.from_bytes(digest[:16], "big")
    letters: list[str] = []
    for _ in range(27):
        number, remainder = divmod(number, 26)
        letters.append(_TOKEN_ALPHABET[remainder])
    return f"[{category.upper()}_{''.join(letters)}]"


def _redact_string(text: str, config: PiiRedactionConfig) -> str:
    for detector in _active_detectors(config):

        def replace(match: re.Match[str], detector: _Detector = detector) -> str:
            value = match.group(0)
            if detector.validator is not None and not detector.validator(value):
                return value
            return _placeholder_token(detector.name, value, config)

        text = detector.pattern.sub(replace, text)
        if detector.name == "api_key":

            def labeled(match: re.Match[str]) -> str:
                start = match.start("value") - match.start()
                return match.group(0)[:start] + _placeholder_token(
                    "api_key", match.group("value"), config
                )

            text = _KEY_LABEL.sub(labeled, text)
    return text


def _redact_media(value: object, config: PiiRedactionConfig) -> object:
    if isinstance(value, list):
        return [_redact_media(item, config) for item in value]
    if not isinstance(value, dict):
        return deepcopy(value)
    if any(_redact_string(key, config) != key for key in value):
        raise _privacy_failure()
    copied = deepcopy(value)
    for key, item in value.items():
        if key in {"base64", "file_data"} or (
            key == "data" and value.get("type") != "text"
        ):
            continue
        if key in {"url", "image_url"} and isinstance(item, str):
            if not item.startswith("data:") and _redact_string(item, config) != item:
                raise _privacy_failure()
        elif key == "content" and isinstance(item, list):
            copied[key] = _redact_content(item, config)
        elif isinstance(item, str):
            copied[key] = _redact_string(item, config)
        elif isinstance(item, (dict, list)):
            copied[key] = _redact_media(item, config)
    return copied


def _redact_content(content: object, config: PiiRedactionConfig) -> object:
    if isinstance(content, str):
        return _redact_string(content, config)
    if not isinstance(content, list):
        raise _privacy_failure()
    result: list[Any] = []
    text_slots: list[tuple[int, bool, str]] = []

    def flush() -> None:
        if not text_slots:
            return
        # Detect ordinary text split across adjacent provider content blocks.
        joined = "".join(slot[2] for slot in text_slots)
        safe = _redact_string(joined, config)
        if safe != joined:
            first, mapping, _ = text_slots[0]
            if mapping:
                result[first]["text"] = safe
            else:
                result[first] = safe
            for index, mapping, _ in text_slots[1:]:
                if mapping:
                    result[index]["text"] = ""
                else:
                    result[index] = ""
        text_slots.clear()

    for block in content:
        if isinstance(block, dict) and any(
            _redact_string(key, config) != key for key in block
        ):
            raise _privacy_failure()
        if isinstance(block, str):
            text_slots.append((len(result), False, block))
            result.append(block)
        elif (
            isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ):
            text_slots.append((len(result), True, block["text"]))
            result.append(
                {
                    key: deepcopy(value)
                    if key in {"type", "text"}
                    else _redact_value(value, config)
                    for key, value in block.items()
                }
            )
        else:
            flush()
            if not isinstance(block, dict):
                raise _privacy_failure()
            kind = block.get("type")
            if kind in {
                "image",
                "image_url",
                "file",
                "audio",
                "input_audio",
                "video",
                "document",
            }:
                copied = _redact_media(block, config)
            elif kind in {"thinking", "redacted_thinking", "reasoning"}:
                if kind == "redacted_thinking":
                    raise _privacy_failure()
                copied = _redact_value(block, config)
                if copied != block and (
                    "signature" in block or kind == "redacted_thinking"
                ):
                    raise _privacy_failure()
            elif kind in {"tool_use", "tool_call", "function_call", "tool_result"}:
                copied = _tool_call(block, config, raw=kind == "function_call")
                for key in ("input", "args", "content", "output"):
                    if key in copied:
                        copied[key] = (
                            _redact_content(copied[key], config)
                            if key == "content" and isinstance(copied[key], list)
                            else _redact_value(copied[key], config)
                        )
            elif kind in {"refusal", "output_text", "input_text"}:
                copied = _redact_value(block, config)
            else:
                raise _privacy_failure()
            result.append(copied)
    flush()
    return result


def _redact_value(value: object, config: PiiRedactionConfig) -> object:
    """Only project JSON values; dictionary keys and schema identifiers stay unchanged."""

    if isinstance(value, str):
        return _redact_string(value, config)
    if isinstance(value, list):
        return [_redact_value(item, config) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item, config) for item in value)
    if isinstance(value, Mapping):
        if value.get("encrypted_content"):
            raise _privacy_failure()
        if any(
            isinstance(key, str) and _redact_string(key, config) != key for key in value
        ):
            raise _privacy_failure()
        result = {
            item_key: (
                _placeholder_token("api_key", item, config)
                if "api_key" in config.detectors
                and str(item_key).lower()
                in {"api_key", "apikey", "api-key", "access_token", "client_secret"}
                and isinstance(item, str)
                and len(item) >= 16
                and not _PLACEHOLDER.fullmatch(item)
                else _redact_value(item, config)
            )
            for item_key, item in deepcopy(dict(value)).items()
        }
        if value.get("signature") and result != value:
            raise _privacy_failure()
        return result
    if value is None or type(value) in {bool, int, float}:
        return value
    raise _privacy_failure()


def _tool_call(call: dict, config: PiiRedactionConfig, *, raw: bool = False) -> dict:
    result = deepcopy(call)
    for field in ("id", "name"):
        if (
            isinstance(call.get(field), str)
            and _redact_string(call[field], config) != call[field]
        ):
            raise _privacy_failure()
    if raw:
        function = result.get("function", result)
        if (
            isinstance(function.get("name"), str)
            and _redact_string(function["name"], config) != function["name"]
        ):
            raise _privacy_failure()
        if "arguments" in function:
            arguments = json.loads(function["arguments"])
            function["arguments"] = json.dumps(
                _redact_value(arguments, config), ensure_ascii=False
            )
    elif "args" in result:
        result["args"] = _redact_value(result["args"], config)
    return result


def _redact_message(message: BaseMessage, config: PiiRedactionConfig) -> BaseMessage:
    if not isinstance(message, BaseMessage):
        raise _privacy_failure()
    for name in (
        message.name,
        message.additional_kwargs.get("name"),
        getattr(message, "role", None),
        getattr(message, "tool_call_id", None),
    ):
        if isinstance(name, str) and _redact_string(name, config) != name:
            raise _privacy_failure()
    updates: dict[str, object] = {"content": _redact_content(message.content, config)}
    kwargs = deepcopy(message.additional_kwargs)
    for key in ("reasoning_content", "reasoning", "reasoning_details"):
        if key in kwargs:
            projected = _redact_value(kwargs[key], config)
            if projected != kwargs[key] and kwargs.get("signature"):
                raise _privacy_failure()
            kwargs[key] = projected
    if "audio" in kwargs:
        kwargs["audio"] = _redact_media(kwargs["audio"], config)
    if isinstance(message, AIMessage):
        updates["tool_calls"] = [
            _tool_call(call, config) for call in message.tool_calls
        ]
        updates["invalid_tool_calls"] = [
            _tool_call(call, config) for call in message.invalid_tool_calls
        ]
        if "tool_calls" in kwargs:
            kwargs["tool_calls"] = [
                _tool_call(call, config, raw=True) for call in kwargs["tool_calls"]
            ]
        if "function_call" in kwargs:
            kwargs["function_call"] = _tool_call(
                kwargs["function_call"], config, raw=True
            )
    updates["additional_kwargs"] = kwargs
    return message.model_copy(deep=True, update=updates)


def _scope_required(config: PiiRedactionConfig) -> None:
    if config.enabled and (
        not config.token_secret or config.scope is None or not all(config.scope)
    ):
        raise _privacy_failure("scope")


def redact_text(text: str | None, config: PiiRedactionConfig | None) -> str | None:
    """Redact one text field; disabled policies are an exact pass-through."""

    config = config if config is not None else load_pii_redaction_config()
    if not config.enabled or not isinstance(text, str) or not text:
        return text
    _scope_required(config)
    try:
        return _redact_string(text, config)
    except GraphBubbleUp:
        raise
    except Exception:
        pass
    raise _privacy_failure()


def contains_pii(text: str | None, config: PiiRedactionConfig | None) -> bool:
    return redact_text(text, config) != text


def redact_messages(
    messages: Sequence[BaseMessage], config: PiiRedactionConfig | None
) -> list[BaseMessage]:
    config = config if config is not None else load_pii_redaction_config()
    if not config.enabled:
        return list(messages)
    _scope_required(config)
    try:
        return [_redact_message(message, config) for message in messages]
    except GraphBubbleUp:
        raise
    except Exception:
        pass
    raise _privacy_failure()


def _redact_schema(schema: object, config: PiiRedactionConfig) -> object:
    if isinstance(schema, list):
        return [_redact_schema(item, config) for item in schema]
    if not isinstance(schema, dict):
        if isinstance(schema, str) and _redact_string(schema, config) != schema:
            raise _privacy_failure()
        return deepcopy(schema)
    if any(_redact_string(key, config) != key for key in schema):
        raise _privacy_failure()
    for field in ("properties", "$defs", "definitions"):
        definitions = schema.get(field)
        if isinstance(definitions, dict) and any(
            _redact_string(name, config) != name for name in definitions
        ):
            raise _privacy_failure()
    return {
        key: _redact_value(value, config)
        if key in {"description", "examples", "example", "default", "title"}
        else (
            {name: _redact_schema(item, config) for name, item in value.items()}
            if key in {"properties", "$defs", "definitions"} and isinstance(value, dict)
            else _redact_schema(value, config)
        )
        for key, value in schema.items()
    }


def _redact_tool(tool: BaseTool | dict, config: PiiRedactionConfig) -> BaseTool | dict:
    if isinstance(tool, dict):
        return _redact_schema(tool, config)
    if not isinstance(tool, BaseTool):
        raise _privacy_failure()
    if _redact_string(tool.name, config) != tool.name:
        raise _privacy_failure()
    schema = tool.args_schema
    if schema is not None and not isinstance(schema, dict):
        schema = tool.tool_call_schema
        if not isinstance(schema, dict):
            schema = schema.model_json_schema()
    updates = {"description": _redact_string(tool.description, config)}
    safe_schema = _redact_schema(schema, config)
    if safe_schema != schema:
        updates["args_schema"] = safe_schema
    return tool.model_copy(update=updates)


def redact_model_request(
    request: ModelRequest, config: PiiRedactionConfig | None
) -> ModelRequest:
    """Return a request copy safe for a provider; never mutate state or original messages."""

    config = config if config is not None else load_pii_redaction_config()
    if not config.enabled:
        return request
    _scope_required(config)
    try:
        return request.override(
            messages=redact_messages(request.messages, config),
            system_message=_redact_message(request.system_message, config)
            if request.system_message is not None
            else None,
            tools=[_redact_tool(tool, config) for tool in request.tools],
        )
    except GraphBubbleUp:
        raise
    except Exception:
        pass
    raise _privacy_failure()


__all__ = [
    "PII_DETECTORS",
    "PII_REDACTION_ERROR",
    "PiiRedactionConfig",
    "contains_pii",
    "load_pii_redaction_config",
    "pii_config_for_facts",
    "redact_messages",
    "redact_model_request",
    "redact_text",
]
