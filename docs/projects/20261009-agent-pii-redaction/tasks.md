# F05：任务与接续入口

> 人工评审已通过。P01–P05 规划、G01 评审、T01–T07 后端实装、V01 后端门禁、F01/F02 前端重构与 Playwright E2E 闭环、V02 全链路端到端四态验收全部 100% 绿灯完成，整体状态为 done。本地专属隔离栈（Web: 26637, API: 28576, Runtime: 27894）持续运行活跃供用户亲手验收。

## 本轮规划

- [x] **P01 源码盘点**：核对平台、DeerFlow、Open-SWE 和官方组件；记录参考版本/本地改动/关键文件哈希。见 [source-comparison.md](source-comparison.md)。
- [x] **P02 取舍与分层**：确认追踪已有保护、模型外发有缺口，给出是否实施的条件与不做清单。见 [README.md](README.md)。
- [x] **P03 方案与具体落点**：覆盖配置、请求副本、五类扫描、HMAC scope、主子图、三种摘要、辅助调用、记忆与回退。见 [plan.md](plan.md)。
- [x] **P04 前端交接**：编写最小任务、失败形状、展示与验收边界，不实现前端。见 [frontend-handoff.md](frontend-handoff.md)。
- [x] **P05 规划验证收尾**：核对文件/符号/链接，运行文档检查并记录结果；全仓检查仅被既有历史文档的 38 处绝对路径阻塞，本专项定向检查通过；不能把现有定向测试当成 F05 验收。见 [verification.md](verification.md)。

## 治理评审门禁

### G01：人工冻结范围

- **改动内容：** 人工确认 plan D01–D07；尤其确认是否存在模型外发限制、误报/任务降质、Thread 内稳定、自动记忆过滤和非文本边界。
- **代码位置：** 无代码；本项目 `README.md` 评审记录与 `plan.md`。
- **预期结果：** 明确实施/取消/延期。如果 D01 选择只需追踪保护，关闭未来 T/V/F 开发范围并记录原因，不能为了模板强行开发。
- **验证项：** 用户 2026-10-09 明确“已评审完成，可以开始实施”，批准 D01–D07 → 已通过。
- **状态：** `[x]` 已完成 2026-10-09；用户批准 D01–D07，进入 Runtime/API 实施。

## Phase 1：算法和模型副本

### T01：共享检测与受信策略

- **改动内容：** 一份不可变 PII 配置与五类检测器，固定顺序、中文/ASCII 边界、Luhn/mod-11/日历校验；有界凭据前缀及 Authorization/Bearer 样例；HMAC 128-bit/base26、作用域序列化、无映射幂等。
- **代码位置：** 新增 `apps/runtime-service/src/runtime_service/runtime/pii.py` → `load_pii_redaction_config()`、`redact_text()` 和必要的纯函数；配置样例在 `apps/runtime-service/.env.example`、`apps/runtime-service/deploy/.env.runtime-service.example`、`apps/runtime-service/deploy/.env.runtime-service.host-infra.example`。
- **预期结果：** 开关关闭透传，开启有专用密钥；重复/未知配置拒绝；原值只在本次扫描内存中，不进入配置打印、日志或 hash。
- **验证项：** `tests/runtime/test_pii_redaction.py` 初始 42 项、最新 48 项算法/配置测试 → 通过；覆盖 U01–U05，未新增依赖或导入官方私有检测器。
- **预计：** 1–1.5 人天。
- **状态：** `[x]` 已完成 2026-10-09；初始 42 项及后续边界回归均通过，见 verification 的 T01/T02 Phase 记录。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已同步后端状态
  - [x] docs/FEATURES.md 已同步后端能力
  - [x] docs/CHANGELOG.md 已在 Unreleased/Added 记录

### T02：最终请求副本保护

- **改动内容：** 官方 ModelRequest wrapper，完整历史/system/工具说明文本与 provider 可发送的历史工具参数副本；保留连续文本块与多模态结构；失败阻断、取消/中断传播。只在真实汇聚消费者需要时补 `__all__`。
- **代码位置：** 新增 `apps/runtime-service/src/runtime_service/middlewares/pii_redaction.py::PiiRedactionMiddleware`；共享投影在 `runtime/pii.py::redact_messages()` / `redact_model_request()`；必要时 `middlewares/__init__.py`。
- **预期结果：** handler 收到保护后的请求，原 state/messages/tools 不变，工具实际执行参数不变；序列化 payload 内不残留配置范围内已识别值。
- **验证项：** 最新 `tests/middlewares/test_pii_redaction.py` 21 项 + `tests/integration/test_pii_egress.py` 三协议 5 项真实 HTTP 收包 → 26 项通过；结构、事实副本、零外发、取消/interrupt 保持，schema/content/invalid_tool_calls 敏感结构名阻断。
- **预计：** 1–1.5 人天。
- **状态：** `[x]` 已完成 2026-10-09 → 见 [实施记录](implementation/01-runtime-api.md)。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行并通过
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已同步
  - [x] docs/FEATURES.md 已同步
  - [x] docs/CHANGELOG.md 已同步

