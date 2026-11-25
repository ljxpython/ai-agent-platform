from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal[
        "authorize",
        "authorize_search",
        "record_citations",
        "sql_sources",
        "sql_schema",
        "sql_query",
        "diagnostics",
        "logs",
        "documents",
        "source",
        "thread_runs",
        "thread_activity",
    ]
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=50)
    database_id: str = Field(default="", max_length=100)
    table_names: list[str] = Field(default_factory=list, max_length=20)
    table_offset: int = Field(default=0, ge=0, le=1000000)
    log_start: str = Field(default="", max_length=64)
    log_end: str = Field(default="", max_length=64)
    log_service: str = Field(default="", max_length=100)
    query: str = Field(default="", max_length=12000)
    target_thread_id: UUID | None = None
    target_run_id: UUID | None = None
    document_id: str = Field(default="", max_length=200)
    line: int = Field(default=1, ge=1, le=100000)


class InternalReadRequest(ReadRequest):
    project_id: UUID
    actor_id: UUID
    thread_id: UUID
    run_id: UUID
    tool_call_id: str = Field(min_length=1, max_length=256)


class AssistantDatabase(BaseModel):
    """One administrator-provisioned read-only dataset; never the application login."""

    model_config = ConfigDict(extra="forbid")
    dsn: str = Field(repr=False)
    project_id: UUID
    schema_name: str = Field(pattern=r"^[a-z_][a-z0-9_]{0,62}$")
    tables: list[str] = Field(default_factory=list)
    user_ids: list[UUID] = Field(default_factory=list)
    project_roles: list[
        Literal["project_admin", "project_editor", "project_executor"]
    ] = Field(default_factory=list)
    revision: str = Field(min_length=1, max_length=100)
