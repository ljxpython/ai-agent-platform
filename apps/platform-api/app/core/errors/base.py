from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.core.errors.payload import build_error_payload


class PlatformApiError(Exception):
    def __init__(
        self,
        *,
        code: str,
        status_code: int,
        message: str,
        details: Sequence[Mapping[str, Any]] | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.message = message
        self.details = list(details or [])
        self.extra = dict(extra or {})

    def to_payload(self, *, request_id: str | None) -> dict[str, Any]:
        return build_error_payload(
            code=self.code,
            message=self.message,
            request_id=request_id,
            details=self.details,
            extra=self.extra,
        )


class BadRequestError(PlatformApiError):
    def __init__(self, message: str = "Bad request", *, code: str = "bad_request") -> None:
        super().__init__(code=code, status_code=400, message=message)


class ValidationError(PlatformApiError):
    def __init__(
        self,
        message: str = "Validation failed",
        *,
        details: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        super().__init__(
            code="validation_failed",
            status_code=422,
            message=message,
            details=details,
        )


class NotAuthenticatedError(PlatformApiError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(
            code="not_authenticated",
            status_code=401,
            message=message,
        )


class ForbiddenError(PlatformApiError):
    def __init__(self, message: str = "Permission denied", *, code: str = "forbidden") -> None:
        super().__init__(code=code, status_code=403, message=message)


class NotFoundError(PlatformApiError):
    def __init__(self, message: str = "Resource not found", *, code: str = "not_found") -> None:
        super().__init__(code=code, status_code=404, message=message)


class ConflictError(PlatformApiError):
    def __init__(self, message: str = "Resource conflict", *, code: str = "conflict") -> None:
        super().__init__(code=code, status_code=409, message=message)


class ServiceUnavailableError(PlatformApiError):
    def __init__(
        self,
        message: str = "Service unavailable",
        *,
        code: str = "service_unavailable",
    ) -> None:
        super().__init__(code=code, status_code=503, message=message)


class UpstreamServiceError(PlatformApiError):
    def __init__(
        self,
        message: str = "Upstream service error",
        *,
        upstream: str,
        status_code: int = 502,
        code: str = "upstream_service_error",
    ) -> None:
        super().__init__(
            code=code,
            status_code=status_code,
            message=message,
            extra={"upstream": upstream},
        )
