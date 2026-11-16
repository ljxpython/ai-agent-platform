from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass


def compute_alert_fingerprint(source: str, alert_type: str, target_id: str) -> str:
    """计算告警全局唯一指纹 (32位十六进制摘要)."""
    raw = f"{source.strip().lower()}:{alert_type.strip().lower()}:{target_id.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


@dataclass
class AlertThrottleEntry:
    fingerprint: str
    first_triggered_at: float
    last_triggered_at: float
    occurrence_count: int = 1


class AlertGovernanceEngine:
    """告警治理与防抖收敛引擎 (滑动窗口抑制告警风暴)."""

    def __init__(self, cooldown_seconds: float = 300.0) -> None:
        self.cooldown_seconds = cooldown_seconds
        # 内存防抖缓存: fingerprint -> AlertThrottleEntry
        self._cache: dict[str, AlertThrottleEntry] = {}

    def evaluate(
        self,
        source: str,
        alert_type: str,
        target_id: str,
    ) -> tuple[str, bool, int]:
        """评估告警是否应触发外部通知.

        返回: (fingerprint, should_dispatch, current_occurrence_count)
        - should_dispatch = True: 首发或冷却期已过，必须对外发送
        - should_dispatch = False: 冷却期内抑制中，静默仅累加计数
        """
        now = time.time()
        fingerprint = compute_alert_fingerprint(source, alert_type, target_id)

        entry = self._cache.get(fingerprint)
        if entry is None or (now - entry.first_triggered_at > self.cooldown_seconds):
            # 新告警或冷却期已超，重置窗口并触发发送
            self._cache[fingerprint] = AlertThrottleEntry(
                fingerprint=fingerprint,
                first_triggered_at=now,
                last_triggered_at=now,
                occurrence_count=1,
            )
            return fingerprint, True, 1

        # 冷却期内命中：抑制外部发送，仅累加计数
        entry.occurrence_count += 1
        entry.last_triggered_at = now
        return fingerprint, False, entry.occurrence_count

    def get_and_clear_resolve_stats(
        self,
        source: str,
        alert_type: str,
        target_id: str,
    ) -> tuple[str, float, int] | None:
        """告警恢复时获取统计数据 (fingerprint, duration_seconds, total_occurrences) 并清除缓存."""
        fingerprint = compute_alert_fingerprint(source, alert_type, target_id)
        entry = self._cache.pop(fingerprint, None)
        if not entry:
            return None
        duration = max(0.0, time.time() - entry.first_triggered_at)
        return fingerprint, duration, entry.occurrence_count
