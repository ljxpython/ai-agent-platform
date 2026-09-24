# Dear Agent 记忆任务进度

本文件是进度事实源；具体方案见 [Runtime](02-runtime-implementation.md)、[Platform](03-platform-api-contract.md)、[前端交接](04-frontend-handoff.md) 和 [验证](05-verification-and-delivery.md)。日期均为 2026-09-24。`[~]` 表示已实施一部分但未满足该任务全部验收，不能计入完成。

## Runtime

### R01 公开投影与旧数据
- **改动内容：** 新 MemoryView 投影隔离 sources、墓碑和内部提取字段；保留旧路由形状。
- **代码位置：** `apps/runtime-service/src/runtime_service/http/dear_memory.py:envelope`、`services/dearflow_agent/memory.py:MemoryStorage.view`。
- **预期结果：** 新旧客户端分别取得约定形状，旧 JSON 安全读取。
- **验证项：** 新 HTTP/PG 与旧 JSON 读写兼容 fixture 通过。
- **状态：** [x] 已完成，见 `implementation/01-backend-memory.md`。

### R02 命令、事务与去重
- **改动内容：** action 严格字段、CAS、导入跳过计数、采纳替换、事务内提交快照。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py:MemoryCommand`、`MemoryStorage.change`。
- **预期结果：** 非法命令无写入；并发仅一次成功；响应对应本次提交。
- **验证项：** `test_p6_governance.py` PG CAS/导入/替换和 `test_memory_contract.py` 通过。
- **状态：** [x] 已完成，见 `implementation/01-backend-memory.md`。

### R03 到期、容量与维护
- **改动内容：** 过期实体写时清理；sources、墓碑和候选上限暂停自动提取，人工删除仍可用。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py:MemoryStorage.change`、`begin_extraction`。
- **预期结果：** 满额不锁死人工管理；清空旧 epoch 晚到无效。
- **验证项：** 隔离 PG 覆盖过期清理、候选/sources/墓碑满额、人工删除及 clear 重置 epoch；候选满额后删除可重新启用。
- **状态：** [x] 已完成，见 `implementation/02-source-and-model.md`。

### R04 无线程内部接口
- **改动内容：** 新 GET/POST `/internal/dear/memory`，双端 operation 白名单，保留旧路由。
- **代码位置：** `apps/runtime-service/src/runtime_service/http/dear_memory.py`、`runtime/auth.py`、`webapp.py`。
- **预期结果：** 仅有效用户项目委托可访问；disabled 不查 PG。
- **验证项：** Runtime 合约测试与真实 Platform→Runtime→PG HTTP 链路通过。
- **状态：** [x] 已完成，见 `implementation/01-backend-memory.md`。

### R05 来源与摘要
- **改动内容：** 主用户消息快照合并同 run、同 owner 的持久队列消息；摘要后仍可提取，拒绝未知作者来源。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/memory.py:abefore_agent/aafter_agent`、`messaging/inbox.py:memory_sources`。
- **预期结果：** 来源真实，摘要后保留，队列异作者不污染本人。
- **验证项：** 摘要、队列作者/交付状态、同 run 批量来源和逐条 quote/ID 隔离测试通过。
- **状态：** [x] 已完成，见 `implementation/02-source-and-model.md`。

### R06 提取与状态
- **改动内容：** 两次共用180秒、PG 持久尝试次数、来源认领、失败状态、取消事务栅栏及跨 run 不重放。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/memory.py:aafter_agent`、`memory.py:begin_extraction/propose/finish_extraction`。
- **预期结果：** 失败可见，不误增 revision，旧 run 不覆盖新 run。
- **验证项：** 可控模型、隔离 PG 并发 run/批量来源及 MAOMAO 独立模型测试通过；完整平台 run/SSE 另列 R08/V03。
- **状态：** [x] 已完成，见 `implementation/02-source-and-model.md`。

### R07 召回与降级
- **改动内容：** 有界词法排序、标签转义、自动召回 PG 故障继续对话。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py:context`、`middleware/memory.py:awrap_model_call`。
- **预期结果：** 相关旧事实优先，候选/到期不注入，存储失败不破坏普通回答。
- **验证项：** 固定 10 正例＋10 负例、转义/预算/降级单测及 MAOMAO 合成事实问答通过。
- **状态：** [x] 已完成，见 `implementation/02-source-and-model.md`。

### R08 工具与共享权限
- **改动内容：** Platform ACL 受信回调；新 run 装配前、模型调用和工具执行前检查共享状态。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory_access.py`、`agent.py`、`tools/memory.py`。
- **预期结果：** 共享 Thread 不注入、不提取、不允许记忆工具；本人无 Thread 管理仍可用。
- **验证项：** HMAC、当前 ACL、运行中分享的可控测试通过；真实 run/SSE 分享竞态待测。
- **状态：** [~] 局部完成。

## Platform API

