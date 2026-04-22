from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import PlatformApiError, register_exception_handlers


class _ValidationPayload(BaseModel):
    name: str
    count: int


class CoreErrorHandlingTest(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()

        @app.middleware("http")
        async def inject_request_id(request, call_next):  # type: ignore[no-untyped-def]
            request.state.request_id = "req-phase-b"
            return await call_next(request)

        register_exception_handlers(app)

        @app.get("/platform-error")
        async def platform_error() -> None:
            raise PlatformApiError(
                code="phase_b_error",
                status_code=418,
                message="Phase B failure",
                details=[{"field": "name"}],
                extra={"scope": "test"},
            )

        @app.post("/validate")
        async def validate(payload: _ValidationPayload) -> dict[str, object]:
            return payload.model_dump()

        self.client = TestClient(app)

    def test_platform_api_error_uses_unified_envelope(self) -> None:
        response = self.client.get("/platform-error")

        self.assertEqual(response.status_code, 418, response.text)
        payload = response.json()
        self.assertEqual(payload["request_id"], "req-phase-b")
        self.assertEqual(payload["error"]["code"], "phase_b_error")
        self.assertEqual(payload["error"]["message"], "Phase B failure")
        self.assertEqual(payload["error"]["details"], [{"field": "name"}])
        self.assertEqual(payload["error"]["extra"], {"scope": "test"})

    def test_request_validation_error_uses_unified_envelope(self) -> None:
        response = self.client.post("/validate", json={"name": "demo", "count": "oops"})

        self.assertEqual(response.status_code, 422, response.text)
        payload = response.json()
        self.assertEqual(payload["request_id"], "req-phase-b")
        self.assertEqual(payload["error"]["code"], "validation_failed")
        self.assertEqual(payload["error"]["message"], "Validation failed")
        self.assertTrue(payload["error"]["details"])
        self.assertEqual(payload["error"]["details"][0]["loc"], ["body", "count"])

    def test_http_exception_uses_unified_envelope(self) -> None:
        response = self.client.get("/missing-route")

        self.assertEqual(response.status_code, 404, response.text)
        payload = response.json()
        self.assertEqual(payload["request_id"], "req-phase-b")
        self.assertEqual(payload["error"]["code"], "route_not_found")
        self.assertEqual(payload["error"]["message"], "Route not found")


if __name__ == "__main__":
    unittest.main()
