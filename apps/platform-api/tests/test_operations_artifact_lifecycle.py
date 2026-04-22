from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from app.core.context.models import ActorContext
from app.core.db import build_engine, build_session_factory, create_core_tables
from app.modules.operations.application.artifacts import LocalOperationArtifactStore
from app.modules.operations.application.service import OperationsService


class OperationsArtifactLifecycleTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "operations-artifact-lifecycle.db"
        self._engine = build_engine(f"sqlite:///{database_path}")
        self._session_factory = build_session_factory(self._engine)
        create_core_tables(self._engine)
        self.artifact_root = Path(self._tmpdir.name) / "artifacts"
        self.artifact_store = LocalOperationArtifactStore(
            str(self.artifact_root),
            storage_backend="local",
            retention_hours=24,
        )
        self.service = OperationsService(
            session_factory=self._session_factory,
            artifact_store=self.artifact_store,
        )
        self.actor = ActorContext(
            user_id=str(uuid4()),
            platform_roles=("platform_super_admin",),
            project_roles={},
        )

    def tearDown(self) -> None:
        self._engine.dispose()
        self._tmpdir.cleanup()

    def test_local_artifact_store_refuses_expired_artifact(self) -> None:
        artifact = self.artifact_store.save_bytes(
            operation_id="op-expired",
            filename="expired.txt",
            media_type="text/plain",
            payload=b"expired",
        )
        artifact["expires_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        with self.assertRaisesRegex(Exception, "Operation artifact expired"):
            self.artifact_store.resolve(artifact)

    async def test_cleanup_expired_artifacts_removes_files_and_reclaims_bytes(self) -> None:
        self.artifact_store.save_bytes(
            operation_id="op-cleanup",
            filename="cleanup.txt",
            media_type="text/plain",
            payload=b"cleanup-target",
        )
        metadata_path = self.artifact_root / "op-cleanup" / ".artifact.json"
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        payload["expires_at"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        metadata_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        result = await self.service.cleanup_expired_artifacts(actor=self.actor, limit=100)

        self.assertEqual(result.storage_backend, "local")
        self.assertEqual(result.retention_hours, 24)
        self.assertEqual(result.scanned_count, 1)
        self.assertEqual(result.removed_count, 1)
        self.assertEqual(result.missing_count, 0)
        self.assertEqual(result.bytes_reclaimed, len(b"cleanup-target"))
        self.assertFalse((self.artifact_root / "op-cleanup").exists())


if __name__ == "__main__":
    unittest.main()