### B01 契约与 OpenAPI
- **改动内容：** 新请求/响应 Pydantic 类型和公开 OpenAPI。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py:MemoryCommandBody/MemoryView`。
- **预期结果：** 前端能读取新路由字段定义。
- **验证项：** OpenAPI、ready/disabled 投影、真实 422 `details.loc` 与 HTTP 包通过。
- **状态：** [x] 已完成，见 `implementation/02-source-and-model.md`。

### B02 网关、委托与权限
- **改动内容：** 新路由、service、upstream adapter；沿用 `project.runtime.read/execute`，限定用户本人。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`、`application/service.py`、`adapters/langgraph/runtime_gateway_upstream.py`。
- **预期结果：** 无需 Thread，客户端无法指定记忆 owner。
- **验证项：** 匿名/外人拒绝、真实 HTTP/PG、adapter 测试通过。
- **状态：** [x] 已完成，见 `implementation/01-backend-memory.md`。

### B03 错误与体积
- **改动内容：** 1.5MB 流式读取上限，422 和上游异常去正文。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py:write_dear_memory`、`adapters/langgraph/runtime_gateway_upstream.py:dear_memory`。
- **预期结果：** 返回 `error.code`、request_id，不泄露事实正文。
- **验证项：** 真实 HTTP 409/422/413 与请求 ID、adapter 503/504 脱敏映射通过。
- **状态：** [x] 已完成，见 `implementation/02-source-and-model.md`。

### B04 审计
- **改动内容：** 个人记忆路径按固定 action 审计，仅保存安全动作元数据。
- **代码位置：** `apps/platform-api/src/platform_api/modules/audit/http_resolution.py`。
- **预期结果：** 不将 fact text、quote 或导入数组落入审计。
- **验证项：** `test_audit_http_resolution.py` 通过。
- **状态：** [x] 已完成，见 `implementation/01-backend-memory.md`。

### B05 跨服务存储验证
- **改动内容：** Platform HTTP→Runtime HTTP→隔离 PG schema、重启持久化与冲突。
- **代码位置：** `apps/platform-api/tests/test_runtime_gateway_memory.py`。
- **预期结果：** 完整后端管理链路可用。
- **验证项：** 真实 HTTP/PG 测试通过；模型运行链路另属 R08/V03。
- **状态：** [x] 已完成，见 `implementation/01-backend-memory.md`。

### B06 前端交接包与方案修正
- **改动内容：** 审查修正前端交接文档 `04-frontend-handoff.md`，纠偏 `http-error.ts` 复用、孤儿 `useDearGovernanceContext.ts` 清理、`ThreadAccessControl.vue` 分享隐私提示、静默轮询、日期时区及双模导入预览规则。
- **代码位置：** `docs/projects/20260920-dear-agent-memory/04-frontend-handoff.md`。
- **预期结果：** 前端实施规范与后端真实 `MemoryView` 契约、现有前端基础设施 100% 对齐。
- **验证项：** 人工审查确认通过。
- **状态：** [x] 已完成（2026-09-24 用户已确认修正方案）。

## Platform Web（前端实施）

### F01 错误工具与无线程 Memory Service
- **改动内容：** 在 `http-error.ts` 导出同步错误/详情提取辅助；重写 `memory.service.ts` 对接 `/api/langgraph/dear/memory`，定义 `MemoryView`、`MemoryCommandPayload`（含 `replace_fact_id`）。
- **代码位置：** `apps/platform-web/src/utils/http-error.ts`、`apps/platform-web/src/services/dear-agent/memory.service.ts`、`apps/platform-web/src/services/dear-agent/memory.service.spec.ts`。
- **预期结果：** 彻底移除旧 `threadId` 参数依赖，完整解析 `{ request_id, error: { code, message, details } }`。
- **验证项：** `pnpm --dir "apps/platform-web" test:run "src/services/dear-agent/memory.service.spec.ts"` → ✅ 通过（5 passed）
- **状态：** `[x]` 已完成 2026-09-24 → 见 `implementation/03-frontend-memory.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新

### F02 无线程页面上下文、状态矩阵、防竞态与静默轮询
- **改动内容：** `DearAgentMemoryPage.vue` 切换至 `useWorkspaceProjectContext()`，删除孤儿 `useDearGovernanceContext.ts` 及 `.spec.ts`；实现 `ready`/`disabled`/只读横幅/提取状态栏/`pause_reason`、`scopeGeneration` 防竞态及 `extraction.running` 静默轮询。
- **代码位置：** `apps/platform-web/src/modules/dear-agent/pages/DearAgentMemoryPage.vue`、`apps/platform-web/src/modules/dear-agent/composables/useDearGovernanceContext.ts`（已删除）。
- **预期结果：** 无需创建会话即可管理个人记忆；`disabled` 独立提示；切项目反序响应不串数据；后台轮询不闪屏、不冲草稿。
- **验证项：** `DearAgentMemoryPage.spec.ts` 状态矩阵与竞态用例 → ✅ 通过
- **状态：** `[x]` 已完成 2026-09-24 → 见 `implementation/03-frontend-memory.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新

### F03 事实表单、本地时区日期与 409 CAS 冲突保留草稿
- **改动内容：** 事实新增/编辑弹窗使用 `BaseDialog`，`Array.from` 统计 Unicode 字符，`<input type="date">` 本地时区回显与 `23:59:59.999` ISO 转换（未改日期原样保留），409 冲突自动拉新 revision 并持久展示冲突提示。
- **代码位置：** `apps/platform-web/src/modules/dear-agent/pages/DearAgentMemoryPage.vue`。
- **预期结果：** 杜绝跨时区 `expires_at <= now()` 误触发 400；409 冲突不丢草稿、不自动重发 POST。
- **验证项：** `DearAgentMemoryPage.spec.ts` 表单、未改日期保留与 409 冲突用例 → ✅ 通过
- **状态：** `[x]` 已完成 2026-09-24 → 见 `implementation/03-frontend-memory.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新

