# 对话历史智能体维度过滤与紧凑微型分页器优化

## 背景与诉求
1. **历史会话未按选中的智能体隔离**：
   在通用对话工作台（Chat）中，切换不同智能体（如 `showcase_demo`）时，左侧会话历史列表始终拉取全项目的全部会话，导致不同 Agent 的对话互相混杂，用户无法直观查看和管理当前 Agent 的专属历史。
2. **前后端职责与设计缺失**：
   - 后端 Gateway 及 `@langchain/langgraph-sdk` 的 `/threads/search` 与 `/threads/count` 接口早已支持 `metadata.agent_id` 过滤。
   - 问题根源在于前端 `ChatPage.vue` 列表拉取未传入 `metadata: { agent_id }`，且未在智能体切换时联动刷新重置列表，属于前端调用与视图联动设计缺失。
3. **分页器寻径效率低**：
   原微型分页器仅支持简单的“上一页 / 下一页”，当会话数量较多（如上百条）时，用户无法快速直达最早的历史记录，也无法快速定位中间批次的数据。

## 变更内容
1. **历史会话按 Agent 过滤与动态联动 (`ChatPage.vue`, `session.service.ts`)**：
   - `session.service.ts` 的 `count` 方法扩展支持传入 `metadata` 过滤参数，与已支持 metadata 的 `list` 保持一致。
   - `ChatPage.vue` 统一计算当前生效的 `currentFilterAgentId`（结合当前 resolved 的目标 Agent 及路由 `agentId` 参数）。
   - `loadThreads` 和 `handlePageChange` 均携带 `metadata: { agent_id: filterAgent }` 向服务端发起查询，并在内存层进行健壮的兜底筛选。
   - 新增针对 `[activeProjectId, auth.sessionEpoch, currentFilterAgentId]` 的响应式监听，用户切换 Agent 时自动切换并重置至第 1 页，无刷新/同 Agent 内切 thread 不引起多余重载。
2. **紧凑微型分页器极简高质感升级（方案 A+B） (`ChatThreadSidebar.vue`)**：
   - 接入服务端 `totalThreads` 计数，精准呈现总数据量与总页数 `totalPages`。
   - 新增 `«` 首页与 `»` 末页直达按钮，针对 100 条会话一键即可直达最后一页（最早历史记录）或回到首页。
   - 新增页码微型数字输入框 `[ 3 ] / 5`，支持用户直接敲入页号回车或失焦快速跳至中间数据，越界或非法输入自动受控修正。
3. **单元测试与质量验证**：
   - `session.service.spec.ts` 补充 `list` 与 `count` 传递 `metadata` 参数的请求格式测试。
   - 新增 `ChatThreadSidebar.spec.ts` 单元测试，全面覆盖首页/末页/上页/下页事件发射、输入跳转、越界修正等场景。
   - `typecheck`（vue-tsc）零报错通过；`eslint` 对改动文件校验零 error 零 warning 通过；全量 72 个测试文件全部通过。

## 涉及文件
- [MODIFY] `apps/platform-web/src/services/threads/session.service.ts`
- [MODIFY] `apps/platform-web/src/services/threads/session.service.spec.ts`
- [MODIFY] `apps/platform-web/src/modules/chat/components/ChatThreadSidebar.vue`
- [NEW] `apps/platform-web/src/modules/chat/components/ChatThreadSidebar.spec.ts`
- [MODIFY] `apps/platform-web/src/modules/chat/pages/ChatPage.vue`