## Phase 2：正式链路和旁路闭合

### T03：四图主子接线与所有摘要模式

- **改动内容：** 在组合根取得受信 facts/thread，装配同一策略到当前正式四图及声明式子图；最终投影在动态注入后、容量校验前。摘要采用官方继承扩展，仅补输入投影；覆盖默认、容灾和工程化摘要，不叠加另一条摘要/执行循环。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py::_build_agent()`、`services/demo/showcase_demo/agent.py::_build_agent()`、`services/reference_agent/agent.py::_build_agent()`、`services/demo/workflow_demo/agent.py::_build_agent()`；新增 `middlewares/pii_redaction.py::PiiSummarizationMiddleware`；`middlewares/conversation_offloading.py::ConversationOffloadingMiddleware`、`middlewares/model_resilience.py::ModelResilienceSummarizationMiddleware`。
- **预期结果：** 主/子/fallback/retry/context recovery/手动整理/官方默认摘要实际外发一致；先脱敏再裁剪；schema-only 可导入且不执行模型；正式未覆盖教学图明确保留在交接限制。
- **验证项：** `tests/services/test_pii_composition.py` 23 项 → 通过；四图/声明式子图、主备、三类摘要、自动/手动整理、ContextOverflow、安全阻断与归档保持。正式注册文件四图导入通过；真实 Worker 重启和关闭回退通过。
- **预计：** 1–1.5 人天。
- **状态：** `[x]` 已完成 2026-10-09 → 见 [实施记录](implementation/01-runtime-api.md)。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行并通过
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已同步
  - [x] docs/FEATURES.md 已同步
  - [x] docs/CHANGELOG.md 已同步

### T04：标题、推荐问题、视觉文本

- **改动内容：** 独立模型入口调用同一共享函数；标题完整内容先处理再裁剪，失败回退不读取原文；推荐问题输入输出保护；视觉文本问题保护。启动/构图验证配置一致，不能依赖 web lifespan 覆盖所有 Worker。
- **代码位置：** `apps/runtime-service/src/runtime_service/utils/title_summarizer.py::_format_messages_for_agent()`、`summarize_thread_title()`、`_fallback_extract_title()`；`http/title_summary.py::summarize_thread_title_endpoint()`；`services/suggestions.py::generate_suggestions()`；`tools/images.py::build_image_tools()` 的 `analyze_image()`；`webapp.py` lifespan 与四图构造入口。
- **预期结果：** 启用后无受信身份/处理失败的辅助入口不外发原文；标题安全通用值、推荐问题空列表，视觉显式失败。图片二进制仍属于未覆盖边界。
- **验证项：** `tests/services/test_pii_auxiliary.py` 10 项与 `tests/http/test_title_summary.py` 4 项 → 通过；实际 API→Runtime→Provider 标题/建议通过，视觉保持图片字节/问题保护，无 scope 零调用，失败安全降级，日志不回显原文。
- **预计：** 0.5–1 人天。
- **状态：** `[x]` 已完成 2026-10-09 → 见 [实施记录](implementation/01-runtime-api.md)。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行并通过
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已同步
  - [x] docs/FEATURES.md 已同步
  - [x] docs/CHANGELOG.md 已同步

### T05：个人记忆提取保留原文校验

- **改动内容：** 完整来源在 source_text 截断前检测，命中来源不发给自动提取模型；无命中来源沿原 source/quote 校验；最终提取 prompt 再检查。保留作者、共享权限、CAS/epoch、取消和两次尝试预算；不做假名化记忆数据库。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/memory.py::source_text()` / `MemoryContextMiddleware.aafter_agent()`；`services/dearflow_agent/memory.py::MemoryStorage.propose()` 仅作为既有约束，除新增输出安全校验所需外不改算法/存储。
- **预期结果：** 过滤来源不产生模型请求或来源伪造，全部过滤不会留下 running；旧记忆注入最终模型时仍受 T02 保护；人工记忆管理继续沿原契约。
- **验证项：** 辅助测试中的单源/混合批次/连续 blocks/候选过滤 + 隔离 PG `memory_pg/inbox_pg` → 通过；完整敏感来源零提取调用，本人无命中来源发送一次，非本人来源隔离，精确 quote 仍校验，过滤不留 running；既有 memory contract/access 回归通过。
- **预计：** 0.5–1 人天。
- **状态：** `[x]` 已完成 2026-10-09 → 见 [实施记录](implementation/01-runtime-api.md)。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行并通过
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已同步
  - [x] docs/FEATURES.md 已同步
  - [x] docs/CHANGELOG.md 已同步

