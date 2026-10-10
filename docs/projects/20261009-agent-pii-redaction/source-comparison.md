# F05：源码对照与取舍

> 本文记录 2026-10-09 实施前的源码盘点；实施后的能力与差异见 [实施记录](implementation/01-runtime-api.md) 和 [验证记录](verification.md)。

## 参考基线

2026-10-09 检查用户指定的本地 `research/deer-flow`、`research/open-swe` 和当前平台工作区，以工作区源码为准，不把 README 宣称当成运行证据。

| 仓库 | HEAD | 注意 |
|---|---|---|
| 当前平台 | `85d63d87bdf84dabbb963f79e8dd4b2db4432ade` | 调研开始时工作区干净 |
| DeerFlow | `cc664451f03140b376611f329ae400c313530bdb` | 工作区有本地改动；路径采用当前 monorepo 结构 |
| Open-SWE | `ad417d64d91cc349d63d832c7b643637dc1774cf` | 工作区有大量改动，`uv.lock` 存在冲突；不安装、运行或修改参考仓 |

参考关键文件的 SHA-256：

| 仓库内路径 | SHA-256 |
|---|---|
| DeerFlow `backend/packages/harness/deerflow/agents/middlewares/pii_redaction_middleware.py` | `6a6c3a6c0728580914184ee9ff300a726b170349f25f07e6ade1606dcf1fb724` |
| DeerFlow `backend/packages/harness/deerflow/config/pii_redaction_config.py` | `d92c8943db41a95126aca89a6dae0378d6b4ade76bc9dc09ce9d1e934803b25c` |
| DeerFlow `backend/packages/harness/deerflow/agents/middlewares/memory_middleware.py` | `774db3f312a9d080ad3d6327436a75980c3500f44441c58c3a67a7b9c8f952ca` |
| Open-SWE `agent/utils/langfuse.py` | `15ca56916690cb0c8a9a46e128cbcf390ffb1d4a6ed5eed8328acc60854afa5e` |
| Open-SWE `agent/utils/gateway.py` | `fa66d8ead3fea08ec35962028d60463a809bfccca05151ef88fe440cf522562d` |

## DeerFlow 实际怎样做

主要参考位置均在 `backend/packages/harness/deerflow/` 下。

| 位置与符号 | 实际行为 | 取舍 |
|---|---|---|
| `agents/middlewares/pii_redaction_middleware.py::_DETECTORS` | 邮箱 → API Key → 身份证 → 信用卡 → 手机；数字规则用 lookaround，避免中文 `\b` 问题 | 借鉴顺序和中文边界测试；不把校验和当成真实性证明 |
| 同文件 `_placeholder_token()` | HMAC-SHA256，前 16 字节；使用 `a-z` 的 26 字符字母表编码为 27 字符 token；输入实际为 `category + NUL + value` | 借鉴有密钥、无映射、幂等；同事描述的 `category:value` 与源码不一致 |
| 同文件 `_process_request()` / `wrap_model_call()` / `awrap_model_call()` | 只改需要清洗的 HumanMessage 请求副本，并处理请求内 `summary_text`；state 保留原文 | 借鉴副本方式；当前平台没有同名 summary state，不迁移 DeerFlow provenance 字段 |
| 同文件 `_should_redact()` / `_redact_result()` | 只处理固定 web 工具及带 DeerFlow MCP 标记的结果；支持 ToolMessage 和 `Command.update.messages` | 不迁移工具名/tag 判断；本平台最终模型边界统一处理 ToolMessage，保留工具执行事实 |
| 同文件 `_try_process()`、工具 wrapper | 普通异常记录 warning 后返回原请求/结果；GraphBubbleUp 单独传播 | 不作为强保护的默认失败语义；不能保证开启后原文不会外发 |
| `config/pii_redaction_config.py::PiiRedactionConfig` | 默认关闭；五个 `redact_*` 布尔字段；启用时密钥至少 16 字符 | 沿用默认关闭，改用本平台环境配置；长度检查不等于密钥熵 |
| `agents/middlewares/tool_error_handling_middleware.py::_build_runtime_middlewares()` / `build_subagent_runtime_middlewares()`；`agents/factory.py` 装配 | 主/子 Agent 显式加入同一 PII 组件 | 借鉴共用接线；不复制第二套 factory/runtime |
| `agents/middlewares/summarization_middleware.py` / `durable_context_middleware.py` | 压缩输入和摘要重新注入调用 `redact_text()` | 必须对应补当前摘要路径，不能只靠主图 wrapper |
| `agents/middlewares/title_middleware.py` | 完整用户/助手字段先脱敏，再截断，再直接调用标题模型 | 借鉴先脱敏后截断，避免把敏感值切成检测不到的片段 |
| `agents/middlewares/memory_middleware.py::redact_queued_messages()`；`agents/memory/summarization_hook.py::memory_flush_hook()` | 后续补片已覆盖记忆提取队列、工具参数与原文 provenance | 同事五项清单漏掉此范围；本平台记忆有精确 quote 校验，不能直接换成占位符 |
| `tracing/factory.py::_create_langfuse_handler()` | 独立装配 Langfuse 回调，未在此处看到 PII export mask | 模型前 wrapper 不能证明链/工具级追踪不记录原文；沿用本平台更严格出口 |

