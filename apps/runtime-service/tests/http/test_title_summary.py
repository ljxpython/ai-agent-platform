"""Unit tests for title_summary HTTP endpoint in runtime-service."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient
from unittest.mock import AsyncMock, patch

from runtime_service.webapp import app


@pytest.fixture
def client():
    return TestClient(app)


def test_summarize_title_endpoint_success(client):
    with patch(
        "runtime_service.http.title_summary.summarize_thread_title",
        new_callable=AsyncMock,
    ) as mock_summarize:
        mock_summarize.return_value = "用户注册方案"

        response = client.post(
            "/internal/threads/th-12345/title/summarize",
            json={
                "messages": [
                    {"role": "user", "content": "帮我写一个用户注册接口方案"},
                    {"role": "assistant", "content": "收到，这是方案细节..."},
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["thread_id"] == "th-12345"
        assert data["title"] == "用户注册方案"
        mock_summarize.assert_awaited_once()


def test_summarize_title_endpoint_empty_messages(client):
    with patch(
        "runtime_service.http.title_summary.summarize_thread_title",
        new_callable=AsyncMock,
    ) as mock_summarize:
        mock_summarize.return_value = "新对话"

        response = client.post(
            "/internal/threads/th-empty/title/summarize",
            json={"messages": []},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["thread_id"] == "th-empty"
        assert data["title"] == "新对话"


def test_summarize_title_endpoint_handles_exception_gracefully(client):
    with patch(
        "runtime_service.http.title_summary.summarize_thread_title",
        new_callable=AsyncMock,
    ) as mock_summarize:
        mock_summarize.side_effect = RuntimeError("Fatal LLM crash")

        response = client.post(
            "/internal/threads/th-crash/title/summarize",
            json={
                "messages": [
                    {"role": "user", "content": "崩溃测试"},
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["thread_id"] == "th-crash"
        assert data["title"] == "新对话"
