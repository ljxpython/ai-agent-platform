"""Small synthetic calibration set; these labels do not establish production accuracy."""

import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from runtime_service.middlewares import loop_detection as module


def test_observation_calibration_reports_false_positives_and_misses(monkeypatch):
    scenarios = [
        ("identical_no_progress", True, [("a", "same")] * 4, 1),
        ("alternating_six", True, [("a", "same"), ("b", "same")] * 3, 1),
        ("alternating_three", True, [("a", "same"), ("b", "same"), ("a", "same")], 0),
        ("authorized_polling", False, [("a", "pending")] * 3, 1),
        ("changing_results", False, [("a", str(i)) for i in range(4)], 0),
        ("bounded_retry", False, [("a", "temporary error")] * 2, 0),
        ("parallel_progress", False, [(str(i), "same") for i in range(4)], 0),
        ("approval_resume", False, [("a", "same")] * 4, 0),
    ]
    rows, events = [], []
    config = {"metadata": {"run_id": "synthetic"}}
    monkeypatch.setattr(module, "get_config", lambda: config)
    monkeypatch.setattr(
        module, "log_diagnostic", lambda event, fields: events.append((event, fields))
    )
    monkeypatch.setattr(module, "record_diagnostic_event", lambda *_: None)
    for name, positive, batches, expected in scenarios:
        events.clear()
        config["metadata"]["run_id"] = name
        mw = module.LoopDetectionMiddleware(["read_file"], observe_only=True)
        state = {"messages": [HumanMessage(id="user", content="synthetic task")]}
        state.update(mw.before_agent(state, Runtime()))
        for i, (path, result) in enumerate(batches):
            if name == "approval_resume" and i == 2:
                config["metadata"]["run_id"] = name + "-resumed"
                state.update(mw.before_agent(state, Runtime()))
            calls = [
                {"id": f"call-{i}", "name": "read_file", "args": {"file_path": path}}
            ]
            if name == "parallel_progress":
                calls.append(
                    {
                        "id": f"parallel-{i}",
                        "name": "read_file",
                        "args": {"file_path": path + "-second"},
                    }
                )
            state["messages"].extend(
                [
                    AIMessage(id=f"ai-{i}", content="", tool_calls=calls),
                    *[
                        ToolMessage(
                            id=call["id"] + "-result",
                            content=result,
                            name=call["name"],
                            tool_call_id=call["id"],
                        )
                        for call in calls
                    ],
                ]
            )
            state.update(mw.before_model(state, Runtime()) or {})
        mw.after_agent(state, Runtime())
        signals = [
            fields for event, fields in events if event == "runtime.loop.observation"
        ]
        assert len(signals) == expected
        assert all(event["confirmation_status"] == "suspected" for event in signals)
        assert len(state["messages"]) == 1 + sum(
            3 if name == "parallel_progress" else 2 for _ in batches
        )
        rows.append(
            {
                "scenario": name,
                "label_loop": positive,
                "signals": len(signals),
                "eligible_batches": state["runtime_loop_state"]["eligible_batches"],
            }
        )
    counts = {
        "true_positive": sum(
            row["label_loop"] and bool(row["signals"]) for row in rows
        ),
        "false_positive": sum(
            not row["label_loop"] and bool(row["signals"]) for row in rows
        ),
        "false_negative": sum(row["label_loop"] and not row["signals"] for row in rows),
        "true_negative": sum(
            not row["label_loop"] and not row["signals"] for row in rows
        ),
    }
    assert counts == {
        "true_positive": 2,
        "false_positive": 1,
        "false_negative": 1,
        "true_negative": 4,
    }
    print(
        json.dumps(
            {
                "scope": "synthetic_calibration_not_production_accuracy",
                "scenarios": rows,
                "counts": counts,
            },
            ensure_ascii=False,
        )
    )
