from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from platform_api.config import Settings
from platform_api.main import create_app


class CorsMiddlewareOrderTest(unittest.TestCase):
    def test_unauthorized_response_keeps_cors_headers(self) -> None:
        settings = Settings(
            platform_db_enabled=False,
            auth_required=True,
            cors_allow_origins=("http://127.0.0.1:3000",),
        )

        with patch("platform_api.main.load_settings", return_value=settings):
            app = create_app()

        client = TestClient(app)
        response = client.get(
            "/api/projects",
            headers={"Origin": "http://127.0.0.1:3000"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"), "http://127.0.0.1:3000"
        )
        self.assertEqual(response.headers.get("vary"), "Origin")
        request_id = response.headers["x-request-id"]
        self.assertRegex(request_id, r"^[0-9a-f]{32}$")
        self.assertEqual(response.headers["x-trace-id"], request_id)
        self.assertIn("x-request-id", response.headers["access-control-expose-headers"])
        self.assertIn("x-trace-id", response.headers["access-control-expose-headers"])

        forged = client.get(
            "/api/projects",
            headers={
                "Origin": "http://127.0.0.1:3000",
                "x-request-id": "attacker-request",
                "x-trace-id": "attacker-trace",
            },
        )
        self.assertRegex(forged.headers["x-request-id"], r"^[0-9a-f]{32}$")
        self.assertNotEqual(forged.headers["x-request-id"], request_id)
        self.assertEqual(forged.headers["x-trace-id"], forged.headers["x-request-id"])
        self.assertEqual(forged.json()["request_id"], forged.headers["x-request-id"])


if __name__ == "__main__":
    unittest.main()
