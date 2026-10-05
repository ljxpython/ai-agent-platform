"""Runtime-owned schedule preview using the scheduler's exact parser."""

from datetime import UTC, datetime
from uuid import UUID

from croniter import CroniterBadCronError, CroniterBadDateError
from fastapi import APIRouter, Header, HTTPException, Query
from langgraph_runtime_pg.cron import next_cron_date
from langgraph_runtime_pg.database import connect
from langgraph_runtime_pg.run_store import RunRepository
from pydantic import BaseModel, ConfigDict, Field

from runtime_service.auth.platform import authenticate

router = APIRouter()


class Preview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schedule: str = Field(min_length=1, max_length=256)
    timezone: str
    after: datetime
    end_time: datetime | None = None
    count: int = Field(default=5, ge=1, le=20)


@router.post("/internal/crons/preview")
async def preview_cron(
    payload: Preview, authorization: str | None = Header(default=None)
):
    facts = await authenticate(authorization)
    if facts["runtime_scope"]["operation"] != "cron-read":
        raise HTTPException(403, "Cron preview scope denied")
    if payload.after.tzinfo is None or (
        payload.end_time and payload.end_time.tzinfo is None
    ):
        raise HTTPException(422, "Dates require a UTC offset")
    cursor, times = payload.after.astimezone(UTC), []
    try:
        for _ in range(payload.count):
            try:
                cursor = next_cron_date(payload.schedule, cursor, payload.timezone)
            except CroniterBadDateError as exc:
                if not times:
                    raise HTTPException(
                        422, "Cron expression has no future occurrence"
                    ) from exc
                break
            if payload.end_time and cursor > payload.end_time:
                break
            times.append(cursor.isoformat())
    except (CroniterBadCronError, KeyError, ValueError) as exc:
        raise HTTPException(422, "Invalid cron expression or timezone") from exc
    return {"times": times, "timezone": payload.timezone}


@router.get("/internal/crons/{task_id}/runs")
async def cron_runs(
    task_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    authorization: str | None = Header(default=None),
):
    user = await authenticate(authorization)
    if user["runtime_scope"]["operation"] != "cron-read":
        raise HTTPException(403, "Cron history scope denied")
    filters = {
        "cron_id": str(task_id),
        "project_id": user["project_id"],
        "scheduled_owner": user["identity"],
        "scheduled_tenant": user["tenant_id"],
    }
    async with connect() as conn:
        rows, total = await RunRepository().search(
            conn.session, metadata=filters, limit=limit, offset=offset
        )
        items = [
            {
                "cron_id": str(task_id),
                "run_id": str(row.run_id),
                "thread_id": str(row.thread_id) if row.thread_id else None,
                "status": row.status,
                "trigger": row.metadata_.get("trigger", "scheduled"),
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
                "error_code": row.metadata_.get("error_code", row.reason)
                if row.status == "error"
                else None,
            }
            for row in rows
        ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}
