from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TraceLogEntry(BaseModel):
    timestamp: str = Field(description="ISO 8601 formatted timestamp")
    nanos: str = Field(description="Unix timestamp in nanoseconds")
    service: str = Field(default="unknown", description="Source microservice name")
    level: str = Field(default="info", description="Log level")
    event: str = Field(default="", description="Structured event name if present")
    summary: str = Field(default="", description="Human-readable log summary")
    span_id: str = Field(default="", description="Span ID if available")
    duration_ms: float | None = Field(
        default=None, description="Duration in milliseconds if available"
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Parsed structured JSON payload"
    )
    raw: str = Field(description="Raw log text")


class TraceLogsResponse(BaseModel):
    trace_id: str
    total: int = 0
    duration_ms: float | None = Field(
        default=None, description="Total trace duration in milliseconds"
    )
    services: list[str] = Field(default_factory=list)
    logs: list[TraceLogEntry] = Field(default_factory=list)
    error: str | None = None
