"""Extract runtime loop observation signals from gateway diagnostics payloads."""

from __future__ import annotations

from typing import Any


def recover_loop_signals(diagnostics: list[dict[str, Any]]) -> tuple[int, bool]:
    """Count confirmed or observed loop signals across run diagnostics receipts.

    Returns `(signals_count, observed)` where `observed=False` means diagnostics
    telemetry was unavailable rather than guaranteed zero.
    """
    if not diagnostics:
        return 0, False

    observed = False
    signals = 0
    for item in diagnostics:
        if not isinstance(item, dict):
            continue
        avail = str(item.get("availability") or "")
        if avail in {"available", "partial"}:
            observed = True
        obs_list = item.get("observations")
        if isinstance(obs_list, list):
            for obs in obs_list:
                if not isinstance(obs, dict):
                    continue
                ev_name = str(obs.get("event") or obs.get("name") or "")
                fields = obs.get("fields") if isinstance(obs.get("fields"), dict) else obs
                if "loop" in ev_name:
                    observed = True
                    sig_val = fields.get("signals")
                    if isinstance(sig_val, int) and sig_val >= 0:
                        signals += sig_val
                    elif fields.get("confirmation_status") == "suspected" or ev_name.endswith("transition"):
                        signals += 1
        loop_det = item.get("loop_detection") or item.get("loop_observation")
        if isinstance(loop_det, dict):
            observed = True
            sig_val = loop_det.get("signals", loop_det.get("loop_signals", 0))
            if isinstance(sig_val, int) and sig_val > 0:
                signals += sig_val
    return signals, observed
