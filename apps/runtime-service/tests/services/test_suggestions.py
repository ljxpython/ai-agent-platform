from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from runtime_service.runtime.auth import RuntimeScope, VerifiedDelegation
from runtime_service.runtime.contracts import RuntimePolicy, RuntimePrincipal
from runtime_service.runtime.resolver import runtime_context_hash
from runtime_service.services.suggestions import clean_suggestions, generate_suggestions


def _facts() -> VerifiedDelegation:
    return VerifiedDelegation(
        principal=RuntimePrincipal(
            user_id="user-1",
            tenant_id="tenant-1",
            project_id="project-1",
            role="editor",
            permissions=(),
        ),
        policy=RuntimePolicy(
            version="policy-1",
            allowed_model_ids=("model-1",),
            denied_tool_names=(),
            tool_policy_version="tools-1",
        ),
        scope=RuntimeScope(
            tenant_id="tenant-1",
            project_id="project-1",
            assistant_id="agent-1",
            thread_id="thread-1",
            operation="suggestions-generate",
        ),
        context_hash=runtime_context_hash({}),
    )


def test_clean_suggestions_strips_provider_wrappers_and_deduplicates() -> None:
    response = SimpleNamespace(
        content='<think>ignore</think>```json\n["  下一步是什么？ ", "下一步是什么？", 3]\n```'
    )
    assert clean_suggestions(response, count=3) == ["下一步是什么？"]


def test_clean_suggestions_rejects_long_items() -> None:
    response = SimpleNamespace(content='["' + "x" * 121 + '", "ok"]')
    assert clean_suggestions(response, count=3) == ["ok"]


def test_generate_suggestions_calls_model_once_and_returns_empty_on_failure() -> None:
    class Model:
        def __init__(self, result: object) -> None:
            self.result = result
            self.calls = 0

        async def ainvoke(self, _messages: object) -> object:
            self.calls += 1
            if isinstance(self.result, BaseException):
                raise self.result
            return self.result

    payload = {
        "messages": [{"role": "user", "content": "解释这个架构"}],
        "n": 2,
        "context": {},
        "timeout_seconds": 1.0,
    }
    model = Model(SimpleNamespace(content='["比较方案", "给出下一步"]'))
    result = asyncio.run(
        generate_suggestions(
            facts=_facts(), thread_id="thread-1", payload=payload, model=model
        )
    )
    assert result == ["比较方案", "给出下一步"]
    assert model.calls == 1

    failed = Model(RuntimeError("provider down"))
    assert (
        asyncio.run(
            generate_suggestions(
                facts=_facts(), thread_id="thread-1", payload=payload, model=failed
            )
        )
        == []
    )


def test_generate_suggestions_timeout_is_best_effort() -> None:
    class SlowModel:
        async def ainvoke(self, _messages: object) -> object:
            await asyncio.sleep(0.05)
            return SimpleNamespace(content='["too late"]')

    payload = {
        "messages": [{"role": "user", "content": "继续"}],
        "n": 1,
        "context": {},
        "timeout_seconds": 0.001,
    }
    assert (
        asyncio.run(
            generate_suggestions(
                facts=_facts(), thread_id="thread-1", payload=payload, model=SlowModel()
            )
        )
        == []
    )


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "system", "content": "forbidden"}],
        [{"role": "user", "content": " "}],
    ],
)
def test_generate_suggestions_rejects_invalid_messages(messages: list[dict]) -> None:
    with pytest.raises(ValueError):
        asyncio.run(
            generate_suggestions(
                facts=_facts(),
                thread_id="thread-1",
                payload={"messages": messages, "n": 1, "context": {}},
                model=SimpleNamespace(),
            )
        )
