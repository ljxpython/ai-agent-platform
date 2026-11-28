"""Direct DeepEval metrics adapter with whitebox evidence context and 4-tier CoT rubrics."""

from __future__ import annotations

import json
from typing import Any

from eval_runner.domain.contracts import Case, Evidence, MetricResult
from eval_runner.scorers.judge import PlatformJudgeLLM

DEEPEVAL_METRICS = {
    "Faithfulness",
    "ContextualRecall",
    "ContextualPrecision",
    "ToolCorrectness",
    "ArgumentCorrectness",
    "BusinessFacts",
    "EvidenceBoundary",
    "RecommendationGrounding",
    "ConversationalGEval",
    "KnowledgeRetention",
    "StepEfficiency",
}

_FOUR_TIER_ANCHOR = (
    "\n[评分标尺 4-Tier Rubrics (0.0~1.0)]\n"
    "- 0.0~0.2 严重错误/越权/幻觉捏造/违背约束\n"
    "- 0.3~0.6 不及格/关键细节缺失/绕路或未遵循后续纠正\n"
    "- 0.7~0.8 基本达标，结论与依据一致但遗漏非核心次要细节\n"
    "- 0.9~1.0 完美对齐证据、工具与全部业务规则\n"
    "要求 CoT-first：先列出具体观察到的事实与缺陷条目，再给出最终分数。"
)


def _format_transcript(evidence: Evidence) -> str:
    turns = (evidence.checks or {}).get("transcript") or []
    if not turns and evidence.messages:
        turns = [
            {
                "role": m.get("role", m.get("type")),
                "content": str(m.get("content") or "")[:1000],
            }
            for m in evidence.messages
            if isinstance(m, dict)
        ]
    if not turns:
        return ""
    lines = []
    for idx, item in enumerate(turns[:20], 1):
        role = item.get("role", "unknown")
        content = str(item.get("content") or "")[:800]
        lines.append(f"[{idx}] {role}: {content}")
    return "\n".join(lines)


def _format_tool_trace(evidence: Evidence) -> str:
    if not evidence.tool_events:
        return "无工具调用事件。"
    compact = [
        {
            "name": e.get("name"),
            "status": e.get("status"),
            "args": e.get("args"),
            "output_preview": str(e.get("output_preview") or "")[:300],
        }
        for e in evidence.tool_events[:30]
    ]
    return json.dumps(compact, ensure_ascii=False)


def _build_criteria(spec_name: str, base_criteria: str, case: Case, evidence: Evidence) -> str:
    parts = [base_criteria or f"Evaluate {spec_name} strictly based on observed facts."]
    if case.business_rules:
        parts.append("核心业务规则：\n- " + "\n- ".join(case.business_rules[:8]))
    rubric = case.expectations.get("rubric")
    if isinstance(rubric, str) and rubric.strip():
        parts.append(f"标准验收参考：{rubric.strip()}")
    if spec_name in {"ToolCorrectness", "ArgumentCorrectness", "StepEfficiency"}:
        executed_count = sum(1 for e in evidence.tool_events if e.get("status") == "executed")
        parts.append(f"真实工具执行总次数={executed_count}，工具序列：\n{_format_tool_trace(evidence)}")
    if spec_name in {"ConversationalGEval", "KnowledgeRetention"}:
        tr = _format_transcript(evidence)
        if tr:
            parts.append(f"完整多轮对话与中断轨迹：\n{tr}")
    parts.append(_FOUR_TIER_ANCHOR)
    return "\n\n".join(parts)


