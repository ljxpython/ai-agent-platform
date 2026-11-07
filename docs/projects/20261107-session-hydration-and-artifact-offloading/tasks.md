# 会话快照水合与媒体外置治理 - 任务拆分

> 更新：2026-11-07。总体方向和新数据范围已获用户确认；继续实现和联合验证，既有通过记录仅作阶段证据。项目进度以本文件为准，验收口径见 [verification.md](verification.md)。

## 范围约束

所有测试和实现面向新版本上线后新建的会话。无存量修复、数据迁移、双格式兼容或旧版本回退兼容任务。GraphHarbor 基线为 `0.13.0.post48`，当前方案不要求修改；若发现独立通用缺陷，遵循其仓库规范另行评估。项目为治理改动；人工确认来源见 [README.md](README.md)，不重复请求已给出的方向批准。

## Phase 0：评审与方案修订

### T00：评审结论落地

- [x] 阅读四份初稿，对照本地 SDK、前端消息管道、Runtime 媒体出口及 API 契约。
- [x] 记录用户确认：复用现有能力、仅覆盖新会话新数据、GraphHarbor 不得与业务耦合。
- [x] 修订 README/plan/tasks/verification，删除存量兼容设计，补齐职责、交接边界、统一性能口径和功能验证。
- **说明：** 上述完成项仅为静态评审与文档修订。初稿将现场性能证据标为已完成，缺少可复核产物，已改由 T01 补采；不能据此宣称根因或性能已实测。
- **完成日期：** 2026-11-07。

## Phase 1：基线与最小技术闭环

### T01：依赖基线、请求画像与快照交接验证

- **状态：** [/] 部分完成 2026-11-07 → SDK/快照交接与应用验证完成，F1/F2 性能基线 待完成；见 implementation/01-runtime-web.md
- **位置：** `apps/platform-web/package.json`、`pnpm-lock.yaml`、`patches/@langchain__langgraph-sdk@1.10.2.patch`；`apps/platform-web/src/modules/chat/composables/useSessionConnection.ts` → `useSessionConnection` / `recoverExpiredStream`；`apps/platform-web/scripts/inspect-session-loading.mjs`。
- **内容：** 核验 SDK lock、registry tarball 和本地补丁；修正测量脚本为可配置本地目标和输出目录，采集同一新建夹具的 Thread/State/History/SSE 请求数、完整响应耗时及体积分布。不得默认登录生产、使用硬编码凭据或依赖个人目录产物。
- **内容：** 验证 idle/pending/running/interrupted、快照期间状态变化、订阅间隙、重连/游标过期、跨页及后台运行发现；核对根消息与 scoped 详情的加载责任。
- **交付：** 可复现基线、依赖来源及摘要、完整性能记录、现有协议足够或不足的证据；在 plan.md 固化确切交接入口。
- **当前发现：** `@langchain/langgraph-sdk@1.10.2` registry integrity 与 lock 一致，`dist/stream/controller.js` 与安装文件逐字节一致；控制器自带 state hydrate、idle 延迟订阅和消息 ID 封存。GraphHarbor stream 先登记 queue 再回放持久化事件，以 sequence 去重；其独立 in-memory 定向测试 6/6 通过。未核对生产 bundle。SDK 的 `next=[]` 不能单独证明没有待启动 Run，仍需合并核对 Thread/Run 状态。
- **结果：** SDK/GraphHarbor 回放能力核查通过；首屏不再主动读取 history，相关 Web 回归和真实刷新恢复通过。F1/F2 30 样本性能基线未纳入本地收口。
- **验证：** 锁定安装可复现；可控事件时序下不漏消息、不退回中间态；采样口径满足 verification.md。
- **门禁：** 若缺口必须改 GraphHarbor，重新评估；不得直接修改 node_modules/site-packages 充当交付。

### T02：冻结新媒体引用与模型输入契约

- **状态：** [/] 部分完成 2026-11-07 → 见 implementation/01-runtime-web.md
- **位置：** `apps/runtime-service/src/runtime_service/middlewares/filesystem.py` → `ResultFilesystemMiddleware`；`apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py` 中主/子图中间件装配；`apps/runtime-service/src/runtime_service/workspace/artifact_refs.py` → `ArtifactWorkspace`；`apps/runtime-service/src/runtime_service/tools/images.py` → `build_image_tools`。
- **内容：** 明确当前支持的媒体块与实际工具返回类型；复用现有引用字段、不可变 Workspace 存储及远端路由。在工具返回前引用化，验证“工具结果 → 轻量 checkpoint/公开事件 → 模型临时展开 → 浏览器预览”。
- **交付：** 在 plan.md 固化单一引用结构、保存/解析切面、公开投影和错误语义；不新增兼容协议、存储服务或 UUID 成果物体系。
- **验证：** 真实模型可以读取图片信息；临时展开不写回状态；工具原始事件不绕过外置处理；原文件改写不改变已保存引用；失败不留下悬空引用。
- **当前发现：** Runtime v3 探针显示 middleware `handler()` 后改写可修正 checkpoint，却无法撤回已发出的 `tools/tool-finished` 原始输出；工具执行出口在事件 callback 之前返回时，公开工具事件只包含引用。因此现有 post-handler `_guard_result` 不是充分的媒体外置切面。
- **结果：** 同步/异步 `read_file` 工具入口均在公开前生成 `extras.runtime_image`；模型请求副本临时展开并校验 SHA-256；GraphHarbor 未修改。
- **门禁：** 若后续发现 GraphHarbor 独立通用缺陷，提交证据并依其仓库规范评估；不得直接修改 node_modules/site-packages 充当交付。
- **依赖：** T01 的依赖与协议边界。

