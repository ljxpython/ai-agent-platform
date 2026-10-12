import asyncio
import threading

from runtime_service.observability import usage_projection as module


def test_projection_lifespan_joins_inflight_work_on_shutdown(monkeypatch):
    entered, release, exited = threading.Event(), threading.Event(), threading.Event()

    def work():
        entered.set()
        assert release.wait(2)
        exited.set()

    monkeypatch.setenv("DATABASE_URI", "configured")
    monkeypatch.setattr(module, "project_pending", work)

    async def verify():
        context = module.usage_projection_lifespan()
        await context.__aenter__()
        assert await asyncio.to_thread(entered.wait, 1)
        stopping = asyncio.create_task(context.__aexit__(None, None, None))
        await asyncio.sleep(0.02)
        assert not stopping.done()
        release.set()
        await stopping
        assert exited.is_set()

    try:
        asyncio.run(verify())
    finally:
        release.set()


def test_projection_lifespan_without_database_is_idle(monkeypatch):
    monkeypatch.delenv("DATABASE_URI", raising=False)

    def unexpected():
        raise AssertionError("projector must not start without DB")

    monkeypatch.setattr(module, "project_pending", unexpected)

    async def verify():
        async with module.usage_projection_lifespan():
            await asyncio.sleep(0)

    asyncio.run(verify())