身份证实现中对日期只做年月日范围检查，未验证真实日历日期；例如 2 月 31 日仍可通过该日期判断。CPF/CUIT/RFC 等外国证件规则不属于本期需求。API Key 检测仅涵盖已知前缀，普通 Bearer/JWT、无前缀密钥及任意密码不自动被覆盖。

## Open-SWE 能力与本平台已有能力

| 能力 | Open-SWE | 本平台事实 | 是否重做 |
|---|---|---|---|
| 追踪凭据清洗 | `agent/utils/langfuse.py::_redact()` / `_mask_otel_spans()` 按字段和凭据格式替换 span 中的字符串 | `apps/runtime-service/src/runtime_service/observability/langfuse.py::_mask_spans()` 删除 input/output/exception/status 属性；`_mask()`、metadata 白名单提供补充保护 | 不重做；补结构化 payload/metadata 回归，保持正文不导出 |
| 外部模型策略网关 | `agent/utils/gateway.py::gateway_overrides()` 路由到可选 LangSmith Gateway；实际 PII 政策在外部配置，部分 provider/缺 key 时回退直连 | `runtime/modeling.py::build_model()` 是受管 Provider 连接构造，不是内容脱敏网关 | 不把借鉴 Open-SWE 等同于已具备 PII；本期不加外部 Gateway 依赖 |
| 异常和诊断保护 | MCP 等入口有凭据错误处理 | `tools/errors.py`、`observability/errors.py`、`observability/diagnostics.py` 及 Platform API 安全投影已有实现 | 复用；不把它们改成第二份内容检测器 |
| 普通模型输入 PII | 未在检查的 `agent/**/*.py` 中找到本地五类请求副本检测机制 | 未在 `apps/runtime-service/src/**/*.py` 找到相应机制 | 存在缺口，但是否启用取决于部署的数据外发需求 |
| 消息结构修复 | 多个 Sanitize middleware 修复模型消息/参数 | `middlewares/runtime_config.py::sanitize_tool_call_messages()` 保证 AI/Tool 配对与格式 | 复用；这是结构修复，不能当作 PII 检测 |
| 凭据展示遮罩 | Dashboard 凭据界面隐藏值 | Platform API `platform_config/service.py::_mask_secret()` 及模型目录凭据访问边界 | 复用；只保护凭据字段展示，不检测聊天正文 |

当前代码位置一律相对 `apps/runtime-service/src/runtime_service/`，除非表中明确标注完整服务路径。

## 官方能力能否直接复用

已先查询 `langchain-docs` 与 `langchain-reference` MCP，并核对本平台锁定/已安装的 LangChain `1.3.17`、DeepAgents `0.7.8`、Langfuse `4.15.1`、GraphHarbor `0.13.0.post43`。不能根据 `docs/CONTEXT.md` 中旧 post42 描述推断当前锁版本。

- [PIIMiddleware 官方参考](https://reference.langchain.com/python/langchain/agents/middleware/pii/PIIMiddleware)支持内置邮箱/信用卡与自定义 detector；公开 `PIIMatch`、`detect_email`、`detect_credit_card` 可用于复用或对照。
- 当前版本 `before_model()` 只检查最后一条 HumanMessage，以及最后一个 AIMessage 后面的工具结果；返回 state 更新。命中后用 `str(content)` 重建消息，不能满足本方案的全历史、请求副本和多模态结构保留要求。
- 当前 `hash` 策略是无密钥 SHA-256 的前 8 个 hex 字符，既非 HMAC，也不足以满足低熵标识符保护及本方案碰撞预算；不能直接替代。
- 当前邮箱/卡号 `\b` 规则漏检中文紧贴值；信用卡规则限定 16 位，未覆盖 13–19 位。已用合成数据复现，见验证记录。
- 官方新版本支持流 transformer，但本期不做 UI/流输出 PII 改写，不新增第二套 SSE 清洗器。

因此：复用官方 Middleware/ModelRequest/消息结构与可适用的公开检测函数，补上中文边界、所需校验和与 HMAC；不整套启用官方 state 改写 middleware 再叠一套 DeerFlow middleware，不导入官方私有 `_redaction` 接口。

## 需求价值与代价

| 场景 | 判断 | 原因 |
|---|---|---|
| 只担心追踪平台保存正文 | 不新增 F05 | 现有正文删除更直接，重新保存脱敏正文还会扩大数据暴露面 |
| 使用外部模型，明确禁止发送五类文本标识符 | 建议实施 | 请求副本保护能补现有缺口，需全入口验收 |
| 需要模型生成正确收件地址、查询指定手机号或处理真实支付数据 | 谨慎启用 | 占位符会破坏任务；本期没有自动恢复或受控数据执行通道 |
| 以“工业级”为理由默认全局开启 | 不建议 | 没有指定数据边界时收益无法验收，误报和任务降质可直接影响用户 |
| 要保证任何 PII、图片、工具外发、日志与存储都安全 | F05 不够 | 需要另行批准的数据分类、出口和生命周期治理，正则不能承担该承诺 |

本方案只复用现有的授权、模型构建、状态和观测体系。新增算法有明确的当前调用点，不建设新的安全平台。
