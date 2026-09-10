from __future__ import annotations

import asyncio
import logging

from dotenv import load_dotenv

from platform_api.config import load_settings
from platform_api.core.db import build_engine, build_session_factory, create_core_tables
from platform_api.core.observability import log_event
from platform_api.modules.operations.bootstrap import build_operation_worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    load_dotenv()
    settings = load_settings()
    if not settings.platform_db_enabled:
        raise RuntimeError("platform_db_enabled must be true before starting the operations worker")
    if not settings.database_url:
        raise RuntimeError("database_url is required before starting the operations worker")

    engine = build_engine(settings.database_url)
    try:
        session_factory = build_session_factory(engine)
        if settings.platform_db_auto_create:
            create_core_tables(engine)

        worker = build_operation_worker(
            settings=settings,
            session_factory=session_factory,
        )
        log_event(
            logger,
            "operation.worker.started",
            queue_backend=settings.operations_queue_backend,
            heartbeat_interval_seconds=settings.operations_worker_heartbeat_interval_seconds,
        )
        await worker.run_forever()
    finally:
        log_event(logger, "operation.worker.stopped")
        engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
