from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.factory import create_app


class CorsMiddlewareOrderTest(unittest.TestCase):
    def test_unauthorized_response_keeps_cors_headers(self) -> None:
        settings = Settings(
            platform_db_enabled=False,
            auth_required=True,
            cors_allow_origins=("http://127.0.0.1:3000",),
        )

        with patch("app.factory.load_settings", return_value=settings):
            app = create_app()

        client = TestClient(app)
        response = client.get(
            "/api/projects",
            headers={"Origin": "http://127.0.0.1:3000"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://127.0.0.1:3000")
        self.assertEqual(response.headers.get("vary"), "Origin")


if __name__ == "__main__":
    unittest.main()
