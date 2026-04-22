from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.errors import NotFoundError


@dataclass(frozen=True, slots=True)
class OperationArtifact:
    path: Path
    filename: str
    media_type: str
    size_bytes: int
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class OperationArtifactCleanupSummary:
    storage_backend: str
    retention_hours: int
    scanned_count: int
    removed_count: int
    missing_count: int
    bytes_reclaimed: int


class LocalOperationArtifactStore:
    _METADATA_FILENAME = ".artifact.json"

    def __init__(
        self,
        root_dir: str,
        *,
        storage_backend: str = "local",
        retention_hours: int = 72,
    ) -> None:
        self._root_dir = Path(root_dir).expanduser()
        self._storage_backend = storage_backend
        self._retention_hours = retention_hours

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
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(hours=self._retention_hours)
        artifact_payload = {
            "relative_path": str(path.relative_to(self._root_dir)),
            "filename": safe_filename,
            "media_type": media_type or "application/octet-stream",
            "size_bytes": len(payload),
            "storage_backend": self._storage_backend,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "retention_hours": self._retention_hours,
        }
        self._metadata_path(operation_dir).write_text(
            json.dumps(artifact_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return artifact_payload

    def resolve(self, artifact_payload: dict[str, object]) -> OperationArtifact:
        relative_path = str(artifact_payload.get("relative_path") or "").strip()
        filename = str(artifact_payload.get("filename") or "").strip()
        media_type = str(artifact_payload.get("media_type") or "application/octet-stream").strip()
        size_bytes = int(artifact_payload.get("size_bytes") or 0)
        expires_at = self._parse_datetime(artifact_payload.get("expires_at"))
        if not relative_path or not filename:
            raise NotFoundError(message="Operation artifact not found", code="operation_artifact_not_found")

        root_path = self._root_dir.resolve()
        path = (root_path / relative_path).resolve()
        if root_path not in path.parents and path != root_path:
            raise NotFoundError(message="Operation artifact not found", code="operation_artifact_not_found")
        if expires_at is not None and expires_at <= datetime.now(timezone.utc):
            raise NotFoundError(message="Operation artifact expired", code="operation_artifact_expired")
        if not path.exists() or not path.is_file():
            raise NotFoundError(message="Operation artifact not found", code="operation_artifact_not_found")

        return OperationArtifact(
            path=path,
            filename=filename,
            media_type=media_type or "application/octet-stream",
            size_bytes=size_bytes if size_bytes > 0 else path.stat().st_size,
            expires_at=expires_at,
        )

    def cleanup_expired(self, *, limit: int, now: datetime | None = None) -> OperationArtifactCleanupSummary:
        self._root_dir.mkdir(parents=True, exist_ok=True)
        current_time = now or datetime.now(timezone.utc)
        scanned_count = 0
        removed_count = 0
        missing_count = 0
        bytes_reclaimed = 0

        metadata_paths = sorted(self._root_dir.glob(f"*/{self._METADATA_FILENAME}"))
        for metadata_path in metadata_paths:
            if removed_count >= limit:
                break
            scanned_count += 1
            payload = self._load_metadata(metadata_path)
            expires_at = self._parse_datetime(payload.get("expires_at"))
            if expires_at is None or expires_at > current_time:
                continue

            relative_path = str(payload.get("relative_path") or "").strip()
            artifact_path = (self._root_dir / relative_path).resolve() if relative_path else None
            size_bytes = 0
            if artifact_path is not None and artifact_path.exists() and artifact_path.is_file():
                size_bytes = artifact_path.stat().st_size
                artifact_path.unlink(missing_ok=True)
                bytes_reclaimed += size_bytes
            else:
                missing_count += 1

            metadata_path.unlink(missing_ok=True)
            self._cleanup_empty_dir(metadata_path.parent)
            removed_count += 1

        return OperationArtifactCleanupSummary(
            storage_backend=self._storage_backend,
            retention_hours=self._retention_hours,
            scanned_count=scanned_count,
            removed_count=removed_count,
            missing_count=missing_count,
            bytes_reclaimed=bytes_reclaimed,
        )

    def _metadata_path(self, operation_dir: Path) -> Path:
        return operation_dir / self._METADATA_FILENAME

    @staticmethod
    def _load_metadata(metadata_path: Path) -> dict[str, object]:
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _cleanup_empty_dir(operation_dir: Path) -> None:
        try:
            if operation_dir.exists() and operation_dir.is_dir() and not any(operation_dir.iterdir()):
                operation_dir.rmdir()
        except OSError:
            return

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