### F04 候选卡片原文溯源、会话跳转与替换已有事实
- **改动内容：** 候选卡片展示 `quote`（缺失显示“历史记录缺少原文”）、`category`、`expires_at`、`source_kind` 及命名路由跳转 `workspace-dear-agent`；支持「直接采纳」、「替换已有事实…（`replace_fact_id`）」与「拒绝」。
- **代码位置：** `apps/platform-web/src/modules/dear-agent/pages/DearAgentMemoryPage.vue`。
- **预期结果：** 候选审核可溯源、可替换冲突旧事实。
- **验证项：** `DearAgentMemoryPage.spec.ts` 候选采纳/替换/拒绝/跳转用例 → ✅ 通过
- **状态：** `[x]` 已完成 2026-09-24 → 见 `implementation/03-frontend-memory.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新

### F05 便携 JSON 导出与文件/文本双模追加导入预览
- **改动内容：** 导出调用 fresh `readMemory` 下载 `dear-memory-YYYYMMDD.json`；导入支持选择 `.json` 文件或粘贴文本，前端严格校验体积/类型/分类/日期并预览有效/重复/错误条目，提交后按 `mutation.added/skipped` 反馈。
- **代码位置：** `apps/platform-web/src/modules/dear-agent/pages/DearAgentMemoryPage.vue`。
- **预期结果：** 非法分类/格式在前端精准拦截定位；合法数据追加导入并展示服务端真实计数。
- **验证项：** `DearAgentMemoryPage.spec.ts` 导出与导入校验用例 → ✅ 通过
- **状态：** `[x]` 已完成 2026-09-24 → 见 `implementation/03-frontend-memory.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新

### F06 标准确认弹窗与共享会话隐私提示
- **改动内容：** 记忆页删除/清空改用 `ConfirmDialog`；在 `ThreadAccessControl.vue` 的 `mode === 'share'` 安全说明区补齐“共享会话自动停用个人记忆，但历史回答中已生成的个人信息仍对共享成员可见”。
- **代码位置：** `apps/platform-web/src/modules/dear-agent/pages/DearAgentMemoryPage.vue`、`apps/platform-web/src/modules/chat/components/ThreadAccessControl.vue`、`apps/platform-web/src/modules/chat/components/ThreadAccessControl.spec.ts`。
- **预期结果：** 消灭 `window.confirm`；分享弹窗明确告知历史回答隐私边界。
- **验证项：** `DearAgentMemoryPage.spec.ts` 与 `ThreadAccessControl.spec.ts` → ✅ 通过
- **状态：** `[x]` 已完成 2026-09-24 → 见 `implementation/03-frontend-memory.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新

### F07 前端验证门禁与全套回归
- **改动内容：** 执行单元测试、TypeScript 类型检查与 ESLint 静态检查，记录验证结果到 `verification.md`。
- **代码位置：** `docs/projects/20260920-dear-agent-memory/verification.md`。
- **预期结果：** 单测、typecheck、eslint 零报错通过。
- **验证项：** `pnpm test:run` (16 passed)、`pnpm typecheck` (0 errors)、`pnpm exec eslint` (0 errors, 0 warnings) → ✅ 通过
- **状态：** `[x]` 已完成 2026-09-24 → 见 `implementation/03-frontend-memory.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新

## 验证与外部交付

- **V01 Runtime 单元与 PG：** [x] 定向契约、隔离 PG、授权和独立 MAOMAO 模型验证完成；5 条环境门控用例跳过，详见 `verification.md`。
- **V02 Platform 鉴权、HTTP、审计：** [x] 50 条相关测试通过，详见 `verification.md` Phase 区。
- **V03 新线程真实模型、性能及回退：** [~] 独立模型提取/问答与 PG 重启已测；平台真实 run/SSE、性能基线和部署回退未执行。
- **V04 前端重构与组件测试：** [x] F01—F07 全部完成，3 套测试共 16 条用例、typecheck 与 eslint 全绿；真实浏览器 E2E 待联调栈启动后执行。
- **V05 Final：** [ ] 尚待真实环境完整 run/SSE 与浏览器联调验收后执行 Final done 判定。

