"""Public workspace browsing response models."""

from typing import Literal

from pydantic import BaseModel

PreviewKind = Literal["text", "markdown", "image", "html-sandbox", "download"]


class WorkspaceEntry(BaseModel):
    path: str
    name: str
    type: Literal["file", "directory"]
    size_bytes: int | None
    mtime: str
    mime_type: str | None
    preview_kind: PreviewKind | None
    is_artifact: bool


class WorkspacePage(BaseModel):
    items: list[WorkspaceEntry]
    next_cursor: str | None = None


class ArtifactRef(BaseModel):
    version: Literal[1]
    artifact_id: str
    path: str
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    kind: str
    preview_kind: PreviewKind


class ArtifactPage(BaseModel):
    items: list[ArtifactRef]
    next_cursor: str | None = None