def evaluate_l2_deepeval(
    case: Case,
    evidence: Evidence,
    judge: PlatformJudgeLLM,
) -> list[MetricResult]:
    """Lazily import deepeval.metrics and run requested L2 semantic metrics with whitebox context."""
    requested = [m for m in case.metrics if m.name in DEEPEVAL_METRICS]
    if not requested:
        return []

    from deepeval.metrics import (
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        FaithfulnessMetric,
        GEval,
    )
    from deepeval.models import DeepEvalBaseLLM
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams

    class _PlatformDeepEvalModel(DeepEvalBaseLLM):
        """Bridge PlatformJudgeLLM to DeepEvalBaseLLM with Pydantic schema support."""

        def __init__(self, inner: PlatformJudgeLLM):
            self._inner = inner
            super().__init__(model=inner.get_model_name())

        def load_model(self):
            return self._inner

        def get_model_name(self) -> str:
            return self._inner.get_model_name()

        def generate(self, prompt: str, schema: Any = None) -> Any:
            raw = self._inner.generate(prompt, schema=schema)
            if schema is not None and hasattr(schema, "model_validate_json"):
                return schema.model_validate_json(raw)
            return raw

        async def a_generate(self, prompt: str, schema: Any = None) -> Any:
            raw = await self._inner.a_generate(prompt, schema=schema)
            if schema is not None and hasattr(schema, "model_validate_json"):
                return schema.model_validate_json(raw)
            return raw

    judge_model = _PlatformDeepEvalModel(judge)

    results: list[MetricResult] = []
    transcript_text = _format_transcript(evidence)
    user_input = transcript_text or "\n".join(t.content for t in case.turns) or "(dynamic simulation)"
    expected_output = str(
        case.expectations.get("expected_answer")
        or case.expectations.get("rubric")
        or ""
    )

    whitebox_context = list(evidence.retrieved_contexts)
    if evidence.tool_events:
        whitebox_context.append(f"[工具轨迹]\n{_format_tool_trace(evidence)}")
    if evidence.artifacts:
        summary_arts = {k: v[:600] for k, v in list(evidence.artifacts.items())[:8]}
        whitebox_context.append(f"[工作区产物]\n{json.dumps(summary_arts, ensure_ascii=False)}")

    test_case = LLMTestCase(
        input=user_input,
        actual_output=evidence.final_answer,
        expected_output=expected_output or None,
        retrieval_context=evidence.retrieved_contexts or None,
        context=whitebox_context or None,
    )

    for spec in requested:
        if spec.name in {"Faithfulness", "ContextualRecall", "ContextualPrecision"} and (
            evidence.contexts_state != "recorded" or not evidence.retrieved_contexts
        ):
            results.append(
                MetricResult(
                    name=spec.name,
                    layer="L2",
                    passed=False,
                    score=0.0,
                    reason=f"contexts_unavailable:{evidence.contexts_state}",
                )
            )
            continue

        if spec.name == "Faithfulness":
            metric = FaithfulnessMetric(threshold=spec.threshold, model=judge_model)
        elif spec.name == "ContextualRecall":
            metric = ContextualRecallMetric(threshold=spec.threshold, model=judge_model)
        elif spec.name == "ContextualPrecision":
            metric = ContextualPrecisionMetric(threshold=spec.threshold, model=judge_model)
        else:
            criteria = _build_criteria(spec.name, spec.criteria, case, evidence)
            eval_params = [
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ]
            if expected_output:
                eval_params.append(LLMTestCaseParams.EXPECTED_OUTPUT)
            if whitebox_context:
                eval_params.append(LLMTestCaseParams.CONTEXT)
            metric = GEval(
                name=spec.name,
                criteria=criteria,
                evaluation_params=eval_params,
                threshold=spec.threshold,
                model=judge_model,
            )

        metric.measure(test_case)
        score = float(getattr(metric, "score", 0.0) or 0.0)
        reason = str(getattr(metric, "reason", "") or "")
        if spec.params.get("position_swap") and whitebox_context and len(whitebox_context) > 1:
            swapped_case = LLMTestCase(
                input=user_input,
                actual_output=evidence.final_answer,
                expected_output=expected_output or None,
                retrieval_context=list(reversed(evidence.retrieved_contexts)) or None,
                context=list(reversed(whitebox_context)),
            )
            metric.measure(swapped_case)
            score_swapped = float(getattr(metric, "score", 0.0) or 0.0)
            score = round((score + score_swapped) / 2.0, 4)
            reason = f"{reason} [PositionSwap={score_swapped:.2f}]"
        passed = bool(score >= spec.threshold)
        results.append(
            MetricResult(
                name=spec.name,
                layer="L2",
                passed=passed,
                score=round(score, 4),
                reason=reason,
            )
        )
    return results
