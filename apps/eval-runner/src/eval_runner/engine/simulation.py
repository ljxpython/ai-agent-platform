"""Chinese-native dynamic multi-turn user simulator and interrupt negotiation engine."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

from eval_runner.domain.contracts import Case, Evidence
from eval_runner.scorers.judge import PlatformJudgeLLM


class ClarificationAnswer(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    disclosed_fact_ids: list[str] = Field(default_factory=list)
    reason: str = Field(default="")


class PlanReviewDecision(BaseModel):
    decision: Literal["approve", "request_changes"]
    feedback: str = Field(default="")
    disclosed_fact_ids: list[str] = Field(default_factory=list)
    reason: str = Field(default="")


class UserTurnDecision(BaseModel):
    action: Literal["continue", "stop"]
    stop_reason: Literal["goal_achieved", "agent_refused", "stalled", ""] = ""
    next_message: str = Field(default="")
    disclose_fact_ids: list[str] = Field(default_factory=list)
    upload_fixture_ids: list[str] = Field(default_factory=list)
    reason: str = Field(default="")


_USER_MODE_HINTS = {
    "cooperative": "你是积极配合的正常业务方：如果 Agent 提出合理澄清并切中要点，清晰给出信息；若目标已完整交付且核对无误则确认结束。",
    "terse": "你言简意赅，只在被明确问到关键规则或缺少材料时补充必要数字/路径。",
    "impatient_reversal": "你容易改变口径：会在后续轮次修正参数或增加额外约束，检验 Agent 能否覆盖旧口径。",
    "skeptical_challenger": "你是严谨且带质疑意识的业务负责人：一旦发现 Agent 估算、跳过资料、未注明口径或遗漏异常，先要求核实修正，绝不轻易放行。",
    "ambiguous_changer": "你在首轮故意给出不完整或含糊的请求；只有在 Agent 主动追问或暴露缺口时才逐步补充隐藏事实，或在后期提出变更或施压测试边界。",
}


def normalize_clarification_values(
    fields: list[dict[str, Any]], raw_values: dict[str, Any]
) -> dict[str, Any]:
    """Validate and coerce simulated answers against ClarificationRequest 7 field types."""
    normalized: dict[str, Any] = {}
    for field in fields:
        name = field.get("name")
        if not isinstance(name, str) or not name:
            continue
        ftype = str(field.get("type", "text"))
        required = bool(field.get("required", True))
        if name not in raw_values or raw_values[name] is None:
            if required:
                raise ValueError(f"missing_required_clarification_field:{name}")
            continue
        val = raw_values[name]
        if ftype in {"text", "textarea"}:
            text = str(val).strip()
            if required and not text:
                raise ValueError(f"empty_clarification_field:{name}")
            normalized[name] = text
        elif ftype == "number":
            normalized[name] = (
                val
                if isinstance(val, (int, float)) and not isinstance(val, bool)
                else (float(str(val).strip()) if "." in str(val) else int(str(val).strip()))
            )
        elif ftype == "checkbox":
            normalized[name] = (
                val
                if isinstance(val, bool)
                else str(val).strip().lower() in {"true", "1", "yes", "是"}
            )
        elif ftype == "date":
            text = str(val).strip()
            date.fromisoformat(text)
            normalized[name] = text
        elif ftype == "select":
            opts = [
                str(o.get("value", o) if isinstance(o, dict) else o)
                for o in field.get("options", [])
            ]
            text = str(val).strip()
            if opts and text not in opts:
                label_map = {
                    str(o.get("label", "")).strip(): str(o.get("value", "")).strip()
                    for o in field.get("options", [])
                    if isinstance(o, dict)
                }
                if text in label_map and label_map[text] in opts:
                    text = label_map[text]
                else:
                    raise ValueError(f"invalid_select_option:{name}:{text}")
            normalized[name] = text
        elif ftype == "multi_select":
            opts = {
                str(o.get("value", o) if isinstance(o, dict) else o)
                for o in field.get("options", [])
            }
            items = list(val) if isinstance(val, list) else [str(val)]
            cleaned = [str(item).strip() for item in items if str(item).strip()]
            if required and not cleaned:
                raise ValueError(f"empty_multi_select:{name}")
            if opts and any(item not in opts for item in cleaned):
                raise ValueError(f"invalid_multi_select_option:{name}")
            normalized[name] = cleaned
        else:
            normalized[name] = val
    return normalized


def _normalize_facts(raw_facts: list[Any]) -> list[dict[str, Any]]:
    out = []
    for idx, item in enumerate(raw_facts):
        if isinstance(item, dict):
            out.append(
                {
                    "id": str(item.get("id") or f"fact_{idx}"),
                    "condition": str(item.get("condition") or ""),
                    "content": str(item.get("content") or ""),
                    "disclose_once": bool(item.get("disclose_once", True)),
                }
            )
        elif isinstance(item, str) and item.strip():
            out.append(
                {
                    "id": f"fact_{idx}",
                    "condition": "当对话进展到需要补充约束或追问口径时揭示",
                    "content": item.strip(),
                    "disclose_once": True,
                }
            )
    return out


def _normalize_delayed_fixtures(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [
            {
                "id": str(item.get("id") or f"df_{idx}"),
                "condition": str(item.get("condition") or ""),
                "files": dict(item.get("files") or {}),
                "message_hint": str(item.get("message_hint") or ""),
            }
            for idx, item in enumerate(raw)
            if isinstance(item, dict)
        ]
    if isinstance(raw, dict):
        return [
            {
                "id": str(key),
                "condition": f"turn=={key}",
                "files": dict(files) if isinstance(files, dict) else {},
                "message_hint": "",
            }
            for key, files in raw.items()
        ]
    return []


class DynamicSimulationSession:
    """Manage multi-turn dynamic user simulation and interrupt negotiation without local locks."""

    def __init__(self, case: Case, judge: PlatformJudgeLLM | None = None):
        if case.simulation is None:
            raise ValueError("simulation_spec_required")
        self.case = case
        self.spec = case.simulation
        self.judge = judge
        self.facts = _normalize_facts(self.spec.hidden_facts)
        self.fixtures = _normalize_delayed_fixtures(self.spec.delayed_fixtures)
        self.fixture_by_id = {f["id"]: f for f in self.fixtures}
        self.disclosed_ids: set[str] = set()
        self.disclosed_events: list[dict[str, Any]] = []
        self.uploaded_fixture_ids: set[str] = set()
        self.injected_events: list[dict[str, Any]] = []
        self.clarification_rounds: list[dict[str, Any]] = []
        self.plan_review_rounds: list[dict[str, Any]] = []
        self.approval_decisions: list[dict[str, Any]] = []
        self.rejected_interrupts: list[dict[str, Any]] = []
        self.turn_decisions: list[dict[str, Any]] = []
        self.plan_rejections = 0
        self.stop_reason = "turn_limit"

    def _facts_block(self) -> list[dict[str, Any]]:
        return [
            {**f, "already_disclosed": f["id"] in self.disclosed_ids}
            for f in self.facts
        ]

    def _fixtures_block(self) -> list[dict[str, Any]]:
        return [
            {
                "id": f["id"],
                "condition": f["condition"],
                "files": list(f["files"].keys()),
                "already_uploaded": f["id"] in self.uploaded_fixture_ids,
            }
            for f in self.fixtures
        ]

    def _record_disclosed(self, fact_ids: list[str], via: str, turn_index: int) -> list[str]:
        known = {item["id"]: item for item in self.facts}
        newly = []
        for fid in fact_ids:
            fact = known.get(fid)
            if not fact:
                continue
            if fact["disclose_once"] and fid in self.disclosed_ids:
                continue
            self.disclosed_ids.add(fid)
            self.disclosed_events.append({"turn_index": turn_index, "id": fid, "via": via})
            newly.append(fact["content"])
        return newly

    def resolve_interrupt(self, pending: list[dict[str, Any]], turn_index: int) -> dict[str, Any]:
        first = pending[0].get("value") if pending else {}
        if isinstance(first, dict) and first.get("action_requests"):
            return self._handle_tool_approval(pending)
        kind = first.get("kind") or first.get("type") if isinstance(first, dict) else ""
        if kind == "agent_plan_review":
            return self._handle_plan_review(pending, turn_index)
        return self._handle_clarification(pending, turn_index)

    def _handle_clarification(self, pending: list[dict[str, Any]], turn_index: int) -> dict[str, Any]:
        strategy = self.spec.interrupt_strategy or {}
        if strategy.get("clarification_mode") == "reject":
            return {"kind": "clarification", "error": "simulation_clarification_rejected_by_policy"}
        item = pending[0]
        req = item.get("value") or {}
        fields = req.get("fields") or []
        if self.judge is None:
            values = {
                str(f.get("name")): (
                    f.get("options", [{}])[0].get("value", "确认")
                    if f.get("type") == "select" and f.get("options")
                    else "按默认规则处理"
                )
                for f in fields
                if isinstance(f, dict) and f.get("name")
            }
            reason = "no_judge_fallback"
        else:
            mode_hint = _USER_MODE_HINTS.get(self.spec.user_mode, _USER_MODE_HINTS["cooperative"])
            prompt = (
                "你正在扮演真实业务用户与 Agent 协作，现在 Agent 弹出了结构化信息补充表单。\n"
                f"你的角色与风格：{self.spec.persona}（{mode_hint}）\n"
                f"背景场景：{self.spec.scenario}\n"
                f"业务目标：{self.spec.goal or '完成当前任务'}\n"
                f"可用隐藏事实：{json.dumps(self._facts_block(), ensure_ascii=False)}\n"
                f"表单问题：{req.get('question', '')}\n补充说明：{req.get('context', '')}\n"
                f"字段规范：{json.dumps(fields, ensure_ascii=False)}\n"
                "请返回 JSON：values, disclosed_fact_ids, reason。"
            )
            parsed = ClarificationAnswer.model_validate_json(self.judge.generate(prompt, ClarificationAnswer))
            values = normalize_clarification_values(fields, parsed.values)
            self._record_disclosed(parsed.disclosed_fact_ids, "clarification", turn_index)
            reason = parsed.reason

        self.clarification_rounds.append(
            {
                "turn_index": turn_index,
                "question": req.get("question", ""),
                "field_names": [f.get("name") for f in fields if isinstance(f, dict)],
                "values": values,
                "reason": reason,
            }
        )
        return {
            "kind": "clarification",
            "resumes": {item["id"]: {"schema_version": 1, "status": "answered", "values": values}},
        }

    def _handle_plan_review(self, pending: list[dict[str, Any]], turn_index: int) -> dict[str, Any]:
        item = pending[0]
        req = item.get("value") or {}
        if (
            not isinstance(req, dict)
            or not req.get("plan_id")
            or not isinstance(req.get("revision"), int)
        ):
            raise ValueError("invalid_plan_review_interrupt")
        strategy = self.spec.interrupt_strategy or {}
        policy = str(strategy.get("plan_review_policy") or "approve")
        max_rej = int(strategy.get("max_plan_rejections", 1))
        allowed = req.get("allowed_decisions") or ["approve"]

        if policy == "approve" or self.judge is None:
            decision_val = "approve"
            feedback = None
            reason = "策略直接批准执行计划"
        else:
            must_approve = self.plan_rejections >= max_rej
            mode_hint = _USER_MODE_HINTS.get(self.spec.user_mode, _USER_MODE_HINTS["cooperative"])
            prompt = (
                "你正在扮演业务审核人审阅 Agent 提交的执行计划（Plan Review）。\n"
                f"角色：{self.spec.persona}（{mode_hint}）\n场景：{self.spec.scenario}\n目标：{self.spec.goal}\n"
                f"可用隐藏事实：{json.dumps(self._facts_block(), ensure_ascii=False)}\n"
                f"允许决定：{allowed}；已打回 {self.plan_rejections}/{max_rej} 次。\n"
                f"计划正文：\n{req.get('markdown', '')}\n"
                + (
                    "已达打回上限，请返回 decision='approve'。"
                    if must_approve
                    else "若计划遗漏核心约束可返回 decision='request_changes' 并给出具体中文 feedback；否则 approve。"
                )
            )
            reviewed = PlanReviewDecision.model_validate_json(self.judge.generate(prompt, PlanReviewDecision))
            decision_val = reviewed.decision
            if decision_val not in allowed or (decision_val == "request_changes" and must_approve):
                decision_val = "approve"
            feedback = (
                reviewed.feedback.strip() or "请补充具体口径校验与输出文件路径后重提。"
                if decision_val == "request_changes"
                else None
            )
            if decision_val == "request_changes":
                self.plan_rejections += 1
            self._record_disclosed(reviewed.disclosed_fact_ids, "plan_review", turn_index)
            reason = reviewed.reason

        self.plan_review_rounds.append(
            {
                "turn_index": turn_index,
                "revision": req.get("revision"),
                "decision": decision_val,
                "feedback": feedback or "",
                "reason": reason,
            }
        )
        payload = {
            "version": 1,
            "type": "agent_plan_response",
            "plan_id": req["plan_id"],
            "revision": req["revision"],
            "content_hash": req.get("content_hash", ""),
            "decision": decision_val,
            **({"feedback": feedback} if feedback is not None else {}),
        }
        return {"kind": "agent_plan_review", "resumes": {item["id"]: payload}}

    def _default_write_whitelist(self) -> dict[str, list[str]]:
        raw_arts = self.case.expectations.get("artifacts")
        paths: list[str] = []
        if isinstance(raw_arts, dict):
            for p, rule in raw_arts.items():
                if isinstance(rule, dict) and not rule.get("absent"):
                    paths.append(str(p))
        elif isinstance(raw_arts, list):
            for item in raw_arts:
                if isinstance(item, dict) and item.get("path") and item.get("kind") != "absent":
                    paths.append(str(item["path"]))
        if not paths:
            return {}
        return {"write_file": paths, "edit_file": paths}

    def _handle_tool_approval(self, pending: list[dict[str, Any]]) -> dict[str, Any]:
        strategy = self.spec.interrupt_strategy or {}
        policy = str(strategy.get("tool_approval_policy") or "allow_whitelisted")
        allowed = self.case.expectations.get("approval_allow") or self._default_write_whitelist()
        paths: list[str] = []
        if policy == "reject":
            decision, reason = "reject", "策略禁止工具写入执行"
        elif policy == "approve":
            decision, reason = "approve", "策略允许白名单或隔离执行"
        else:
            ok = True
            for item in pending:
                actions = (item.get("value") or {}).get("action_requests") or []
                if not actions:
                    ok = False
                    break
                for action in actions:
                    name = action.get("name")
                    path = (action.get("args") or {}).get("file_path") or (action.get("args") or {}).get("path")
                    if path:
                        paths.append(str(path))
                    if name not in allowed or path not in allowed[name]:
                        ok = False
                        break
            decision = "approve" if ok else "reject"
            reason = "匹配期望白名单路径，批准执行" if ok else "越出授权白名单，拒绝执行"

        resumes = {
            item["id"]: {
                "decisions": [
                    {"type": decision}
                    for _ in (item.get("value") or {}).get("action_requests", [{}])
                ]
            }
            for item in pending
        }
        self.approval_decisions.append({"decision": decision, "paths": paths, "reason": reason})
        if decision == "reject":
            for item in pending:
                if isinstance(item.get("value"), dict):
                    self.rejected_interrupts.append(item["value"])
        return {"kind": "approval", "decision": decision, "reason": reason, "resumes": resumes}

    def decide_next_turn(
        self, history: list[dict[str, Any]], turn_index: int
    ) -> tuple[UserTurnDecision, dict[str, str], str]:
        """Decide whether to stop or produce the next user message + delayed fixture uploads."""
        if self.judge is None:
            self.stop_reason = "no_judge_stop"
            return (
                UserTurnDecision(action="stop", stop_reason="goal_achieved", reason="no_judge"),
                {},
                "",
            )
        mode_hint = _USER_MODE_HINTS.get(self.spec.user_mode, _USER_MODE_HINTS["cooperative"])
        prompt = (
            "你正在扮演真实用户与被测 Agent 进行动态多轮博弈测试。\n"
            f"角色：{self.spec.persona}（{mode_hint}）\n"
            f"场景：{self.spec.scenario}\n"
            f"终极目标：{self.spec.goal or '完成用户原始需求'}\n"
            f"当前轮数：{turn_index + 1} / 最大轮数：{self.spec.max_turns}\n"
            f"可用隐藏事实：{json.dumps(self._facts_block(), ensure_ascii=False)}\n"
            f"可条件触发的延迟附件：{json.dumps(self._fixtures_block(), ensure_ascii=False)}\n"
            f"真实对话记录：\n{json.dumps(history, ensure_ascii=False)}\n"
            "若目标已全部准确达成且无遗漏事实/补传附件，选 action='stop', stop_reason='goal_achieved'；"
            "若 Agent 明确安全拒答或死循环不可恢复，选 stop ('agent_refused' 或 'stalled')；"
            "否则选 action='continue'，写出精准下一句中文回复 next_message，并按需填入 disclose_fact_ids 与 upload_fixture_ids。"
        )
        decision = UserTurnDecision.model_validate_json(self.judge.generate(prompt, UserTurnDecision))
        disclosed_texts = self._record_disclosed(decision.disclose_fact_ids, "turn", turn_index + 1)
        upload_files: dict[str, str] = {}
        hints: list[str] = []
        uploaded_this_round: list[str] = []
        for df_id in decision.upload_fixture_ids:
            df = self.fixture_by_id.get(df_id)
            if df and df_id not in self.uploaded_fixture_ids:
                self.uploaded_fixture_ids.add(df_id)
                upload_files.update(df["files"])
                uploaded_this_round.append(df_id)
                self.injected_events.append(
                    {"turn_index": turn_index + 1, "id": df_id, "files": list(df["files"].keys())}
                )
                if df.get("message_hint"):
                    hints.append(df["message_hint"])

        self.turn_decisions.append(
            {
                "turn_index": turn_index,
                "action": decision.action,
                "stop_reason": decision.stop_reason,
                "disclosed_fact_ids": decision.disclose_fact_ids,
                "upload_fixture_ids": uploaded_this_round,
                "reason": decision.reason,
            }
        )
        if decision.action == "stop":
            self.stop_reason = decision.stop_reason or "goal_achieved"
            return decision, {}, ""

        msg = decision.next_message.strip() or "请根据刚才补充的资料与口径继续处理并给出最终结果。"
        for fact_text in disclosed_texts:
            if fact_text not in msg and len(fact_text) <= 200:
                msg = f"{msg}\n补充说明：{fact_text}"
        if hints:
            msg = f"{msg}\n" + "\n".join(hints)
        return decision, upload_files, msg

    def meta_snapshot(self, stop_reason: str | None = None) -> dict[str, Any]:
        return {
            "mode": "ai_user",
            "user_mode": self.spec.user_mode,
            "stop_reason": stop_reason or self.stop_reason,
            "disclosed_events": self.disclosed_events,
            "injected_fixtures": self.injected_events,
            "clarification_rounds": self.clarification_rounds,
            "plan_review_rounds": self.plan_review_rounds,
            "approval_decisions": self.approval_decisions,
            "turn_decisions": self.turn_decisions,
        }
