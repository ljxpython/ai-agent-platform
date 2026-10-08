"""Reuse committed preparation results; resource operations must remain idempotent."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from typing import Annotated, NotRequired

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import PrivateStateAttr

from runtime_service.observability.diagnostics import log_diagnostic
from runtime_service.observability.langfuse import record_diagnostic_event
from runtime_service.runtime import verified_delegation_from_user
from runtime_service.runtime.errors import RuntimeAuthError, RuntimeResolutionError


def merge_preparations(left: dict, right: dict) -> dict[str, str]:
    merged = {**left, **right}
    if len(merged) > 16 or any(
        not isinstance(key, str)
        or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key)
        or not isinstance(value, str)
        or not re.fullmatch(r"[0-9a-f]{64}", value)
        for key, value in merged.items()
    ):
        raise RuntimeResolutionError("runtime.prepare.invalid_state")
    return merged


class RunPrepareState(AgentState):
    runtime_prepare: NotRequired[
        Annotated[dict[str, str], PrivateStateAttr, merge_preparations]
    ]


class RunPrepareMiddleware(AgentMiddleware):
    state_schema = RunPrepareState

    @property
    def name(self):
        return f"{type(self).__name__}_{self.component}"

    def __init__(
        self, component: str, config_hash: str | None, *, metadata=None, revision=1
    ):
        super().__init__()
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", component):
            raise ValueError("Invalid preparation component")
        self.component = component
        self.config_hash = config_hash
        self.metadata = dict(metadata or {})
        self.revision = revision

    def _validate(self, runtime) -> None:
        raise NotImplementedError

    def _is_prepared(self) -> bool:
        raise NotImplementedError

    def _prepare(self) -> None:
        raise NotImplementedError

    def _fingerprint(self, runtime, config) -> str | None:
        facts = verified_delegation_from_user(runtime.server_info.user)
        info = runtime.execution_info
        execution_id = getattr(info, "run_id", None)
        metadata_id = (config.get("metadata") or {}).get("run_id")
        if execution_id and metadata_id and str(execution_id) != str(metadata_id):
            raise RuntimeAuthError("runtime.prepare.identity_mismatch")
        run_id = execution_id or metadata_id
        if not run_id or not self.config_hash:
            return None
        identity = {
            "schema": 1,
            "run": str(run_id),
            "tenant": facts.principal.tenant_id,
            "project": facts.principal.project_id,
            "thread": info.thread_id,
            "graph": runtime.server_info.graph_id,
            # The final segment identifies this hook task, which changes when
            # rescheduled. Only the owning graph namespace belongs in the latch.
            "namespace": (config.get("metadata") or {})
            .get("langgraph_checkpoint_ns", "")
            .rpartition("|")[0],
            "component": self.component,
            "config": self.config_hash,
            "revision": self.revision,
        }
        return hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def _record(self, config, outcome, started):
        fields = {
            **self.metadata,
            "component": self.component,
            "scope": self.metadata.get("scope", "primary"),
            "namespace": (config.get("metadata") or {})
            .get("langgraph_checkpoint_ns", "")
            .split("|"),
            "outcome": outcome,
            "error_code": "prepare_failed" if outcome == "failed" else None,
            "duration_ms": round((time.monotonic() - started) * 1000, 3),
        }
        try:
            log_diagnostic("runtime.prepare.completed", fields)
            record_diagnostic_event("runtime.prepare.completed", fields)
        except Exception:
            pass

    async def abefore_agent(self, state, runtime, config):
        started = time.monotonic()
        try:
            self._validate(runtime)
            fingerprint = self._fingerprint(runtime, config)
            markers = merge_preparations({}, state.get("runtime_prepare", {}))
            if fingerprint:
                merge_preparations(markers, {self.component: fingerprint})
            ready = await asyncio.to_thread(self._is_prepared)
            matching = fingerprint and markers.get(self.component) == fingerprint
            if matching and ready:
                self._record(config, "reused", started)
                return None
            await asyncio.to_thread(self._prepare)
            self._record(config, "repaired" if matching else "prepared", started)
            return (
                {"runtime_prepare": {self.component: fingerprint}}
                if fingerprint
                else None
            )
        except Exception:
            self._record(config, "failed", started)
            raise


__all__ = ["RunPrepareMiddleware", "RunPrepareState"]
