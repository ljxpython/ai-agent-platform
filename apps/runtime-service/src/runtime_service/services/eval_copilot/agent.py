"""Authoring Copilot graph for drafting and validating evaluation cases."""

from __future__ import annotations

import ast
import json
import operator
from typing import Any

from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from langgraph.pregel import Pregel

from runtime_service.runtime import AgentDefaults
from runtime_service.services.eval_shared import (
    build_eval_expert_graph,
    eval_internal_post,
)

SYSTEM_PROMPT = """你是平台评测出题专家（Eval Copilot），帮助用户基于业务场景或脱敏会话材料设计高质量评测用例（Case v3）。
规则：
1. 涉及金额、数量、百分比核算必须先调用 calculate 工具，禁止心算。
2. 需要查看现有评测集和草稿时，调用 fetch_suite_context 工具，不得编造不存在的用例。
3. 严禁把隐藏标准答案泄露到 turns 输入中；给出修改建议前调用 validate_case_draft 校验结构合法性。
4. 仅返回结构化建议，不直接发布题库或执行被测 Agent。"""

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def safe_calculate(expression: str) -> str:
    """Safely evaluate basic arithmetic expressions without eval()."""

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(node.op)](_eval(node.operand))
        raise ValueError("unsupported_expression")

    tree = ast.parse(expression.strip(), mode="eval")
    return str(round(_eval(tree.body), 6))


def validate_case_draft(draft_json: str) -> dict[str, Any]:
    """Validate candidate Case v3 JSON structure before returning to frontend Diff."""
    data = json.loads(draft_json)
    errors = []
    if not isinstance(data.get("case_key"), str) or not data["case_key"].strip():
        errors.append("case_key_required")
    if data.get("split", "dev") not in {"dev", "holdout"}:
        errors.append("invalid_split")
    if not data.get("turns") and not data.get("simulation"):
        errors.append("turns_or_simulation_required")
    if not isinstance(data.get("metrics"), list) or not data["metrics"]:
        errors.append("metrics_required")
    return {"valid": len(errors) == 0, "errors": errors}


def make_tools(facts: Any):
    @tool
    def calculate(expression: str) -> str:
        """Compute exact arithmetic values for rubric expectations."""
        return safe_calculate(expression)

    @tool
    def fetch_suite_context(suite_id: str) -> dict[str, Any]:
        """Read current suite metadata and existing draft cases from platform-api."""
        return eval_internal_post(
            "copilot-context",
            "/api/evaluation/internal/copilot-context",
            {"project_id": facts.principal.project_id, "suite_id": suite_id},
        )

    @tool
    def validate_case(draft_json: str) -> dict[str, Any]:
        """Validate candidate Case v3 JSON structure."""
        return validate_case_draft(draft_json)

    return [calculate, fetch_suite_context, validate_case]


DEFAULTS = AgentDefaults(
    model_id="deepseek:DeepSeek-V4-Flash",
    system_prompt=SYSTEM_PROMPT,
    prompt_version="eval-copilot-v1",
    optional_tool_names=("calculate", "fetch_suite_context", "validate_case"),
)


async def get_agent(config: RunnableConfig) -> Pregel:
    return await build_eval_expert_graph(
        config,
        graph_id="eval_copilot",
        defaults=DEFAULTS,
        tools_factory=make_tools,
    )