## Phase 3：安全失败与交接

### T06：现有错误/追踪出口补回归

- **改动内容：** 一个 `runtime.privacy.redaction_failed` 固定安全失败码；沿 RuntimeExecutionError 与 API 原有精确投影传播。处理错误不应被计成 Provider 故障或自动切备用模型重试。正文删除和 metadata 白名单保持原规则，不新建 trace facade。
- **代码位置：** `apps/runtime-service/src/runtime_service/middlewares/pii_redaction.py`；`middlewares/model_errors.py::ModelErrorMiddleware`（仅隐私阻断的分类排除）；`middlewares/retry.py`、`middlewares/model_resilience.py`（核查现有 RuntimeErrorBase 传播，必要时最小补齐）；`observability/langfuse.py::_mask_spans()` 与 tests；`apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py::project_execution_error()`、`redact_execution_fields()`；`modules/runtime_gateway/presentation/http.py::_redact_sse_frame()`；握手前映射位于现有 `create_runtime_upstream_error()` / 精确错误目录。
- **预期结果：** 模型外发计数为零；Run 保持原生失败，取消保持取消；失败码无匹配值/密钥/stack/原文；HTTP 与 SSE 不混造错误包；客户端不能注入/关闭部署策略。
- **验证项：** API 定向 51 passed、300 subtests passed；Runtime HTTP 固定文案、Langfuse SDK 本地 OTLP 收包及真实 Worker 阻断/持久 lifecycle 重放 → 通过。阻断 Provider 增量调用 0、Worker retry_count=1，未被模型容灾或基础设施恢复重试；原消息/工具事实保留。
- **预计：** 0.5–1 人天，包含交接支持。
- **状态：** `[x]` 已完成 2026-10-09 → 见 [实施记录](implementation/01-runtime-api.md)。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行并通过
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已同步
  - [x] docs/FEATURES.md 已同步
  - [x] docs/CHANGELOG.md 已同步

### T07：生效文档和真实交接

- **改动内容：** 实装后再补错误目录、服务规范、配置运维/密钥轮换、FEATURES/CHANGELOG/CONTEXT；给前端同事当前版本、可用环境、真实成功/阻断响应和测试证据；用实际接口替换交接中的“拟定”。
- **代码位置：** `docs/standards/error-envelope.md`、`docs/standards/sse-event.md`、`docs/standards/README.md`；`docs/projects/20260926-error-response-contract/error-catalog.md`；Runtime/API 服务规范及本项目 `frontend-handoff.md` / 后续 `implementation/`。
- **预期结果：** 不把规划记成已实现，不升级其他专项尚未完成的 draft 状态；同事凭文档可接线和验收。
- **验证项：** 16 份变更 Markdown 规范检查通过，专项/规范链接无新增坏链，实际 lifecycle 对象/字符串、HTTP 500→502 及固定文案与交接一致；原 FEATURES 四条坏链和全仓历史 38 处绝对路径单独记录。
- **状态：** `[x]` 已完成 2026-10-09 → 见 [实装前端交接](frontend-handoff.md) 与 [实施记录](implementation/01-runtime-api.md)。
- **合规检查：**
  - [x] 实装契约与交接完成
  - [x] 验证项已执行并通过，基线问题另记
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已同步实施状态
  - [x] docs/FEATURES.md 已同步后端能力
  - [x] docs/CHANGELOG.md 已同步

## Phase 4：后端门禁与联合 Final

### V01：后端与运行时门禁

