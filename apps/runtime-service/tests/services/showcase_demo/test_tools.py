import asyncio

import httpx
import pytest

from runtime_service.runtime import (
    RuntimeResolutionError,
    fetch_model_connection,
    modeling,
)
from runtime_service.services.demo.showcase_demo import tools
from runtime_service.services.demo.showcase_demo.tools import fetch_documentation


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://docs.python.org/",
        "https://127.0.0.1/",
        "https://docs.python.org.evil.invalid/",
        "https://user:pass@docs.python.org/",
        "https://docs.python.org:8443/",
        "https://[invalid/",
    ],
)
def test_documentation_rejects_untrusted_urls_without_network(monkeypatch, url):
    def forbidden(*args, **kwargs):
        pytest.fail("Untrusted URL reached the HTTP client")

    monkeypatch.setattr(tools.httpx, "AsyncClient", forbidden)
    result = asyncio.run(fetch_documentation.ainvoke({"url": url}))
    assert "Use an HTTPS URL" in result


@pytest.mark.parametrize("kind", ["text", "redirect", "binary", "large", "failure"])
def test_documentation_fetch_is_bounded_and_reports_failures(monkeypatch, kind):
    def handler(request):
        if kind == "redirect":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/"})
        if kind == "binary":
            return httpx.Response(
                200, content=b"bytes", headers={"content-type": "image/png"}
            )
        if kind == "failure":
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(
            200, text="reference" if kind == "text" else "x" * (tools._MAX_BYTES + 1)
        )

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        tools.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(handler)),
    )
    result = asyncio.run(
        fetch_documentation.ainvoke(
            {"url": "https://docs.python.org/3/library/csv.html"}
        )
    )
    expected = {
        "text": "reference",
        "redirect": "Redirects are not followed",
        "binary": "Only text",
        "large": "truncated at 128 KiB",
        "failure": "request failed",
    }
    assert expected[kind] in result
    assert len(result) < tools._MAX_BYTES + 100


def test_model_reference_is_validated_without_leaking_credentials(monkeypatch):
    monkeypatch.setenv(
        "PLATFORM_RUNTIME_MODEL_CONFIG_URL", "https://platform.invalid/model"
    )
    payload = {
        "model_id": "model-a",
        "provider": "openai",
        "base_url": "https://model.invalid",
        "protocol": "openai",
        "model": "model-a",
        "api_key": "test-only-secret",
    }

    def handler(request):
        assert request.headers["x-runtime-model-ref"] == "opaque-ref"
        assert request.headers["x-project-id"] == "project"
        return httpx.Response(200, json=payload)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        modeling.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(handler)),
    )
    result = asyncio.run(
        fetch_model_connection("opaque-ref", model_id="model-a", project_id="project")
    )
    assert result == payload
    with pytest.raises(RuntimeResolutionError) as error:
        asyncio.run(
            fetch_model_connection(
                "opaque-ref", model_id="model-b", project_id="project"
            )
        )
    assert "test-only-secret" not in str(error.value)
