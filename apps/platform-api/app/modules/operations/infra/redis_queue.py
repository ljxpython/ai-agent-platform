from __future__ import annotations

from redis.asyncio import Redis

from app.modules.operations.application.ports import (
    OperationDispatcherProtocol,
    OperationQueueConsumerProtocol,
    StoredOperation,
)


class RedisListOperationQueue(OperationDispatcherProtocol, OperationQueueConsumerProtocol):
    def __init__(
        self,
        *,
        redis_url: str,
        queue_name: str,
    ) -> None:
        self._redis_url = redis_url
        self._queue_name = queue_name

    async def dispatch(self, *, operation: StoredOperation) -> None:
        client = Redis.from_url(self._redis_url, decode_responses=True)
        try:
            await client.lpush(self._queue_name, operation.id)
        finally:
            await client.aclose()

    async def dequeue(self, *, timeout_seconds: float) -> str | None:
        client = Redis.from_url(self._redis_url, decode_responses=True)
        timeout = max(1, int(round(timeout_seconds)))
        try:
            result = await client.brpop(self._queue_name, timeout=timeout)
            if result is None:
                return None

            _, operation_id = result
            normalized = str(operation_id).strip()
            return normalized or None
        finally:
            await client.aclose()
