from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from platform_api.core.errors import PlatformApiError, register_exception_handlers


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

    def test_validation_details_exclude_input_and_private_message(self) -> None:
        from platform_api.core.errors.payload import safe_validation_details

        details = safe_validation_details(
            [
                {
                    "loc": ["body", "secret", True, "x" * 129],
                    "type": "missing",
                    "msg": "token=secret",
                    "input": "secret",
                    "ctx": {"key": "secret"},
                }
            ]
            * 20
            + ["malformed"]
        )
        self.assertEqual(len(details), 20)
        self.assertEqual(
            details[0],
            {"loc": ["body", "secret"], "type": "missing", "message": "Field required"},
        )
        self.assertNotIn("token=secret", str(details))
        self.assertEqual(safe_validation_details(["malformed"]), [])

    def test_platform_error_has_matching_request_header(self) -> None:
        response = self.client.get("/platform-error")
        self.assertEqual(
            response.headers["x-request-id"], response.json()["request_id"]
        )

    def test_error_header_allowlist(self) -> None:
        from platform_api.core.errors.payload import safe_error_headers

        headers = {
            "Retry-After": "15",
            "Set-Cookie": "secret=1",
            "Authorization": "Bearer secret",
            "Allow": "GET, POST, bad value",
        }
        self.assertEqual(
            safe_error_headers(429, headers, platform=False), {"Retry-After": "15"}
        )
        self.assertEqual(
            safe_error_headers(405, headers, platform=False), {"Allow": "GET, POST"}
        )
        self.assertEqual(
            safe_error_headers(503, {"Retry-After": "1\r\nsecret"}, platform=False), {}
        )


if __name__ == "__main__":
    unittest.main()