## Phase 2：实现

### T03：前端权威快照与实时接管

- **状态：** [/] 部分完成 2026-11-07 → 见 implementation/01-runtime-web.md
- **位置：** `apps/platform-web/src/modules/chat/components/ChatSession.vue`；`composables/useSessionConnection.ts`；`composables/useChatActions.ts` → `loadHistory`；`composables/useTranscriptMessages.ts` → `useTranscriptMessages`（后三者相对 `src/modules/chat/`）。
- **内容：** 复用 SDK 控制器与现有消息管道，去除首屏仅为当前消息读取整批历史的路径；根据权威状态和版本对齐缓存、快照与事件，按需加载历史和子任务详情。
- **验证：** 新建会话完成后刷新/切回不倒退、不重复；运行中接管、审批恢复、停止、继续提问、分支、子任务与撤权均正常。
- **约束：** 不额外建立运行状态机，不为旧消息格式保留 fallback；故障恢复与权限保护继续有效。

### T04：Runtime 媒体外置与模型临时展开

- **状态：** [/] 部分完成 2026-11-07 → 见 implementation/01-runtime-web.md
- **位置：** T02 确定的工具返回/中间件切面、模型调用装配、Workspace 读写；测试位于 `apps/runtime-service/tests/middlewares/` 和 `tests/services/dearflow_agent/`。
- **内容：** 对当前支持的结构化内联二进制统一引用化；保留文本和消息关联字段，覆盖主/子图及当前工具的同步/异步返回路径。模型侧按当前 Provider 协议临时恢复媒体。
- **验证：** checkpoint 与公开事件不携带内联媒体；首次看图和后续追问正确；缺失/损坏/写入失败明确报错，不静默丢图、不重跑已执行工具、不退回内联格式。

### T05：API 投影与 Web 按需预览

- **状态：** [/] 部分完成 2026-11-07 → 见 implementation/01-runtime-web.md
- **位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`、`application/service.py`（后者相对同一模块）；`apps/platform-web/src/services/threads/workspace.service.ts`、`apps/platform-web/src/modules/chat/components/MessageContent.vue` 和实际媒体渲染组件。
- **内容：** 复用 State/History/Workspace 接口，按新引用最小补齐投影与预览。现有能力足够则只补验证，不强行为每个服务新增代码。
- **验证：** Thread/项目权限、子任务可见性、预览/下载、路径和类型校验；缺失文件只影响对应媒体展示；内部参考媒体不自动发布为成果物。
- **约束：** 不新增存量消息瘦身代理，不预设新 blobs 端点或 Transcript 存储。

## Phase 3：联合验收与收尾

### T06：功能、安全、性能与失败恢复验收

- **状态：** [/] 部分完成 2026-11-07 → 本地功能链路已完成；性能、远端 Workspace 和完整故障注入 待完成
- **内容：** 执行 verification.md 中单元、三服务集成、真实模型 E2E、性能与故障注入场景；读写入口均验证新引用，覆盖已支持的本地/远端 Workspace 部署模式。
- **交付：** 每个 Phase 独立证据，记录执行版本、命令、环境、夹具与实际结果；缺少环境先完成其余项，再准确报告缺口。
- **范围：** 不测试存量迁移或旧版本读取新格式；验证当前版本自身的失败恢复，不通过降级旧逻辑解决错误。

### T07：Final 复核与文档同步

- **状态：** [/] 部分完成 2026-11-07；按真实证据标记项目 `partial`
- **内容：** 独立填写 Final；逐项复核所有任务、GraphHarbor 业务零耦合及验收指标。更新 FEATURES/CONTEXT、实际受影响的服务规范，按实际 feat/fix/perf 写 CHANGELOG。
- **说明：** 当前仅文档修订，不新增用户可见已交付功能的 CHANGELOG，不提前将 SSE/JWT 草案毕业。
- **完成条件：** 全部范围达到 done；不能把 Phase 通过或文档修订完成当作功能交付。生产部署、Git 提交/推送不在当前授权内。

## 进度

- [x] Phase 0：评审与规划修订。
- [/] Phase 1：基线及最小闭环。
- [/] Phase 2：业务实现。
- [/] Phase 3：联合验收与 Final（本地功能通过，治理级完整证据 待完成）。
