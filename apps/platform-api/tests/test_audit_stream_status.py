from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from platform_api.entrypoints.http.middleware.audit_log import (
    register_audit_log_middleware,
)
from platform_api.modules.audit.schemas import AuditResult


class AuditStreamStatusTest(unittest.TestCase):
    def test_audit_write_failure_does_not_change_response(self) -> None:
        app = FastAPI()
        engine = create_engine("sqlite+pysqlite:///:memory:")
        app.state.db_session_factory = sessionmaker(bind=engine)
        register_audit_log_middleware(app)

        @app.get("/ok")
        async def ok() -> dict[str, bool]:
            return {"ok": True}

        with patch(
            "platform_api.entrypoints.http.middleware.audit_log._write_audit_event",
            side_effect=RuntimeError("audit unavailable"),
        ):
            response = TestClient(app).get("/ok")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        engine.dispose()

    def test_stream_failure_keeps_sent_http_status(self) -> None:
        app = FastAPI()
        engine = create_engine("sqlite+pysqlite:///:memory:")
        app.state.db_session_factory = sessionmaker(bind=engine)
        register_audit_log_middleware(app)

        @app.get("/stream")
        async def stream() -> StreamingResponse:
            async def body():
                yield b"first"
                raise RuntimeError("upstream stream failed")

            return StreamingResponse(body(), status_code=200)

        captured = []
        with patch(
            "platform_api.entrypoints.http.middleware.audit_log._write_audit_event",
            side_effect=lambda **kwargs: captured.append(kwargs),
        ):
            with self.assertRaises(RuntimeError):
                TestClient(app).get("/stream")
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["status_code"], 200)
        self.assertIn(captured[0]["result"], (AuditResult.SUCCESS, AuditResult.FAILED))
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
