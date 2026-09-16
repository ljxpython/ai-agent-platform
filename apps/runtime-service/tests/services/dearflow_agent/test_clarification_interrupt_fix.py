import pytest
from uuid import uuid4
from langgraph.errors import GraphBubbleUp, GraphInterrupt
from langgraph.pregel._tools import StreamToolCallHandler
from runtime_service.services.dearflow_agent.schemas import (
    ClarificationRequest,
    ClarificationField,
    Option,
)


def test_clarification_schema_allows_extra_fields():
    # LLM typically includes "type": "select" inside options and extra description
    raw = {
        "question": "请补充背景信息",
        "context": "方案设计",
        "fields": [
            {
                "name": "delivery_format",
                "label": "交付形式",
                "type": "select",
                "required": True,
                "description": "辅助说明字段",
                "options": [
                    {"value": "md", "label": "Markdown文档", "type": "select", "extra_meta": 123},
                    {"value": "doc", "label": "Word文档", "type": "select"},
                ],
            }
        ],
    }
    req = ClarificationRequest.model_validate(raw)
    assert req.question == "请补充背景信息"
    assert len(req.fields) == 1
    assert len(req.fields[0].options) == 2
    assert req.fields[0].options[0].value == "md"


def test_stream_tool_call_handler_ignores_graph_bubble_up():
    emitted = []

    def mock_stream(chunk):
        emitted.append(chunk)

    handler = StreamToolCallHandler(mock_stream, subgraphs=True)
    run_id = uuid4()
    handler._start(
        {"name": "request_information"},
        "input",
        run_id=run_id,
        metadata={"langgraph_checkpoint_ns": "tools:1"},
        tags=[],
        inputs={},
        kwargs={"tool_call_id": "call-clarification-1"},
    )
    assert len(emitted) == 1
    assert emitted[0][2]["event"] == "tool-started"

    # Interrupt should not emit tool-error
    class MockInterrupt(GraphBubbleUp):
        pass

    handler._error(MockInterrupt("interrupted"), run_id=run_id)
    # Event count must remain 1 (no tool-error emitted)
    assert len(emitted) == 1


def test_clarification_schema_tolerates_missing_value_or_string_options():
    # 模拟真实大模型：只传 label，不传 value；或 options 中直接传字符串；或 options 出现重复
    raw = {
        "question": "请确认支付需求",
        "fields": [
            {
                "name": "payment_methods",
                "label": "支持的支付方式",
                "type": "multi_select",
                "options": [
                    {"description": "", "label": "支付宝"},
                    {"description": "", "label": "微信支付"},
                    {"description": "", "label": "银联/银行卡"},
                    "Apple Pay",
                    {"description": "", "label": "支付宝"},  # 重复项
                ],
            }
        ],
    }
    req = ClarificationRequest.model_validate(raw)
    opts = req.fields[0].options
    assert len(opts) == 4  # 重复项已去重
    assert opts[0].value == "支付宝" and opts[0].label == "支付宝"
    assert opts[1].value == "微信支付" and opts[1].label == "微信支付"
    assert opts[2].value == "银联/银行卡" and opts[2].label == "银联/银行卡"
    assert opts[3].value == "Apple Pay" and opts[3].label == "Apple Pay"

