"""Direct DeepEval metrics adapter without MLflow scorer wrappers."""

from __future__ import annotations

from eval_runner.domain.contracts import Case, Evidence, MetricResult
from eval_runner.scorers.judge import PlatformJudgeLLM

DEEPEVAL_METRICS = {
    "Faithfulness",
    "ContextualRecall",
    "ContextualPrecision",
    "ToolCorrectness",
    "BusinessFacts",
    "EvidenceBoundary",
    "RecommendationGrounding",
    "ConversationalGEval",
    "KnowledgeRetention",
    "StepEfficiency",
}


def evaluate_l2_deepeval(
    case: Case,
    evidence: Evidence,
    judge: PlatformJudgeLLM,
) -> list[MetricResult]:
    """Lazily import deepeval.metrics and run requested L2 semantic metrics."""
    requested = [m for m in case.metrics if m.name in DEEPEVAL_METRICS]
    if not requested:
        return []

    # Lazy import keeps eval-runner startup lightweight until L2 scoring runs.
    from deepeval.metrics import (
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        FaithfulnessMetric,
        GEval,
    )
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams

    results: list[MetricResult] = []
    user_input = "\n".join(t.content for t in case.turns) or "(dynamic simulation)"
    expected_output = str(case.expectations.get("expected_answer") or "")
    test_case = LLMTestCase(
        input=user_input,
        actual_output=evidence.final_answer,
        expected_output=expected_output or None,
        retrieval_context=evidence.retrieved_contexts or None,
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
            metric = FaithfulnessMetric(threshold=spec.threshold, model=judge)
        elif spec.name == "ContextualRecall":
            metric = ContextualRecallMetric(threshold=spec.threshold, model=judge)
        elif spec.name == "ContextualPrecision":
            metric = ContextualPrecisionMetric(threshold=spec.threshold, model=judge)
        else:
            criteria = spec.criteria or f"Evaluate {spec.name} strictly based on observed facts."
            metric = GEval(
                name=spec.name,
                criteria=criteria,
                evaluation_params=[
                    LLMTestCaseParams.INPUT,
                    LLMTestCaseParams.ACTUAL_OUTPUT,
                ],
                threshold=spec.threshold,
                model=judge,
            )

        metric.measure(test_case)
        score = float(getattr(metric, "score", 0.0) or 0.0)
        passed = bool(getattr(metric, "success", score >= spec.threshold))
        results.append(
            MetricResult(
                name=spec.name,
                layer="L2",
                passed=passed,
                score=round(score, 4),
                reason=str(getattr(metric, "reason", "") or ""),
            )
        )
    return results
