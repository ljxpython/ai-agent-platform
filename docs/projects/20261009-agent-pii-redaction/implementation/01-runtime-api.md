# F05 Runtime/API 实施记录

日期：2026-10-09。相关任务：T01–T07、V01。状态和验收以 tasks/verification 为准。

## 检测与策略

新增 `apps/runtime-service/src/runtime_service/runtime/pii.py`。`PiiRedactionConfig` 为不可变部署策略，拒绝错误类型、未知/重复 detector、启用缺密钥。`pii_config_for_facts()` 从现有验证身份取得 tenant/project/thread，不接受浏览器政策。

`redact_text()` 复用标准库 regex/HMAC/JSON；固定 email → api_key → national_id → credit_card → phone，身份证使用 mod-11/日期，卡号使用 Luhn。规范 JSON 加算法版本、category、scope 和完整匹配值；HMAC-SHA256 前 128 位按低位先行固定 27 位 base26 编码，无映射存储。

三份 Runtime `.env.example` 新增 `RUNTIME_PII_REDACTION_ENABLED`、`RUNTIME_PII_TOKEN_SECRET`、`RUNTIME_PII_DETECTORS`；默认关闭。没有新依赖、数据库表或政策 CRUD。

## 模型和摘要

新增 `apps/runtime-service/src/runtime_service/middlewares/pii_redaction.py`：`PiiRedactionMiddleware` 只将投影副本交给 handler。`redact_model_request()` 覆盖 messages/system、历史工具参数重复表示、工具说明/schema 文本，保留原 state、工具执行事实、artifact 和媒体二进制。

四组合根 `services/{reference_agent,dearflow_agent,demo/workflow_demo,demo/showcase_demo}/agent.py` 装配同一受信策略；声明式子图显式继承。wrapper 位于动态注入后、容量校验前。

`PiiSummarizationMiddleware` 继承官方摘要，仅补摘要输入先投影、敏感大参数保持完整再投影、溢出尾部保护；`name=SummarizationMiddleware` 替换默认，而不是叠加。

`middlewares/conversation_offloading.py` 继承受保护摘要，自动/手动整理保留既有预算、状态和归档。`middlewares/model_resilience.py` 采用相同摘要输入保护。

主备验证发现两个 DeepAgent 组合根的普通 retry 层先包装 Provider 异常，阻止外层恢复；改为：

```python
RuntimeModelRetryMiddleware(metadata, delegated=child or bundle.policy.enabled)
```

Showcase 同样使用 `readonly or bundle.policy.enabled`；关闭恢复策略时保持原普通重试。既有恢复组件继续负责调用预算、部分输出和备用模型。

## 辅助入口

- `utils/title_summarizer.py`：完整内容先保护再截断，保护模式失败返回“新对话”，输出含 PII 或 token 同样回退；异常只记录类型。
- `http/title_summary.py` 与 API `modules/runtime_gateway/application/service.py::summarize_thread_title()`：现有 Thread-edit 委托绑定标题作用域。
- `services/suggestions.py`：输入/输出共享保护，失效返回空列表。
- `tools/images.py`、`middlewares/images.py`、DearFlow `tools/media.py`：视觉问题保护，原媒体字节不变。
- DearFlow `middleware/memory.py`：`safe_source_text()` 对完整来源及连续 blocks 检查，命中来源跳过自动提取；候选输出再检查，保留 source/quote、作者、epoch/CAS 和原终态。人工记忆管理未改。

## 错误与边界

`runtime/errors.py::RuntimePrivacyError` 沿既有执行错误传播，仅带 `runtime.privacy.redaction_failed`。`middlewares/model_errors.py` 不把它计为 Provider 故障。API `adapters/langgraph/sdk_client.py` 精确投影；HTTP 来源 500 → 502，已建流继续使用原生 lifecycle/tasks/error。

Runtime `runtime/resolver.py` 和 API `core/runtime_contract.py` 拒绝 PII 私有字段注入，API 公开出口剥离这些字段。Runtime `webapp.py` 的 HTTP 隐私错误使用同一固定中文文案，并补 `tests/http/test_pii_error.py` 验证。Langfuse 生产代码没有新增第二套保护；本地真实 OTLP 收包验证既有正文删除。

未知可发送块、无法安全改写的签名/加密 reasoning、含敏感值的远程媒体 URL 或 schema 结构约束阻断；普通媒体引用保留。收包核对发现 schema `properties/$defs/definitions` 名称与媒体字典 key 的扫描缺口，已在唯一算法模块补阻断和四项回归，不改工具参数名。ContextOverflow 后大型敏感工具尾部阻断官方有损裁剪恢复，避免半个标识符漏检。该限制写入运行规范和交接。

历史 `invalid_tool_calls` 改为复用 `_tool_call()`，保护 malformed args 文本并阻断敏感 name/id；所有内容块先检查顶层 key。修复前 name/id 两条回归确实未阻断，修复后中间件 21 项、三协议 HTTP 收包 5 项通过，原工具契约与执行事实保持。

## 隔离链路与测试修正

真实 PG/inbox 验证敏感完整来源不进入提取、无命中本人来源发送一次，其他作者隔离，原文 quote 校验继续有效。完整扫描后恢复 inbox 原有 6000 字截断，避免无命中的长来源在聚合预算阶段被整条跳过；新增开启/关闭 × 敏感尾部/正常尾部四项回归，修复前 3 failed/1 passed，修复后记忆相关 29 项通过。正式 API/Worker 链路验证主子图、未知 block 零外发、approve/edit/reject、同 key 重启、同 Thread 密钥轮换及关闭后重启回退；事实记录见 verification。

Provider fixture 每次生成唯一 tool-call ID，避免旧 checkpoint 回执覆盖；HITL 恢复请求去掉既有契约禁止覆盖的 `version/stream_mode`。旧取消测试保留 Worker 实际注入的 `__graphharbor_run_budget`，不再用静态测试预算覆盖受信运行事实。繁忙主机冷构图超过旧 15 秒测试窗口，准备窗口改为 60 秒、外层九用例上限改为 360 秒后全部通过；仍保持取消清理原有 5 秒断言，不改生产超时或取消语义。

新增测试位于 Runtime `tests/{runtime,middlewares,services,integration,observability}/test_pii*.py`、`tests/fixtures/pii_redaction_platform.py`，API `tests/test_pii_error_projection.py`。具体通过/失败与环境证据见 verification，不以本实施记录宣称专项完成。
