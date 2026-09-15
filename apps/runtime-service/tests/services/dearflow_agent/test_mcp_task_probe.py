import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
import sqlite3
import sys

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client


def test_mcp_task_ack_loss_restart_result_and_cancel(tmp_path):
    database = tmp_path / "tasks.db"

    @asynccontextmanager
    async def session(drop=False):
        params = StdioServerParameters(command=sys.executable,
            args=[str(Path(__file__).with_name("mcp_task_probe.py"))],
            env={**os.environ, "DEAR_PROBE_DB": str(database), "DEAR_PROBE_DROP_ACK": "1" if drop else "0"})
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                info = await client.initialize()
                assert info.capabilities.tasks.cancel is not None
                yield client

    async def run():
        failed = False
        try:
            async with session(drop=True) as client:
                await client.experimental.call_tool_as_task("generate", {"key": "lost-ack"})
        except (ExceptionGroup, Exception):
            failed = True
        assert failed
        with sqlite3.connect(database) as db:
            assert db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 1
        # Only retry because this test provider explicitly supports a stable key.
        async with session() as client:
            recovered = await client.experimental.call_tool_as_task("generate", {"key": "lost-ack"})
            identifier = recovered.task.taskId
            result = await client.experimental.get_task_result(identifier, types.CallToolResult)
            assert result.content[0].text == "synthetic-result"
            pending = await client.experimental.call_tool_as_task("generate", {"key": "cancel-me", "delay": 3600})
            cancelled = await client.experimental.cancel_task(pending.task.taskId)
            assert cancelled.status == "cancelled"
        async with session() as client:
            assert (await client.experimental.get_task(identifier)).status == "completed"
            assert (await client.experimental.get_task(pending.task.taskId)).status == "cancelled"
        with sqlite3.connect(database) as db:
            assert db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 2
    asyncio.run(asyncio.wait_for(run(), 45))
