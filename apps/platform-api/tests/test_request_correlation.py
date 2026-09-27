from __future__ import annotations

import asyncio
import re
import unittest

import httpx
from fastapi import FastAPI, Request

from platform_api.core.context import get_current_request_context
from platform_api.entrypoints.http.middleware.request_context import (
    register_request_context_middleware,
)


class RequestCorrelationTest(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_requests_do_not_inherit_external_or_sibling_ids(self):
        app = FastAPI()
        register_request_context_middleware(app)

        @app.get("/context")
        async def context(request: Request):
            await asyncio.sleep(0.01)
            current = get_current_request_context().request
            return {
                "request_id": current.request_id,
                "state_id": request.state.request_id,
            }

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            responses = await asyncio.gather(
                *(
                    client.get("/context", headers={"x-request-id": "external-id"})
                    for _ in range(12)
                )
            )
            later = await client.get("/context")

        ids = [response.headers["x-request-id"] for response in (*responses, later)]
        self.assertEqual(len(set(ids)), 13)
        for response, request_id in zip((*responses, later), ids, strict=True):
            self.assertRegex(request_id, re.compile(r"^[0-9a-f]{32}$"))
            self.assertEqual(
                response.json(), {"request_id": request_id, "state_id": request_id}
            )
            self.assertEqual(response.headers["x-trace-id"], request_id)
        with self.assertRaisesRegex(RuntimeError, "request_context_not_bound"):
            get_current_request_context()


if __name__ == "__main__":
    unittest.main()
