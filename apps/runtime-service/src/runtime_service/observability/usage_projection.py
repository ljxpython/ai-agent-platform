"""Runtime-owned background maintenance of rebuildable usage aggregates."""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, suppress

from runtime_service.db.repositories.usage_projection import project_pending
from runtime_service.db.usage_connections import close_query_pool

logger = logging.getLogger(__name__)


async def _loop(executor):
    while True:
        try:
            await asyncio.get_running_loop().run_in_executor(executor, project_pending)
        except Exception as exc:
            logger.warning("Usage projection unavailable kind=%s", type(exc).__name__)
        await asyncio.sleep(0.5)


@asynccontextmanager
async def usage_projection_lifespan():
    if not os.getenv("DATABASE_URI"):
        yield
        return
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="usage-projector")
    task = asyncio.create_task(_loop(executor), name="runtime-usage-projector")
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await asyncio.to_thread(executor.shutdown, wait=True)
        await asyncio.to_thread(close_query_pool)
