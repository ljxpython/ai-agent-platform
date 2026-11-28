"""Authoring Copilot graph with domain skills, material reader, trial-run, and graded HITL."""

from __future__ import annotations

import ast
import json
import operator
import re
from importlib.resources import files
from pathlib import Path
from typing import Any

from deepagents.graph import DeepAgentState
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import ToolException
from langgraph.pregel import Pregel

from runtime_service.runtime import AgentDefaults
from runtime_service.services.eval_shared import (
    build_eval_expert_graph,
    eval_internal_post,
)
from runtime_service.tools.documents import build_document_tools
from runtime_service.workspace.scoped import resolve_thread_workspace

SYSTEM_PROMPT = """你是平台评测出题专家（Eval Copilot），擅长把自然语言需求或参考资料（支持多份异构文件）转化为高精度、可执行、带白盒断言的评测用例（Case v3），并能在用户允许下进行试跑验证、失败排障修复或终止评测。

核心工作守则：
1. 【先学规范再出题】设计或修改复杂多轮/工具/代码/安全题前，先调用 list_authoring_skills 与 read_authoring_skill 读取对应领域指南，严禁凭空捏造 JSON 结构。
2. 【查清环境能力】设计 tool_constraints 前先调用 list_target_capabilities 查看目标 Graph 实际开放的工具名，绝不编造不存在的工具名；如需查看现有题库或历史题目，先调 list_project_suites / fetch_suite_context。
3. 【参考资料读取】当用户上传或提及参考文档时，先用 list_uploaded_materials / read_material_file 读取真实原文；涉及金额、比率、统计预期时，必须调 calculate 计算，禁止心算。
4. 【强校验兜底】任何写入草稿前务必先调用 validate_case 自检。非知识库检索题绝不能选择 Faithfulness/ContextualRecall/retrieved。turns[0].content 中严禁泄露答案或隐藏事实原文。
5. 【分级写库】新增不存在的题目（单次 <5 题）调 create_new_eval_cases 直接落库；修改/覆写已有 case_key 或批量 >=5 题必须调 update_existing_eval_cases（触发用户确认）。绝不擅自发布冻结版本。
6. 【授权试跑、防作弊修复与终止】
   - 想验证新题是否跑通时，先调 launch_trial_run（会先请用户一键批准，每次限 1~5 题）；返回 run_id 后提示用户进度并在结束/查询时调 get_run_progress_and_evidence 查明细；
   - 失败修复红线：必须区分“Case 写法问题（工具名/路径/格式过死/提示缺上下文）”与“被测 Agent 真缺陷（死循环/瞎猜/越权）”。只修复 Case 自身写法瑕疵，**严禁通过删除断言或放宽标准去洗白真实 Agent Bug**！
   - 若要停止评测，本会话发起的试跑调 cancel_own_trial_run，其他运行调 cancel_external_eval_run。
7. 【当轮直接行动与结构规范】只要用户需求已明确要求新增、修改草稿、发起试跑或终止任务，严禁只口头回复“我将要执行…”而不调工具，必须在当前回合直接发起对应工具调用！产物断言放在 expectations.artifacts（列表 `[{"path": "...", "kind": "contains", "expected": "..."}]`），工具约束放在 expectations.tool_constraints（`{"required": [...], "forbidden": [...]}`），受保护文件放入 turns[0].fixture 并在 metrics 中选 protected_unchanged。"""

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}

