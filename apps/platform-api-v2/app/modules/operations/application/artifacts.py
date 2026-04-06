from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.errors import NotFoundError


@dataclass(frozen=True, slots=True)
class OperationArtifact:
    path: Path
    filename: str
    media_type: str
    size_bytes: int


class LocalOperationArtifactStore:
    def __init__(self, root_dir: str) -> None:
        self._root_dir = Path(root_dir).expanduser()

    def save_bytes(
        self,
        *,
        operation_id: str,
        filename: str,
        media_type: str,
        payload: bytes,
    ) -> dict[str, object]:
        safe_filename = Path(filename or "artifact.bin").name or "artifact.bin"
        operation_dir = self._root_dir / operation_id
        operation_dir.mkdir(parents=True, exist_ok=True)
        path = operation_dir / safe_filename
        path.write_bytes(payload)
        return {
            "relative_path": str(path.relative_to(self._root_dir)),
            "filename": safe_filename,
            "media_type": media_type or "application/octet-stream",
            "size_bytes": len(payload),
        }

    def resolve(self, artifact_payload: dict[str, object]) -> OperationArtifact:
        relative_path = str(artifact_payload.get("relative_path") or "").strip()
        filename = str(artifact_payload.get("filename") or "").strip()
        media_type = str(artifact_payload.get("media_type") or "application/octet-stream").strip()
        size_bytes = int(artifact_payload.get("size_bytes") or 0)
        if not relative_path or not filename:
            raise NotFoundError(message="Operation artifact not found", code="operation_artifact_not_found")

        root_path = self._root_dir.resolve()
        path = (root_path / relative_path).resolve()
        if root_path not in path.parents and path != root_path:
            raise NotFoundError(message="Operation artifact not found", code="operation_artifact_not_found")
        if not path.exists() or not path.is_file():
            raise NotFoundError(message="Operation artifact not found", code="operation_artifact_not_found")

        return OperationArtifact(
            path=path,
            filename=filename,
            media_type=media_type or "application/octet-stream",
            size_bytes=size_bytes if size_bytes > 0 else path.stat().st_size,
        )
