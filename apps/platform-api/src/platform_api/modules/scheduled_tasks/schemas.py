from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Schedule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schedule_type: Literal["cron", "once"] = "cron"
    cron: str | None = None
    run_at: datetime | None = None
    timezone: str = "Asia/Shanghai"
    end_time: datetime | None = None

    @model_validator(mode="after")
    def validate_schedule(self):
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown IANA timezone") from exc
        if self.schedule_type == "once":
            if self.cron or self.end_time or not self.run_at:
                raise ValueError("once requires run_at only")
            if self.run_at.tzinfo is None or self.run_at.microsecond:
                raise ValueError("run_at requires a UTC offset and whole seconds")
        elif not self.cron or self.run_at or len(self.cron.split()) != 5:
            raise ValueError("cron requires a five-field expression only")
        if self.end_time and self.end_time.tzinfo is None:
            raise ValueError("end_time requires a UTC offset")
        return self


class TaskCreate(Schedule):
    title: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=100_000)
    agent_key: str = Field(min_length=1, max_length=128)
    thread_mode: Literal["fresh", "reuse"] = "fresh"
    thread_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_task(self):
        if not self.title.strip() or not self.prompt.strip():
            raise ValueError("title and prompt cannot be blank")
        if (self.thread_mode == "reuse") != bool(self.thread_id):
            raise ValueError("thread_id is required only for reuse mode")
        if self.thread_id:
            self.thread_id = str(UUID(self.thread_id))
        if "offload_conversation" in self.context:
            raise ValueError("Scheduled tasks cannot request conversation offloading")
        return self


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=120)
    prompt: str | None = Field(default=None, min_length=1, max_length=100_000)
    cron: str | None = None
    run_at: datetime | None = None
    timezone: str | None = None
    end_time: datetime | None = None
    context: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        if any(
            getattr(self, key) is None for key in self.model_fields_set - {"end_time"}
        ):
            raise ValueError("Only end_time can be cleared")
        if "offload_conversation" in (self.context or {}):
            raise ValueError("Scheduled tasks cannot request conversation offloading")
        return self
