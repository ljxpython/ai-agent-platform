from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import FastAPI
from sqlalchemy import select

from platform_api.bootstrap.lifespan import lifespan
from platform_api.config import Settings
from platform_api.core.db import build_engine, build_session_factory, create_core_tables
from platform_api.entrypoints.worker.main import main as run_worker
from platform_api.modules.identity.infra.sqlalchemy.models import UserRecord


class ResourceLifecycleTest(unittest.IsolatedAsyncioTestCase):
    async def test_startup_failure_disposes_engine_and_clears_request_resources(self) -> None:
        app = FastAPI()
        app.state.settings = Settings(
            _env_file=None,
            platform_db_enabled=True,
            database_url="sqlite://",
            platform_db_auto_create=True,
            bootstrap_admin_enabled=False,
        )
        engine = Mock()
        with (
            patch("platform_api.bootstrap.lifespan.build_engine", return_value=engine),
            patch("platform_api.bootstrap.lifespan.build_session_factory"),
            patch("platform_api.bootstrap.lifespan.create_core_tables", side_effect=RuntimeError("init failed")),
            self.assertRaisesRegex(RuntimeError, "init failed"),
        ):
            async with lifespan(app):
                self.fail("startup must fail before serving requests")
        engine.dispose.assert_called_once_with()
        self.assertIsNone(app.state.db_engine)
        self.assertIsNone(app.state.db_session_factory)

    async def test_database_initialization_runs_off_loop_and_bootstrap_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_url = f"sqlite:///{Path(directory) / 'platform.db'}"
            app = FastAPI()
            app.state.settings = Settings(
                _env_file=None,
                platform_db_enabled=True,
                database_url=database_url,
                platform_db_auto_create=True,
                bootstrap_admin_enabled=True,
                bootstrap_admin_username="lifecycle-admin",
                bootstrap_admin_password="test-password-only",
            )
            loop_thread = threading.get_ident()
            initialization_threads: list[int] = []

            def initialize(engine) -> None:
                initialization_threads.append(threading.get_ident())
                create_core_tables(engine)

            with patch("platform_api.bootstrap.lifespan.create_core_tables", side_effect=initialize):
                for _ in range(2):
                    async with lifespan(app):
                        self.assertIsNotNone(app.state.db_session_factory)
                    self.assertIsNone(app.state.db_session_factory)

            self.assertEqual(len(initialization_threads), 2)
            self.assertNotIn(loop_thread, initialization_threads)
            engine = build_engine(database_url)
            try:
                with build_session_factory(engine)() as session:
                    users = session.scalars(select(UserRecord)).all()
                    self.assertEqual(len(users), 1)
                    self.assertEqual(users[0].username, "lifecycle-admin")
                    self.assertNotEqual(users[0].password_hash, "test-password-only")
            finally:
                engine.dispose()

    async def test_worker_construction_failure_disposes_engine(self) -> None:
        settings = Settings(
            _env_file=None,
            platform_db_enabled=True,
            database_url="sqlite://",
            platform_db_auto_create=False,
        )
        engine = Mock()
        with (
            patch("platform_api.entrypoints.worker.main.load_dotenv"),
            patch("platform_api.entrypoints.worker.main.load_settings", return_value=settings),
            patch("platform_api.entrypoints.worker.main.build_engine", return_value=engine),
            patch("platform_api.entrypoints.worker.main.build_session_factory"),
            patch("platform_api.entrypoints.worker.main.build_operation_worker", side_effect=RuntimeError("worker failed")),
            self.assertRaisesRegex(RuntimeError, "worker failed"),
        ):
            await run_worker()
        engine.dispose.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