_KNOWN_METRICS = frozenset(
    {
        "completion",
        "answer_contains",
        "artifact_correct",
        "protected_unchanged",
        "approval",
        "cross_project_denied",
        "tool_constraints",
        "clarification_requested",
        "retrieved",
        "turn_expectations",
        "tool_budget",
        "no_write",
        "RefusalAssertion",
        "CounterfactualAssertion",
        "Faithfulness",
        "ContextualRecall",
        "ContextualPrecision",
        "ConversationalGEval",
        "KnowledgeRetention",
        "ToolCorrectness",
        "ArgumentCorrectness",
        "StepEfficiency",
        "EvidenceBoundary",
        "BusinessFacts",
        "RecommendationGrounding",
        "TaskCompletion",
    }
)
_USER_MODES = frozenset(
    {
        "cooperative",
        "terse",
        "impatient_reversal",
        "skeptical_challenger",
        "ambiguous_changer",
    }
)
_ARTIFACT_KINDS = frozenset(
    {"equals", "contains", "json_equals", "json_subset", "csv_rows", "absent"}
)
_INTERRUPT_KEYS = frozenset(
    {
        "clarification_mode",
        "plan_review_policy",
        "max_plan_rejections",
        "tool_approval_policy",
    }
)
_RAG_METRICS = frozenset(
    {"retrieved", "Faithfulness", "ContextualRecall", "ContextualPrecision"}
)
_GRAPH_KNOWN_TOOLS = {
    "dearflow_agent": {
        "request_plan_review",
        "update_plan",
        "ls",
        "read_file",
        "glob",
        "grep",
        "write_file",
        "edit_file",
        "execute",
        "background_execute",
        "background_task",
        "cancel_background_task",
        "search_memory",
        "manage_memory",
        "list_skills",
        "review_skill_package",
        "find_skills",
        "deploy_preview",
        "fetch_web_guidelines",
        "request_information",
        "present_artifacts",
        "parse_document",
        "search_web",
        "fetch_page",
        "github_query",
        "arxiv_search",
        "write_todos",
        "task",
        "generate_image",
        "edit_image",
        "get_media_task",
    },
    "showcase_demo": {
        "ls",
        "read_file",
        "write_file",
        "edit_file",
        "execute",
        "parse_document",
    },
    "reference_agent": {"search_knowledge"},
    "workflow_demo": set(),
}

_SKILLS_PKG = "runtime_service.services.eval_copilot"


def _skills_dir() -> Path:
    return Path(str(files(_SKILLS_PKG).joinpath("skills")))


def list_skill_topics() -> list[dict[str, str]]:
    root = _skills_dir()
    out: list[dict[str, str]] = []
    if not root.is_dir():
        return out
    for p in sorted(root.glob("*.md")):
        first_line = p.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
        out.append({"topic": p.stem, "title": first_line})
    return out


def read_skill_content(topic: str) -> str:
    clean = str(topic or "").strip().removesuffix(".md")
    if not clean or "/" in clean or "\\" in clean or ".." in clean:
        raise ToolException(f"invalid_skill_topic:{topic}")
    target = _skills_dir() / f"{clean}.md"
    if not target.is_file():
        available = ", ".join(item["topic"] for item in list_skill_topics())
        raise ToolException(f"skill_not_found:{clean}; available=[{available}]")
    return target.read_text(encoding="utf-8")[:12000]


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


