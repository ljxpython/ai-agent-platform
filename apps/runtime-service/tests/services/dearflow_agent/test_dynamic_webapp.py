"""Agent Server loads the custom app under a synthetic module name."""
import asyncio
import importlib.util
from pathlib import Path

import httpx


def test_dynamic_webapp_validates_queue_body_without_forward_reference_error():
    path = Path(__file__).resolve().parents[3] / "src/runtime_service/webapp.py"
    spec = importlib.util.spec_from_file_location("dear_dynamic_webapp_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=module.app), base_url="http://test") as client:
            result = await client.post("/internal/threads/thread/messages", json={})
            assert result.status_code == 422
    asyncio.run(run())
