from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ListTestcaseBatchesQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class ListTestcaseDocumentsQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    batch_id: str | None = None
    parse_status: str | None = None
    query: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class ListTestcaseCasesQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    batch_id: str | None = None
    status: str | None = None
    query: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class GetTestcaseBatchDetailQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_limit: int = Field(default=100, ge=1, le=500)
    document_offset: int = Field(default=0, ge=0)
    case_limit: int = Field(default=50, ge=1, le=500)
    case_offset: int = Field(default=0, ge=0)


class ExportTestcaseCasesQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    batch_id: str | None = None
    status: str | None = None
    query: str | None = None
    columns: tuple[str, ...] = ()


class ExportTestcaseDocumentsQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    batch_id: str | None = None
    parse_status: str | None = None
    query: str | None = None


class CreateTestcaseCaseCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    batch_id: str | None = Field(default=None, max_length=255)
    case_id: str | None = Field(default=None, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    status: str = Field(default="active", min_length=1, max_length=64)
    module_name: str | None = Field(default=None, max_length=255)
    priority: str | None = Field(default=None, max_length=32)
    source_document_ids: list[str] = Field(default_factory=list)
    content_json: dict[str, Any] = Field(default_factory=dict)


class UpdateTestcaseCaseCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    batch_id: str | None = Field(default=None, max_length=255)
    case_id: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(default=None, min_length=1, max_length=64)
    module_name: str | None = Field(default=None, max_length=255)
    priority: str | None = Field(default=None, max_length=32)
    source_document_ids: list[str] | None = None
    content_json: dict[str, Any] | None = None
