"""Diagnostic Expert graph with bounded paginated evidence reading and 3-layer RCA Gap."""

from __future__ import annotations

from typing import Any

from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from langgraph.pregel import Pregel

from runtime_service.runtime import AgentDefaults
from runtime_service.services.eval_shared import (
    build_eval_expert_graph,
    eval_internal_post,
)

SYSTEM_PROMPT = """你是平台独立评测诊断专家（Eval Diagnosis Expert），依据真实运行证据用中文解释评测结果并给出可执行改进建议。
规则：
1. 你不能修改题库、不能改分或重新运行被测 Agent。
2. 必须先调用 read_evidence 读取 overview 或 list_cases，下结论必须引用工具返回过的精确 reference（如 overview、case:c1、case:c1@14000）。
3. 严格区分故障与业务未达标：infra_error（运行时故障/流超时/裁判报错）与业务失败分开归因；业务失败必须按三层 Gap 归因：
   - data_gap（数据源缺失）
   - retrieval_gap（检索召回或排序不足）
   - reasoning_gap（工具选择/参数提取/推理规划偏离或死循环）
4. 证据不足时诚实说明边界并建议补采，不得凭空猜测。"""


def make_tools(facts: Any):
    @tool
    def read_evidence(
        run_id: str, ref: str = "overview", offset: int = 0
    ) -> dict[str, Any]:
        """Read paginated run evidence (overview, list_cases, or case:<case_key>)."""
        return eval_internal_post(
            "diagnosis-evidence",
            "/api/evaluation/internal/diagnosis-evidence",
            {
                "project_id": facts.principal.project_id,
                "run_id": run_id,
                "ref": ref,
                "offset": offset,
            },
        )

    return [read_evidence]


DEFAULTS = AgentDefaults(
    model_id="deepseek:DeepSeek-V4-Flash",
    system_prompt=SYSTEM_PROMPT,
    prompt_version="eval-diagnosis-v1",
    optional_tool_names=("read_evidence",),
)


async def get_agent(config: RunnableConfig) -> Pregel:
    return await build_eval_expert_graph(
        config,
        graph_id="eval_diagnosis",
        defaults=DEFAULTS,
        tools_factory=make_tools,
    )
