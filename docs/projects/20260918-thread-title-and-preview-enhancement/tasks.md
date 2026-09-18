# 会话标题识别与消息预览优化 - 任务拆分

## Phase 1: 基础建设与手动重命名（P0）

### Task 1.1: platform-api 暴露 PATCH /threads/{thread_id} 更新元数据
- **文件：**
  - `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
  - `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`
  - `apps/platform-api/tests/test_runtime_gateway_http_matrix.py`
- **改动：**
  - 在 `service.py` 中增加 `update_thread_metadata` 方法，支持安全更新 `title` 与 `preview`，校验 `project.runtime.write` 权限。
  - 在 `http.py` 中新增 `PATCH /threads/{thread_id}` 路由。
- **状态：** 已完成

### Task 1.2: platform-web 服务层与列表渲染优化
- **文件：**
  - `apps/platform-web/src/services/threads/session.service.ts`
  - `apps/platform-web/src/modules/chat/components/ChatThreadSidebar.vue`
  - `apps/platform-web/src/modules/dear-agent/components/DearAgentThreadSidebar.vue`
- **改动：**
  - `session.service.ts` 增加 `update` 方法；
  - 侧边栏卡片增加编辑图标，支持 Inline 重命名会话；
  - 优化第二行预览，消除生硬的 `(无内容)` 兜底。
- **状态：** 已完成

### Task 1.3: 会话首条消息标题清洗与预览填充
- **文件：**
  - `apps/platform-web/src/utils/thread-title.ts`
  - `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
  - `apps/platform-web/src/modules/dear-agent/composables/useDearAgentSession.ts`
- **改动：**
  - 过滤快捷提示词前缀，避免所有标题都叫“设计功能方案：根据业务需求给出优雅的架构...”；
  - 在创建和执行过程中填充首条或最新消息摘要到 `preview`。
- **状态：** 已完成

## Phase 2: LLM 智能标题提炼（P1）

### Task 2.1: runtime-service 新增智能标题提炼端点
- **文件：**
  - `apps/runtime-service/src/runtime_service/http/title_summary.py`
  - `apps/runtime-service/src/runtime_service/webapp.py`
- **改动：**
  - 实现 `POST /internal/threads/{thread_id}/title/summarize`，从历史消息中提炼精炼标题，写回 metadata。
- **状态：** 待开始

### Task 2.2: platform-api 透传与前端静默调用
- **文件：**
  - `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`
  - `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
- **改动：**
  - 网关代理转发；首轮对话 `onCompleted` 后触发后台生成并刷新。
- **状态：** 待开始
