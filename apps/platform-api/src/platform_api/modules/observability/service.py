from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from platform_api.config import Settings
from platform_api.modules.observability.models import TraceLogEntry, TraceLogsResponse

logger = logging.getLogger(__name__)

_SAFE_TRACE_ID_RE = re.compile(r"^[0-9a-zA-Z_-]{8,64}$")
_JSON_OBJECT_RE = re.compile(r"(\{.*\})")


class ObservabilityService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def get_trace_logs(self, trace_id: str) -> TraceLogsResponse:
        trace_id = trace_id.strip()
        if not _SAFE_TRACE_ID_RE.match(trace_id):
            return TraceLogsResponse(
                trace_id=trace_id,
                total=0,
                logs=[],
                error="invalid_trace_id_format",
            )

        loki_url = self._settings.loki_url.rstrip("/")
        # 针对 systemd-journal 与 app-file-logs 进行全局文本匹配检索，排除自身内部代理回显日志
        logql = f'{{job=~"systemd-journal|app-file-logs"}} |= "{trace_id}" !~ "loki/api/v1/query"'
        endpoint = f"{loki_url}/loki/api/v1/query_range"

        try:
            async with httpx.AsyncClient(
                timeout=self._settings.loki_timeout_seconds
            ) as client:
                resp = await client.get(
                    endpoint,
                    params={
                        "query": logql,
                        "limit": 100,
                        "direction": "forward",
                    },
                )
        except Exception as exc:
            logger.warning("Failed to connect to Loki at %s: %s", loki_url, exc)
            return TraceLogsResponse(
                trace_id=trace_id,
                total=0,
                logs=[],
                error="loki_service_unavailable",
            )

        if resp.status_code != 200:
            logger.warning("Loki returned status %d: %s", resp.status_code, resp.text)
            return TraceLogsResponse(
                trace_id=trace_id,
                total=0,
                logs=[],
                error=f"loki_query_failed_{resp.status_code}",
            )

        try:
            data = resp.json()
        except Exception:
            return TraceLogsResponse(
                trace_id=trace_id,
                total=0,
                logs=[],
                error="invalid_loki_json_response",
            )

        results = data.get("data", {}).get("result", [])
        raw_entries: list[tuple[int, str, dict[str, str]]] = []
        for stream in results:
            stream_labels = stream.get("stream", {})
            values = stream.get("values", [])
            for item in values:
                if len(item) >= 2:
                    try:
                        nanos = int(item[0])
                    except (ValueError, TypeError):
                        nanos = 0
                    raw_entries.append((nanos, str(item[1]), stream_labels))

        # 按纳秒时间戳升序排序
        raw_entries.sort(key=lambda x: x[0])

        parsed_logs: list[TraceLogEntry] = []
        services_set: set[str] = set()
        valid_nanos_list: list[int] = []

        for nanos, raw_line, labels in raw_entries:
            # 过滤内部观测回显请求与调试噪音（如 httpx 自身请求 Loki 的记录）
            if "loki/api/v1/query" in raw_line or (
                "httpx" in raw_line and "3100" in raw_line
            ):
                continue

            service = labels.get("service") or ""
            level = "info"
            event = ""
            summary = ""
            span_id = ""
            duration_ms: float | None = None
            payload: dict[str, Any] = {}

            # 尝试提取内嵌 JSON
            json_match = _JSON_OBJECT_RE.search(raw_line)
            if json_match:
                try:
                    payload = json.loads(json_match.group(1))
                    if isinstance(payload, dict):
                        service = payload.get("service") or service
                        level = (payload.get("level") or "info").lower()
                        event = payload.get("event") or ""
                        span_id = payload.get("span_id") or ""
                        if "duration_ms" in payload:
                            try:
                                duration_ms = round(float(payload["duration_ms"]), 2)
                            except (ValueError, TypeError):
                                pass

                        # 构造人话摘要
                        if event == "http.request.completed":
                            method = payload.get("method", "")
                            path = payload.get("path", "")
                            status = payload.get("status_code", "")
                            duration = payload.get("duration_ms", "")
                            summary = f"{method} {path} -> {status} ({duration}ms)"
                        elif event.startswith("runtime.stream"):
                            summary = (
                                f"{event} thread: {payload.get('thread_id', '')[:8]}..."
                            )
                        elif event:
                            summary = f"{event}"
                except Exception:
                    pass

            if not service:
                if "platform-api" in raw_line:
                    service = "platform-api"
                elif "runtime-service" in raw_line or "graphharbor" in raw_line:
                    service = "runtime-service"
                else:
                    service = "system"

            if duration_ms is None:
                # 尝试从文本如 (21.2ms) 或 in 21.2ms 提取
                duration_match = re.search(
                    r"\(?([0-9]+(?:\.[0-9]+)?)\s*ms\)?", raw_line
                )
                if duration_match:
                    try:
                        duration_ms = round(float(duration_match.group(1)), 2)
                    except (ValueError, TypeError):
                        pass

            if not summary:
                # 普通文本截取有效信息
                cleaned = raw_line.strip()
                if len(cleaned) > 120:
                    summary = cleaned[:120] + "..."
                else:
                    summary = cleaned

            if "error" in level or "err" in raw_line.lower():
                if level != "debug":
                    level = "error" if "error" in raw_line.lower() else level

            # 格式化时间戳
            try:
                dt = datetime.fromtimestamp(nanos / 1e9, tz=UTC)
                ts_str = dt.isoformat()
            except Exception:
                ts_str = ""

            if nanos > 0:
                valid_nanos_list.append(nanos)
            services_set.add(service)
            parsed_logs.append(
                TraceLogEntry(
                    timestamp=ts_str,
                    nanos=str(nanos),
                    service=service,
                    level=level,
                    event=event,
                    summary=summary,
                    span_id=span_id,
                    duration_ms=duration_ms,
                    payload=payload,
                    raw=raw_line,
                )
            )

        total_trace_duration_ms: float | None = None
        if len(valid_nanos_list) >= 2:
            total_trace_duration_ms = round(
                (max(valid_nanos_list) - min(valid_nanos_list)) / 1e6, 2
            )
        elif parsed_logs and parsed_logs[0].duration_ms is not None:
            total_trace_duration_ms = parsed_logs[0].duration_ms

        return TraceLogsResponse(
            trace_id=trace_id,
            total=len(parsed_logs),
            duration_ms=total_trace_duration_ms,
            services=sorted(list(services_set)),
            logs=parsed_logs,
        )
