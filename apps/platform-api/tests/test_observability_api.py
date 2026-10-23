from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from platform_api.main import create_app
from platform_api.modules.observability.service import ObservabilityService


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_invalid_trace_id_format(client: TestClient) -> None:
    resp = client.get("/api/v1/observability/traces/short/logs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["error"] == "invalid_trace_id_format"


@pytest.mark.anyio
async def test_observability_service_parse_loki(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from platform_api.config import Settings

    settings = Settings(loki_url="http://127.0.0.1:3100")
    service = ObservabilityService(settings)

    mock_loki_response = {
        "status": "success",
        "data": {
            "resultType": "streams",
            "result": [
                {
                    "stream": {
                        "job": "systemd-journal",
                        "service": "platform-api",
                        "trace_id": "54aaf459b9c5415b90370e5874dbb255",
                    },
                    "values": [
                        [
                            "1792670225737713000",
                            '2026-10-22 19:57:05,737 [INFO] [middleware] {"service": "platform-api", "event": "http.request.completed", "method": "GET", "path": "/health", "status_code": 200, "duration_ms": 0.44, "span_id": "dd806a17b393455b"}',
                        ]
                    ],
                }
            ],
        },
    }

    class MockResponse:
        status_code = 200

        def json(self):
            return mock_loki_response

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def get(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr("httpx.AsyncClient", MockAsyncClient)

    res = await service.get_trace_logs("54aaf459b9c5415b90370e5874dbb255")
    assert res.total == 1
    assert res.services == ["platform-api"]
    entry = res.logs[0]
    assert entry.service == "platform-api"
    assert entry.event == "http.request.completed"
    assert "GET /health -> 200" in entry.summary
    assert entry.span_id == "dd806a17b393455b"
