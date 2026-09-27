# API/Web SSE 与线程会话保活实施记录

## 改动时间
2026-09-26

## 相关任务
- S1 展示与真实 SDK 基线
- S2 网关帧限额与安全关闭
- S3 HTTP 错误边界衔接
- S4 SDK 窄补丁
- S5 去除整流 Run 过滤与取消误判
- S6 会话恢复与 410
- S7 稳定宿主与条目模型
- S8 页面与组件必要接线
- S9 权限与作用域清理

## 改动文件
- `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`
- `apps/platform-web/patches/@langchain__langgraph-sdk@1.10.2.patch`
- `apps/platform-web/pnpm-workspace.yaml`
- `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
- `apps/platform-web/src/modules/chat/composables/useChatSessionPool.ts`
- `apps/platform-web/src/modules/chat/components/ChatSessionPool.vue`
- `apps/platform-web/src/modules/chat/pages/ChatPage.vue`
- `apps/platform-web/src/modules/dear-agent/pages/DearAgentPage.vue`
- `apps/platform-api/tests/fixtures/sse_contract_server.py`
- `apps/platform-web/e2e/sse-event-contract.spec.ts`
- `apps/platform-web/src/services/langgraph/transport.ts`
- 相关 API/Web 定向测试

## 具体改动

1. API 网关使用增量 SSE 分帧，限制单帧 8 MiB；损坏 UTF-8、非法 JSON、Protocol 外层错误、残帧和超限均安全结束，不透传原文。Protocol 与标准 Run 分别校验，并向追踪回调 `eof`、`frame_rejected`、`upstream_error`。
2. SDK patch 增加连接状态订阅、暂停/手动恢复、EOF/握手错误分类、空闲重连和 ready 清理；补丁源与锁文件可由 pnpm 10 frozen install 重现。
3. 会话池由 WorkspaceLayout 持有完整 ChatSession，通过 Teleport 停放；Thread、草稿、附件、上下文和参数按条目隔离。后台 ACK 只绑定条目，视图重新附着时才更新自身路由。
4. 410 恢复使用每 Thread 单飞：先读取权限、state 和 history，再恢复订阅；撤权清理缓存并断开流，网络故障保留授权快照。现有渲染、折叠、滚动和交互不变。

## 验证
- [x] API 分帧/上游错误定向测试：11 passed，110 subtests passed
- [x] Web 全量 Vitest：93 files passed，396 passed，1 skipped（真实 SDK 链路环境缺失）
- [x] SDK ESM/CJS 定向恢复测试：11 passed
- [x] Web typecheck、改动文件 ESLint、production build、pnpm frozen install：通过
- [ ] 真实三服务链路、实施前浏览器视觉基线、容量和三段脱敏样例：未验证
- [x] 隔离受控链路：真实 API/auth/router + 受控 gateway + 真实 SDK/ChatPage 的分片、坏帧、EOF、410、保活及撤权通过（15 passed）；增量细节见 `02-recovery-browser-regression.md` 与 `03-queue-and-fixture-isolation.md`。

## 限制
- 未改 Runtime/GraphHarbor、数据库、部署和 Git 分支/提交。
- 当前只有受控上游的 API/Web 隔离环境；新 Runtime/GraphHarbor 隔离库的迁移初始化不在本期授权，不能宣称真实链路或容量通过。
- 受控夹具已有 reset/scenario/advance/counters、EOF、410 及撤权；V01—V21 所需回放、错序、工具、审批和完整 Vue 场景仍待补齐。
