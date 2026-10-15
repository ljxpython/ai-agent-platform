import asyncio

from runtime_service.services.dearflow_agent.prescreen import (
    detect_signals,
    prescreen_conversation,
)


def test_detect_signals():
    assert "reinforcement" in detect_signals("以后默认用中文回答我")
    assert "reinforcement" in detect_signals("Please always use TypeScript")
    assert "correction" in detect_signals("不对，其实我更喜欢纯文本")
    assert "correction" in detect_signals("not like that, fix this")
    assert not detect_signals("今天天气怎么样")


def test_prescreen_conversation_short_utterance():
    assert prescreen_conversation([{"text": "好的"}]) == (False, "too_short")
    assert prescreen_conversation([{"text": "收到！"}]) == (False, "too_short")
    assert prescreen_conversation([]) == (False, "no_sources")


def test_prescreen_conversation_signals():
    should, reason = prescreen_conversation(
        [{"text": "记住，我的邮箱是 test@example.com"}]
    )
    assert should is True
    assert "reinforcement" in reason

    should, reason = prescreen_conversation(
        [{"text": "不对，我用的不是 Python 3.10，是 3.12"}]
    )
    assert should is True
    assert "correction" in reason


def test_prescreen_conversation_code_and_commands():
    should, reason = prescreen_conversation([{"text": "git status -s"}])
    assert should is False
    assert reason == "code_or_command"

    should, reason = prescreen_conversation([{"text": "```python\nprint(1)\n```"}])
    assert should is False
    assert reason == "code_or_command"


def test_prescreen_conversation_general_query():
    should, reason = prescreen_conversation([{"text": "什么是 Kubernetes 的 Pod？"}])
    assert should is False
    assert reason == "general_query"


def test_prescreen_conversation_first_person_preference():
    should, reason = prescreen_conversation(
        [{"text": "我认为这个架构设计很好，但我更偏好简洁的方案"}]
    )
    assert should is True
    assert "signals:reinforcement" in reason or "first_person" in reason


def test_async_non_blocking_dispatch_and_drain(monkeypatch):
    async def runner():
        import time
        from types import SimpleNamespace

        from runtime_service.services.dearflow_agent.middleware import (
            memory as middleware_module,
        )

        monkeypatch.delenv("MEMORY_EXTRACTION_SYNC", raising=False)
        monkeypatch.setattr(
            middleware_module, "memory_scope", lambda r: ("t", "p", "u")
        )
        monkeypatch.setattr(
            middleware_module, "memory_allowed", lambda r: asyncio.sleep(0, result=True)
        )

        class Store:
            def begin_extraction(self, *args, **kwargs):
                return kwargs["deadline_at"]

            def reserve_extraction_attempt(self, *args, **kwargs):
                return True

            def propose(self, *args, **kwargs):
                return {"status": "proposed", "added": 1}

            def finish_extraction(self, *args, **kwargs):
                return True

        monkeypatch.setattr(middleware_module, "MemoryStorage", Store)

        async def slow_extract(*args, **kwargs):
            await asyncio.sleep(0.1)
            return {
                "parsed": middleware_module.Candidates(candidates=[]),
                "raw": SimpleNamespace(usage_metadata={}),
            }

        model = SimpleNamespace(
            with_structured_output=lambda *args, **kwargs: SimpleNamespace(
                ainvoke=slow_extract
            )
        )
        middleware = middleware_module.MemoryContextMiddleware(model, sync_mode=False)
        runtime = SimpleNamespace(
            execution_info=SimpleNamespace(thread_id="thread", run_id="run")
        )
        state = {
            "dear_memory_source": {
                "id": "h",
                "text": "我偏好使用简洁的中文回答",
                "epoch": 1,
                "enabled": True,
            }
        }

        start = time.monotonic()
        await middleware.aafter_agent(state, runtime)
        elapsed = time.monotonic() - start

        # Non-blocking: aafter_agent returns almost immediately (< 0.05s) despite model taking 0.1s
        assert elapsed < 0.08
        assert len(middleware._background_tasks) == 1

        # Drain tasks ensures background task completes
        await middleware.drain_tasks(timeout=1.0)
        assert len(middleware._background_tasks) == 0

    asyncio.run(runner())
