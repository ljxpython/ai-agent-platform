from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from platform_api.entrypoints.http.router import api_router


class RetiredBusinessRoutesTest(unittest.TestCase):
    def test_retired_business_endpoints_are_not_registered(self) -> None:
        app = FastAPI()
        app.include_router(api_router)

        paths = app.openapi()["paths"]
        self.assertTrue(paths)
        self.assertFalse(any("knowledge" in path or "testcase" in path for path in paths))
        with TestClient(app) as client:
            for path in (
                "/api/projects/project-1/knowledge",
                "/api/projects/project-1/knowledge/documents",
                "/api/testcase/cases",
                "/api/testcase/documents",
            ):
                with self.subTest(path=path):
                    self.assertEqual(client.get(path).status_code, 404)
                    self.assertEqual(client.post(path, json={}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
