import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from platform_api.core.errors import ServiceUnavailableError
from platform_api.modules.evaluation import workbench


@pytest.mark.parametrize(
    "receiver,allowed,expected",
    [
        ("http://127.0.0.1:5001", (), True),
        ("http://localhost:5001/", (), True),
        ("http://49.233.222.54:9128", (), False),
        ("http://49.233.222.54:9128/", ("http://49.233.222.54:9128",), True),
        ("https://evalflow.example", ("https://evalflow.example",), True),
        ("http://49.233.222.54:9129", ("http://49.233.222.54:9128",), False),
        (
            "http://49.233.222.54:9128.attacker.example",
            ("http://49.233.222.54:9128",),
            False,
        ),
        ("http://attacker.example", ("*",), False),
        ("http://127.0.0.1:5001/redirect", (), False),
        ("http://127.0.0.1:5001?target=elsewhere", (), False),
        ("http://127.0.0.1:5001/#fragment", (), False),
        ("http://name:secret@localhost:5001", (), False),
        ("http://localhost:bad-port", (), False),
        ("http://[malformed", (), False),
        ("http://local\nhost:5001", (), False),
        ("ftp://localhost", (), False),
    ],
)
def test_receiver_uses_local_or_explicit_exact_origin(
    monkeypatch, receiver, allowed, expected
):
    project_id = "project"
    settings = SimpleNamespace(
        evaluation_project_id=project_id,
        evaluation_source_token="test-only",
        evaluation_receiver_url=receiver,
        evaluation_receiver_allowed_origins=allowed,
        evaluation_receiver_username="receiver",
        evaluation_receiver_password="test-only",
    )
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=settings))
    )
    monkeypatch.setattr(workbench, "issue_command", lambda *args: "signed-command")
    client = AsyncMock()
    client.post.return_value = httpx.Response(
        200, json={"id": "item"}, request=httpx.Request("POST", "http://localhost")
    )
    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=client)
    manager.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=manager)
    monkeypatch.setattr(workbench.httpx, "AsyncClient", factory)

    action = workbench.forward(request, None, project_id, "read", "item", "request", {})
    if not expected:
        with pytest.raises(ServiceUnavailableError) as error:
            asyncio.run(action)
        assert error.value.code == "evaluation_receiver_invalid"
        factory.assert_not_called()
        return

    assert asyncio.run(action) == {"id": "item"}
    assert factory.call_args.kwargs["trust_env"] is False
    assert factory.call_args.kwargs["follow_redirects"] is False
    assert factory.call_args.kwargs["auth"] == ("receiver", "test-only")
    assert (
        client.post.call_args.args[0]
        == receiver.rstrip("/") + "/ajax-api/evalflow/internal/workbench/command"
    )
    assert (
        client.post.call_args.kwargs["headers"]["x-evaluation-command"]
        == "signed-command"
    )
