"""Platform HTTP client for target snapshots, SSE runs, and judge model resolution."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from eval_runner.targets.sse_probe import SseProbeResult, probe_sse_stream


@dataclass
class PlatformModelConnection:
    model_id: str
    provider: str
    base_url: str
    protocol: str
    model: str
    api_key: str
    context_window_tokens: int | None = None
    pricing: dict[str, Any] | None = None


def sign_internal_payload(secret: str, purpose: str, body_bytes: bytes) -> dict[str, str]:
    stamp = str(int(time.time()))
    message = b"\n".join([purpose.encode(), stamp.encode(), body_bytes])
    sig = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return {
        "content-type": "application/json",
        "x-eval-time": stamp,
        "x-eval-signature": sig,
    }


class PlatformModelResolver:
    """Resolve platform-configured LLM & Embedding connections via internal HMAC API."""

    def __init__(self, base_url: str, internal_secret: str, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.internal_secret = internal_secret
        self.timeout = timeout

    def resolve(self, *, project_id: str, model_id: str) -> PlatformModelConnection:
        body = json.dumps(
            {"project_id": project_id, "model_id": model_id},
            separators=(",", ":"),
        ).encode()
        headers = sign_internal_payload(
            self.internal_secret, "judge-model-config", body
        )
        with httpx.Client(timeout=self.timeout, trust_env=False) as client:
            resp = client.post(
                f"{self.base_url}/api/evaluation/internal/judge-model-config",
                content=body,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
        return PlatformModelConnection(
            model_id=str(data["model_id"]),
            provider=data["provider"],
            base_url=data["base_url"].rstrip("/"),
            protocol=data["protocol"],
            model=data["model"],
            api_key=data["api_key"],
            context_window_tokens=data.get("context_window_tokens"),
            pricing=data.get("pricing"),
        )


class AgentTargetDriver:
    """Drive target Agents over Platform API with SSE TTFT probing."""

    def __init__(
        self,
        base_url: str,
        *,
        bearer_token: str,
        timeout: float = 180.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token
        self.timeout = timeout
        self.clock = clock

    def _headers(self, project_id: str, extra: dict[str, str] | None = None) -> dict[str, str]:
        base = {
            "authorization": f"Bearer {self.bearer_token}",
            "x-project-id": project_id,
            "content-type": "application/json",
        }
        if extra:
            base.update(extra)
        return base

    def create_thread(self, *, project_id: str, metadata: dict[str, Any] | None = None) -> str:
        with httpx.Client(timeout=30.0, trust_env=False) as client:
            resp = client.post(
                f"{self.base_url}/api/langgraph/threads",
                headers=self._headers(project_id),
                json={"metadata": metadata or {}},
            )
            resp.raise_for_status()
            return str(resp.json()["thread_id"])

    def stream_turn(
        self,
        *,
        project_id: str,
        thread_id: str,
        assistant_id: str,
        content: str,
        context: dict[str, Any] | None = None,
        command: dict[str, Any] | None = None,
        idempotency_key: str,
    ) -> SseProbeResult:
        payload: dict[str, Any] = {"assistant_id": assistant_id}
        if command is not None:
            payload["command"] = command
        else:
            payload["input"] = {"messages": [{"role": "user", "content": content}]}
            if context is not None:
                payload["context"] = context

        started = self.clock()
        try:
            with httpx.Client(timeout=self.timeout, trust_env=False) as client:
                with client.stream(
                    "POST",
                    f"{self.base_url}/api/langgraph/threads/{thread_id}/runs/stream",
                    headers=self._headers(
                        project_id, {"Idempotency-Key": idempotency_key}
                    ),
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    return probe_sse_stream(
                        resp.iter_lines(),
                        started_monotonic=started,
                        clock=self.clock,
                    )
        except httpx.TimeoutException:
            elapsed = max(0, int(round((self.clock() - started) * 1000)))
            return SseProbeResult(
                ttft_ms=None,
                duration_ms=elapsed,
                first_event_ms=None,
                final_text="",
                terminal_status="error",
                error_category="stream_timeout",
            )
        except httpx.HTTPError:
            elapsed = max(0, int(round((self.clock() - started) * 1000)))
            return SseProbeResult(
                ttft_ms=None,
                duration_ms=elapsed,
                first_event_ms=None,
                final_text="",
                terminal_status="error",
                error_category="runtime_error",
            )


class InternalExecutionClient:
    """Drive target Agents via platform-api internal HMAC SSE execution proxy."""

    def __init__(
        self,
        base_url: str,
        internal_secret: str,
        *,
        timeout: float = 180.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.base_url = base_url.rstrip("/")
        self.internal_secret = internal_secret
        self.timeout = timeout
        self.clock = clock

    def execute_turn(
        self,
        *,
        run_id: str,
        content: str = "",
        thread_id: str | None = None,
        command: dict[str, Any] | None = None,
        context_overrides: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[str | None, SseProbeResult]:
        payload_dict: dict[str, Any] = {"run_id": run_id}
        if content:
            payload_dict["content"] = content
        if thread_id:
            payload_dict["thread_id"] = thread_id
        if command is not None:
            payload_dict["command"] = command
        if context_overrides:
            payload_dict["context"] = context_overrides
        if idempotency_key:
            payload_dict["idempotency_key"] = idempotency_key
        body = json.dumps(
            payload_dict,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        headers = sign_internal_payload(self.internal_secret, "execute-turn", body)
        started = self.clock()
        resolved_thread_id = thread_id
        try:
            with httpx.Client(timeout=self.timeout, trust_env=False) as client:
                with client.stream(
                    "POST",
                    f"{self.base_url}/api/evaluation/internal/execute-turn",
                    content=body,
                    headers=headers,
                ) as resp:
                    resolved_thread_id = resp.headers.get("x-eval-thread-id") or resolved_thread_id
                    resp.raise_for_status()
                    probe = probe_sse_stream(
                        resp.iter_lines(),
                        started_monotonic=started,
                        clock=self.clock,
                    )
                    return resolved_thread_id, probe
        except httpx.TimeoutException:
            elapsed = max(0, int(round((self.clock() - started) * 1000)))
            return resolved_thread_id, SseProbeResult(
                ttft_ms=None,
                duration_ms=elapsed,
                first_event_ms=None,
                final_text="",
                terminal_status="error",
                error_category="stream_timeout",
            )
        except httpx.HTTPError:
            elapsed = max(0, int(round((self.clock() - started) * 1000)))
            return resolved_thread_id, SseProbeResult(
                ttft_ms=None,
                duration_ms=elapsed,
                first_event_ms=None,
                final_text="",
                terminal_status="error",
                error_category="runtime_error",
            )

    def _post_internal_json(self, purpose: str, payload: dict[str, Any], timeout: float = 20.0) -> dict[str, Any] | None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        headers = sign_internal_payload(self.internal_secret, purpose, body)
        try:
            with httpx.Client(timeout=timeout, trust_env=False) as client:
                resp = client.post(
                    f"{self.base_url}/api/evaluation/internal/{purpose}",
                    content=body,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                return data if isinstance(data, dict) else None
        except httpx.HTTPError:
            return None

    def thread_setup(
        self,
        *,
        run_id: str,
        thread_id: str | None = None,
        fixtures: dict[str, str] | None = None,
        ensure_workspace: bool = False,
    ) -> dict[str, Any] | None:
        return self._post_internal_json(
            "thread-setup",
            {
                "run_id": run_id,
                **({"thread_id": thread_id} if thread_id else {}),
                "fixtures": fixtures or {},
                "ensure_workspace": ensure_workspace,
            },
            timeout=30.0,
        )

    def thread_evidence(
        self,
        *,
        run_id: str,
        thread_id: str,
        run_ids: list[str] | None = None,
        artifact_paths: list[str] | None = None,
    ) -> dict[str, Any] | None:
        return self._post_internal_json(
            "thread-evidence",
            {
                "run_id": run_id,
                "thread_id": thread_id,
                "run_ids": run_ids or [],
                "artifact_paths": artifact_paths or [],
            },
            timeout=30.0,
        )

    def cross_project_probe(
        self,
        *,
        run_id: str,
        thread_id: str,
        isolation_project_id: str | None = None,
    ) -> dict[str, Any] | None:
        return self._post_internal_json(
            "cross-project-probe",
            {
                "run_id": run_id,
                "thread_id": thread_id,
                **({"isolation_project_id": isolation_project_id} if isolation_project_id else {}),
            },
            timeout=15.0,
        )

    def get_thread_usage(self, *, run_id: str, thread_id: str) -> dict[str, Any] | None:
        """Fetch recorded runtime token/cost usage for an executed thread via HMAC bridge."""
        return self._post_internal_json(
            "thread-usage", {"run_id": run_id, "thread_id": thread_id}, timeout=10.0
        )


class PatrolInternalClient:
    """Internal HMAC client for scheduled patrol dispatch & result alert reporting."""

    def __init__(self, base_url: str, internal_secret: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.internal_secret = internal_secret
        self.timeout = timeout

    def _post(self, purpose: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        headers = sign_internal_payload(self.internal_secret, purpose, body)
        with httpx.Client(timeout=self.timeout, trust_env=False) as client:
            resp = client.post(
                f"{self.base_url}/api/evaluation/internal/{purpose}",
                content=body,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, dict) else {}

    def dispatch_schedule(self, schedule_id: str) -> dict[str, Any]:
        return self._post("patrol-dispatch", {"schedule_id": schedule_id})

    def report_patrol(
        self,
        *,
        schedule_id: str,
        run_id: str,
        verdict: str,
        summary_text: str,
        reasons: list[str],
        metrics_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        return self._post(
            "patrol-report",
            {
                "schedule_id": schedule_id,
                "run_id": run_id,
                "verdict": verdict,
                "summary_text": summary_text,
                "reasons": reasons,
                "metrics_snapshot": metrics_snapshot,
            },
        )
