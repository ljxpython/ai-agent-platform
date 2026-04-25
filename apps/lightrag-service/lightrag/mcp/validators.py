from __future__ import annotations

from uuid import UUID

from lightrag.base import DocStatus

VALID_QUERY_MODES = {"local", "global", "hybrid", "naive", "mix", "bypass"}
STATUS_ALIASES = {
    "ready": DocStatus.PROCESSED,
    "processed": DocStatus.PROCESSED,
    "preprocessed": DocStatus.PREPROCESSED,
    "processing": DocStatus.PROCESSING,
    "pending": DocStatus.PENDING,
    "failed": DocStatus.FAILED,
}


def validate_project_id(project_id: str) -> str:
    candidate = str(project_id or "").strip()
    if not candidate:
        raise ValueError("project_id_required")
    try:
        return str(UUID(candidate))
    except (TypeError, ValueError) as exc:
        raise ValueError("project_id_must_be_uuid") from exc


def validate_query_text(query: str) -> str:
    candidate = str(query or "").strip()
    if len(candidate) < 1:
        raise ValueError("query_required")
    return candidate


def validate_query_mode(mode: str | None, default: str) -> str:
    candidate = (mode or default or "mix").strip().lower()
    if candidate not in VALID_QUERY_MODES:
        raise ValueError(f"unsupported_query_mode:{candidate}")
    return candidate


def validate_positive_int(value: int | None, *, field_name: str, default: int) -> int:
    candidate = default if value is None else int(value)
    if candidate < 1:
        raise ValueError(f"{field_name}_must_be_positive")
    return candidate


def validate_document_id(document_id: str) -> str:
    candidate = str(document_id or "").strip()
    if not candidate:
        raise ValueError("document_id_required")
    return candidate


def normalize_status_filter(status: str | None) -> DocStatus | None:
    if status is None:
        return None
    candidate = str(status).strip().lower()
    if not candidate:
        return None
    resolved = STATUS_ALIASES.get(candidate)
    if resolved is None:
        raise ValueError(f"unsupported_status_filter:{candidate}")
    return resolved


def normalize_overall_status(status: str) -> str:
    return "ready" if status == DocStatus.PROCESSED.value else status
