# 异常与取消调用零成本兜底（防止网关财务状态受阻）

**日期**：2026-11-23
**服务**：`runtime-service`
**类型**：`fix`

## 背景与问题

在网关预算与财务熔断治理（Gateway Budget Governance）体系下，当大模型网络调用失败（如代理 502/504、连接超时、鉴权失败等）且供应商未返回用量数据时（`quality == 'missing'`），底层 `estimate_usage_cost()` 之前会直接将该调用的估算费用设为 `None`（SQL 层面为 `NULL`）。

在极端审慎的风控审计逻辑下，账本检测到周期内存在金额未决（`amount IS NULL`）的已终结调用时，会将整个预算周期的状态判定为 `accounting_status = "unverifiable"`（账务状态受阻），导致前端显示警告斜纹进度条，且在硬阻断（`REJECT`）策略下会直接阻断后续所有合法的新增模型调用。

## 改动内容

1. **零成本失败调用判定与兜底（`apps/runtime-service/src/runtime_service/observability/usage.py`）**：
   - 在 `estimate_usage_cost(usage, pricing, outcome=None)` 中补充对失败与取消调用的语义识别：当 `outcome in {"failed", "cancelled"}` 且 `usage["quality"] == "missing"` 时，明确返回费用为 `"0.000000000000"`，原因为 `"zero_cost_on_failure"`；
   - 成功调用（`completed`）若缺失用量，仍保持严格审计返回 `None`（`missing_or_invalid_usage`）；
   - 在 `RuntimeUsageCallback._finish_call` 中传递 `outcome` 参数，确保模型报错时不再写入 `estimated_cost_usd = NULL`。

2. **数据库仓储层对齐（`apps/runtime-service/src/runtime_service/db/repositories/usage.py`）**：
   - 在 `_upsert_call` 重新计价重试时，同样透传 `outcome=call.get("outcome")`，避免重试时覆盖为 `NULL`。

3. **单测覆盖（`apps/runtime-service/tests/observability/test_usage.py`）**：
   - 增加 `test_failed_or_cancelled_call_with_missing_usage_defaults_to_zero_cost` 与 `test_usage_callback_on_llm_error_records_zero_cost_on_missing_response` 两项针对性测试。

## 验证结果

- **测试套件**：`apps/runtime-service/tests/observability/test_usage.py` 与 `test_usage_lifecycle.py` 共 31 项测试 100% 通过（31 passed）；
- **文档规范检查**：通过 `python scripts/check_docs.py` 校验，无绝对路径违规。