def _coerce_case_json(draft_json: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(draft_json, dict):
        data = draft_json
    else:
        raw = str(draft_json or "").strip()
        m = re.match(r"^```(?:json)?\s*([\s\S]*?)```$", raw, flags=re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
        data = json.loads(raw)
    if (
        isinstance(data, dict)
        and "case" in data
        and isinstance(data["case"], dict)
        and "case_key" not in data
    ):
        data = data["case"]
    return data if isinstance(data, dict) else {}


def validate_case_draft(
    draft_json: str | dict[str, Any], *, graph_id: str = "dearflow_agent"
) -> dict[str, Any]:
    """Validate candidate Case v3 JSON structure plus anti-pitfall checks before saving."""
    try:
        data = _coerce_case_json(draft_json)
    except Exception as exc:  # noqa: BLE001
        return {"valid": False, "errors": [f"invalid_json:{exc}"]}
    errors: list[str] = []
    warnings: list[str] = []

    case_key = data.get("case_key")
    if not isinstance(case_key, str) or not case_key.strip():
        errors.append("case_key_required")
    elif not re.fullmatch(r"[a-zA-Z0-9_.-]{1,128}", case_key.strip()):
        errors.append(f"invalid_case_key_format:{case_key}")

    if data.get("split", "dev") not in {"dev", "holdout"}:
        errors.append("invalid_split")

    turns = data.get("turns") or []
    sim = data.get("simulation")
    if not turns and not sim:
        errors.append("turns_or_simulation_required")
    for idx, t in enumerate(turns):
        if not isinstance(t, dict):
            errors.append(f"turn_must_be_object:{idx}")
            continue
        role = str(t.get("role") or "user")
        if role not in {"user", "system"}:
            errors.append(
                f"invalid_turn_role:{idx}:{role}（turns[].role 仅允许 'user' 或 'system'）"
            )

    if isinstance(sim, dict):
        if not str(sim.get("goal") or "").strip():
            errors.append("simulation_goal_required")
        umode = str(sim.get("user_mode") or "cooperative")
        if umode not in _USER_MODES:
            errors.append(f"invalid_user_mode:{umode}")
        strat = sim.get("interrupt_strategy") or {}
        if isinstance(strat, dict):
            bad_strat = sorted(set(strat) - _INTERRUPT_KEYS)
            if bad_strat:
                errors.append(
                    f"unsupported_interrupt_strategy_keys:{','.join(bad_strat)}"
                )

    metrics_raw = data.get("metrics")
    metric_names: list[str] = []
    if not isinstance(metrics_raw, list) or not metrics_raw:
        errors.append("metrics_required")
    else:
        metric_names = [
            str(m.get("name") if isinstance(m, dict) else m).strip()
            for m in metrics_raw
            if (m.get("name") if isinstance(m, dict) else m)
        ]
        bad_metrics = [m for m in metric_names if m not in _KNOWN_METRICS]
        if bad_metrics:
            errors.append(f"unsupported_metrics:{','.join(bad_metrics)}")

    exp = data.get("expectations") if isinstance(data.get("expectations"), dict) else {}
    arts = exp.get("artifacts")
    has_non_absent_art = False
    if isinstance(arts, list):
        for idx, spec in enumerate(arts):
            if not isinstance(spec, dict) or not spec.get("path"):
                errors.append(f"artifact_path_required:{idx}")
                continue
            kind = str(spec.get("kind") or "contains")
            if kind not in _ARTIFACT_KINDS:
                errors.append(f"unsupported_artifact_kind:{kind}")
            if kind != "absent":
                has_non_absent_art = True

    tc = (
        exp.get("tool_constraints")
        if isinstance(exp.get("tool_constraints"), dict)
        else {}
    )
    allowed_tools = _GRAPH_KNOWN_TOOLS.get(graph_id, set())
    if tc and allowed_tools:
        declared: list[str] = []
        for k in ("required", "forbidden", "sequence"):
            vals = tc.get(k) or []
            if isinstance(vals, list):
                declared.extend(str(x) for x in vals if x)
        if isinstance(tc.get("arg_subsets"), dict):
            declared.extend(str(k) for k in tc["arg_subsets"])
        bad_tools = sorted(t for t in set(declared) if t not in allowed_tools)
        if bad_tools:
            errors.append(f"unknown_tools_for_{graph_id}:{','.join(bad_tools)}")

    declared_fixtures: set[str] = set()
    if isinstance(data.get("fixture"), dict):
        declared_fixtures.update(str(k) for k in data["fixture"])
    for t in turns:
        if isinstance(t, dict) and isinstance(t.get("fixture"), dict):
            declared_fixtures.update(str(k) for k in t["fixture"])
    if isinstance(sim, dict) and isinstance(sim.get("delayed_fixtures"), list):
        for entry in sim["delayed_fixtures"]:
            if isinstance(entry, dict) and isinstance(entry.get("files"), dict):
                declared_fixtures.update(str(k) for k in entry["files"])

    prompt_text = " ".join(
        [str(t.get("content") or "") for t in turns if isinstance(t, dict)]
        + ([str(sim.get("goal") or "")] if isinstance(sim, dict) else [])
    )
    placeholders = set(re.findall(r"\{\{([^{}]+)\}\}", prompt_text))
    missing_ph = sorted(p for p in placeholders if p not in declared_fixtures)
    if missing_ph:
        errors.append(f"undeclared_fixture_placeholders:{','.join(missing_ph)}")

    rag_selected = [m for m in metric_names if m in _RAG_METRICS]
    if rag_selected and graph_id != "reference_agent":
        if not any(
            w in prompt_text.lower()
            for w in ("rag", "知识库", "检索", "search_knowledge", "文档召回")
        ):
            errors.append(f"non_rag_case_with_rag_metrics:{','.join(rag_selected)}")

    if declared_fixtures and "protected_unchanged" not in metric_names:
        warnings.append("建议加上 protected_unchanged 保护初始测试夹具不被篡改。")
    if has_non_absent_art and "artifact_correct" not in metric_names:
        errors.append("期望了 artifacts 物理产物，必须勾选 artifact_correct。")
    if isinstance(sim, dict) and "ConversationalGEval" not in metric_names:
        warnings.append("开启了动态仿真，建议补充 ConversationalGEval。")

    res: dict[str, Any] = {"valid": len(errors) == 0, "errors": errors}
    if warnings:
        res["warnings"] = warnings
    return res


def _normalize_upload_path(file_path: str) -> str:
    raw = str(file_path or "").strip()
    if not raw or ".." in raw or raw.startswith("~"):
        raise ToolException("invalid_material_path")
    if raw.startswith("/workspace/uploads/"):
        return raw
    if raw.startswith("/workspace/"):
        raise ToolException("only_uploads_directory_allowed")
    return f"/workspace/uploads/{raw.lstrip('/')}"


def _build_hitl_middleware() -> HumanInTheLoopMiddleware:
    return HumanInTheLoopMiddleware(
        interrupt_on={
            "update_existing_eval_cases": {
                "allowed_decisions": ["approve", "reject"],
                "description": "此操作将修改/覆写题库已有用例（或批量 >=5 题写入草稿）。请确认是否允许保存。",
            },
            "launch_trial_run": {
                "allowed_decisions": ["approve", "reject"],
                "description": "此操作将在隔离靶场拉起真实定向试跑评测（限 <=5 题、单并发，会调用模型并计费）。请确认是否允许执行。",
            },
            "cancel_external_eval_run": {
                "allowed_decisions": ["approve", "reject"],
                "description": "此操作将终止非本对话发起的评测任务，请核对 Run ID 后决定是否终止。",
            },
        }
    )


def make_tools(facts: Any, config: RunnableConfig | None = None):
    configurable = (config or {}).get("configurable") or {}
    thread_id = str(configurable.get("thread_id") or "")
    workspace_root: Path | None = None
    doc_parser = None
    if thread_id:
        try:
            workspace_root = resolve_thread_workspace(
                facts.principal.tenant_id,
                facts.principal.project_id,
                thread_id,
                "eval_copilot",
            )
            doc_tools = build_document_tools(workspace_root)
            doc_parser = doc_tools[0] if doc_tools else None
        except Exception:  # noqa: BLE001
            workspace_root = None
            doc_parser = None

    def _safe_post(purpose: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return eval_internal_post(purpose, path, payload)
        except ToolException as exc:
            return {"ok": False, "error": str(exc)}

    @tool
    def list_authoring_skills() -> list[dict[str, str]]:
        """列出评测出题专用内置 Skill 指南目录，编写复杂多轮/工具/代码/安全题前可按需查看。"""
        return list_skill_topics()

    @tool
    def read_authoring_skill(topic: str) -> str:
        """按主题名读取内置出题 Skill 详细规范（如 case-v3-schema, multi-turn-simulation, metrics-and-anti-pitfalls, code-and-tool-scenarios）。"""
        try:
            return read_skill_content(topic)
        except ToolException as exc:
            return f"error: {exc}"

    @tool
    def list_uploaded_materials() -> dict[str, Any]:
        """列出当前出题会话上传至 /workspace/uploads/ 的所有参考资料文件名。"""
        if workspace_root is None:
            return {"files": [], "note": "当前会话无关联工作区"}
        uploads = workspace_root / "uploads"
        if not uploads.is_dir():
            return {"files": []}
        items = [
            f"/workspace/uploads/{p.name}"
            for p in sorted(uploads.iterdir())
            if p.is_file() and not p.name.startswith(".")
        ]
        return {"files": items}

    @tool
    async def read_material_file(
        file_path: str, query: str | None = None
    ) -> dict[str, Any]:
        """受控只读当前会话上传的参考资料（支持 .txt/.md/.csv/.json/.pdf/.docx），支持传纯文件名或 /workspace/uploads/ 路径。"""
        if doc_parser is None:
            return {"ok": False, "error": "material_workspace_unavailable"}
        try:
            norm = _normalize_upload_path(file_path)
            return await doc_parser.ainvoke({"file_path": norm, "query": query})
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    @tool
    def calculate(expression: str) -> str:
        """精确计算数学表达式（金额、百分比、行数校验前必调用，禁止心算）。"""
        try:
            return safe_calculate(expression)
        except Exception as exc:  # noqa: BLE001
            return f"calculate_error: {exc}"

    @tool
    def list_project_suites() -> dict[str, Any]:
        """查询当前项目下的全部可用评测集列表、题目数与最新冻结版本。"""
        return _safe_post(
            "copilot-suites",
            "/api/evaluation/internal/copilot-suites",
            {"project_id": facts.principal.project_id},
        )

    @tool
    def fetch_suite_context(
        suite_id: str, case_keys: list[str] | None = None
    ) -> dict[str, Any]:
        """查询指定评测集的元信息与已有用例草稿（可传 case_keys 精查指定题目）。"""
        return _safe_post(
            "copilot-context",
            "/api/evaluation/internal/copilot-context",
            {
                "project_id": facts.principal.project_id,
                "suite_id": suite_id,
                **({"case_keys": case_keys} if case_keys else {}),
            },
        )

    @tool
    def list_target_capabilities() -> dict[str, Any]:
        """查询平台可评测 Graph（如 dearflow_agent）的真实开放工具列表、特性支持及全部合法指标名。"""
        return _safe_post(
            "copilot-capabilities",
            "/api/evaluation/internal/copilot-capabilities",
            {"project_id": facts.principal.project_id},
        )

    @tool
    def fetch_recent_failures(
        suite_id: str | None = None, run_id: str | None = None
    ) -> dict[str, Any]:
        """查询近期打擂或试跑的失败用例摘要与未通过指标原因。"""
        return _safe_post(
            "copilot-failures",
            "/api/evaluation/internal/copilot-failures",
            {
                "project_id": facts.principal.project_id,
                **({"suite_id": suite_id} if suite_id else {}),
                **({"run_id": run_id} if run_id else {}),
            },
        )

    @tool
    def validate_case(
        draft_json: str | dict[str, Any], graph_id: str = "dearflow_agent"
    ) -> dict[str, Any]:
        """对单道 Case v3 草稿执行完整 Schema 与工程防呆检查（验证不通过时须自行修正）。"""
        return validate_case_draft(draft_json, graph_id=graph_id)

    @tool
    def create_new_eval_cases(
        suite_id: str, items: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """向题库草稿新增全新题目（严禁覆盖已有 case_key 且单次 <5 题；新增前请先调用 validate_case）。"""
        return _safe_post(
            "copilot-save-cases",
            "/api/evaluation/internal/copilot-save-cases",
            {
                "project_id": facts.principal.project_id,
                "suite_id": suite_id,
                "items": items,
                "mode": "create_only",
            },
        )

    @tool
    def update_existing_eval_cases(
        suite_id: str, items: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """修改/覆写已有题目草稿或批量保存 >=5 题（经人工确认卡批准后执行）。"""
        return _safe_post(
            "copilot-save-cases",
            "/api/evaluation/internal/copilot-save-cases",
            {
                "project_id": facts.principal.project_id,
                "suite_id": suite_id,
                "items": items,
                "mode": "upsert",
            },
        )

    @tool
    def launch_trial_run(
        suite_id: str,
        case_keys: list[str],
        target_project_id: str | None = None,
        agent_id: str | None = None,
        model_id: str | None = None,
        judge_model_id: str | None = None,
    ) -> dict[str, Any]:
        """在用户允许后发起定向试跑（单次限 1~5 题，立即返回 run_id 供追踪进度）。"""
        return _safe_post(
            "copilot-trial-run",
            "/api/evaluation/internal/copilot-trial-run",
            {
                "project_id": facts.principal.project_id,
                "actor_id": facts.principal.user_id,
                "suite_id": suite_id,
                "case_keys": case_keys,
                "target_project_id": target_project_id,
                "agent_id": agent_id,
                "model_id": model_id,
                "judge_model_id": judge_model_id,
                "copilot_thread_id": thread_id,
            },
        )

    @tool
    def get_run_progress_and_evidence(
        run_id: str, case_key: str | None = None
    ) -> dict[str, Any]:
        """查询试跑或打擂 Run 的实时状态、单题得分、白盒工具链、产物与失败依据。"""
        return _safe_post(
            "copilot-run-status",
            "/api/evaluation/internal/copilot-run-status",
            {
                "project_id": facts.principal.project_id,
                "run_id": run_id,
                **({"case_key": case_key} if case_key else {}),
            },
        )

    @tool
    def cancel_own_trial_run(run_id: str, action: str = "cancel") -> dict[str, Any]:
        """终止或暂停本出题对话自己发起的试跑任务（校验归属一致后免二次确认直接停表）。"""
        return _safe_post(
            "copilot-control-run",
            "/api/evaluation/internal/copilot-control-run",
            {
                "project_id": facts.principal.project_id,
                "run_id": run_id,
                "action": action,
                "copilot_thread_id": thread_id,
                "require_own": True,
            },
        )

    @tool
    def cancel_external_eval_run(run_id: str, action: str = "cancel") -> dict[str, Any]:
        """终止或暂停非本对话发起的其他评测任务（经人工确认卡批准后执行）。"""
        return _safe_post(
            "copilot-control-run",
            "/api/evaluation/internal/copilot-control-run",
            {
                "project_id": facts.principal.project_id,
                "run_id": run_id,
                "action": action,
                "copilot_thread_id": thread_id,
                "require_own": False,
            },
        )

    return [
        list_authoring_skills,
        read_authoring_skill,
        list_uploaded_materials,
        read_material_file,
        calculate,
        list_project_suites,
        fetch_suite_context,
        list_target_capabilities,
        fetch_recent_failures,
        validate_case,
        create_new_eval_cases,
        update_existing_eval_cases,
        launch_trial_run,
        get_run_progress_and_evidence,
        cancel_own_trial_run,
        cancel_external_eval_run,
    ]


DEFAULTS = AgentDefaults(
    model_id="deepseek:DeepSeek-V4-Flash",
    system_prompt=SYSTEM_PROMPT,
    prompt_version="eval-copilot-v2",
    optional_tool_names=(
        "list_authoring_skills",
        "read_authoring_skill",
        "list_uploaded_materials",
        "read_material_file",
        "calculate",
        "list_project_suites",
        "fetch_suite_context",
        "list_target_capabilities",
        "fetch_recent_failures",
        "validate_case",
        "create_new_eval_cases",
        "update_existing_eval_cases",
        "launch_trial_run",
        "get_run_progress_and_evidence",
        "cancel_own_trial_run",
        "cancel_external_eval_run",
    ),
)


async def get_agent(config: RunnableConfig) -> Pregel:
    return await build_eval_expert_graph(
        config,
        graph_id="eval_copilot",
        defaults=DEFAULTS,
        tools_factory=make_tools,
        extra_middleware=(_build_hitl_middleware(),),
        state_schema=DeepAgentState,
    )