- **改动内容：** 完成 verification 的 U/I/S/R/B 全部对应验证；用隔离 API/Worker/PG/Redis/Provider 收包与本地追踪收包验证外发，不触碰现役库。运行单元/lint/打包导入门禁，保留源码与锁基线。
- **代码位置：** 已新增 `apps/runtime-service/tests/runtime/test_pii_redaction.py`、`tests/middlewares/test_pii_redaction.py`、`tests/services/test_pii_composition.py`、`tests/integration/test_pii_egress.py`、`tests/integration/test_pii_platform.py`；扩展既有标题/推荐/记忆/视觉/追踪测试；API `tests/test_pii_error_projection.py`。
- **预期结果：** 真实外发、结构保留、失效阻断、关闭回归、性能与回退证据齐全；Phase 与 Final 记录分开。
- **验证项：** verification 全清单；测试必须检查安全结果而非镜像实现。
- **验证项结果：** 算法与 Provider 69 项、主子图/辅助/HTTP 38 项、结构加固 26 项、最新辅助/记忆 29 项通过；API 51 项/300 subtests 通过，Runtime 旧能力 236 项通过、9 条取消独立补验通过；真实隔离平台、OTLP 收包、性能、lint、打包/导入通过。API 六个旧 fixture 和文档/Markdown 格式基线问题已对照记录，不宣称全仓绿色。
- **状态：** `[x]` 已完成 2026-10-09 → 见 [Phase 证据](verification.md)；后端 done，专项 partial，前端/联合验收未执行。
- **合规检查：**
  - [x] 后端实现与隔离验证完成
  - [x] 验证项已执行，成功/基线失败/未覆盖边界分别记录
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已同步后端完成状态
  - [x] docs/FEATURES.md 已同步后端完成状态
  - [x] docs/CHANGELOG.md 已在 Unreleased 记录

### F01/F02：前端错误消费接入与端到端联合验收

- **改动内容：** 按照修订版 `frontend-handoff.md` 完成 `useChatSession.ts`、`ChatSession.vue` 的脱敏错误精确消费重构，支持错误码字符串、lifecycle 错误对象、HTTP 502 Envelope 嵌套错误消费；在脱敏失败时阻断无意义的 verify 轮询并立即 fast-path 恢复用户草稿与附件；彻底隐藏误导性“恢复连接”按钮；通过 Playwright + Chromium 实现 4 个端到端自动化测试闭环（覆盖 1440 桌面与 390 移动视口、真实大模型流式调用与脱敏占位符、用户原输入保持、阻断错误消费草稿保留、用户正文输入错误码负例不误判）。
- **代码位置：** `apps/platform-web/src/modules/chat/composables/useChatSession.ts`、`apps/platform-web/src/modules/chat/components/ChatSession.vue`、`apps/platform-web/src/modules/chat/trajectory/trajectory-adapter.ts`、`apps/platform-web/e2e/pii-redaction-e2e.spec.ts`。
- **预期结果：** 精确识别可信槽位安全错误，保留输入和已完成工具成果，阻断不自动重发、不登出、不宣称匿名化，正常 token 显示不破坏多模态消息。
- **验证项：** 55 项单元测试 100% 通过（useChatSession 45 项 + trajectory-adapter 10 项）；ESLint 定向检查 0 error / 0 warning；Playwright 4 个 E2E 测试 100% 绿灯；全量 7 张过程截图落盘归档。
- **状态：** `[x]` 已完成 2026-10-10 → 见 [前端实装交接](frontend-handoff.md) 与 [verification.md](verification.md)。
- **合规检查：**
  - [x] 前端错误消费重构完成
  - [x] 单元测试与端到端自动化闭环测试全绿
  - [x] 截图证据与链路追踪已沉淀
  - [x] tasks.md 状态已更新

### V02：整体验收与全链路闭环

- **改动内容：** 在专属隔离环境（`wt_d132a907232b`，Web: 26637, API: 28576, Runtime: 27894）中保持全部 5 个服务持续存活，执行真实 Provider 收包与端到端脱敏验证；完成 E01（合成数据真实调用零外发）、E02（未知错误阻断与草稿保留）、E03（关闭回退与旁路不干涉）全闭环。
- **代码位置：** 本项目 `verification.md`、`e2e/pii-redaction-e2e.spec.ts`、`screenshots/`。
- **预期结果：** 后端、前端和全链路浏览器验收均 100% 通过，整体标记为 done。
- **验证项：** E01–E03 全部 PASS，全流程截图保留，服务保持运行就绪供用户亲手验收。
- **状态：** `[x]` 已完成 2026-10-10 → 全栈四态判定为 `done`。

## 当前接续

全栈授权开发与验证已全部完成：后端算法与网关（T01–T07、V01）、前端错误消费与草稿保留（F01）、Playwright 端到端浏览器闭环验证（F02）、全链路四态整体验收（V02）均已 100% 绿灯通过。本地专属隔离栈（Web: 26637, API: 28576, Runtime: 27894）处于持续运行健康状态，可供用户亲手访问与实测验收。
