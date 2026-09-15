"""Disposable P0 MCP task server. SQLite is a test fixture, not production storage."""
import asyncio
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import sqlite3
import time

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server("dear-p0-task-probe")
database = Path(os.environ["DEAR_PROBE_DB"])
with sqlite3.connect(database) as db:
    db.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, status TEXT, created TEXT, ready REAL)")


def read_task(identifier):
    with sqlite3.connect(database) as db:
        row = db.execute("SELECT status,created,ready FROM tasks WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise ValueError("unknown task")
        status, created, ready = row
        if status == "working" and time.time() >= ready:
            status = "completed"
            db.execute("UPDATE tasks SET status=? WHERE id=?", (status, identifier))
    return dict(taskId=identifier, status=status, createdAt=created, lastUpdatedAt=created, ttl=600000, pollInterval=50)


@server.list_tools()
async def tools():
    return [types.Tool(name="generate", description="Synthetic task with provider-specific idempotency",
                       inputSchema={"type": "object", "properties": {"key": {"type": "string"}, "delay": {"type": "number"}}, "required": ["key"]},
                       execution=types.ToolExecution(taskSupport="required"))]


@server.call_tool()
async def generate(name, arguments):
    if name != "generate":
        raise ValueError("unknown tool")
    identifier = hashlib.sha256(arguments["key"].encode()).hexdigest()
    with sqlite3.connect(database) as db:
        db.execute("INSERT OR IGNORE INTO tasks VALUES (?,?,?,?)",
                   (identifier, "working", datetime.now(timezone.utc).isoformat(), time.time() + arguments.get("delay", 0)))
    if os.environ.get("DEAR_PROBE_DROP_ACK") == "1":
        # Crash after durable remote acceptance, before returning the handle.
        os._exit(17)
    return types.CreateTaskResult(task=types.Task(**read_task(identifier)))


@server.experimental.get_task()
async def get_task(request: types.GetTaskRequest):
    return types.GetTaskResult(**read_task(request.params.taskId))


@server.experimental.get_task_result()
async def get_result(request: types.GetTaskPayloadRequest):
    task = read_task(request.params.taskId)
    if task["status"] != "completed":
        raise ValueError("task is not complete")
    return types.GetTaskPayloadResult(**types.CallToolResult(
        content=[types.TextContent(type="text", text="synthetic-result")]).model_dump())


@server.experimental.cancel_task()
async def cancel(request: types.CancelTaskRequest):
    task = read_task(request.params.taskId)
    if task["status"] == "working":
        with sqlite3.connect(database) as db:
            db.execute("UPDATE tasks SET status='cancelled' WHERE id=?", (request.params.taskId,))
    return types.CancelTaskResult(**read_task(request.params.taskId))


async def main():
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
