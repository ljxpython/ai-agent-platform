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

### Task 2.1: runtime-service 核心提炼逻辑与后置清洗
- **文件：**
  - `apps/runtime-service/src/runtime_service/utils/title_summarizer.py`
  - `apps/runtime-service/tests/utils/test_title_summarizer.py`
- **改动：**
  - 读取 `DEEPSEEK_PROXY_URL`、`DEEPSEEK_PROXY_API_KEY`、`DEEPSEEK_PROXY_DEFAULT_MODEL`（`DeepSeek-V4-Flash`）；
  - 使用 LangChain 统一范式 `create_agent(model=..., system_prompt=..., tools=[])` 构建标题总结 Agent；
  - 实现 `clean_generated_title` 严格防呆截断（<=10 字符，去引号去标点）；
  - 编写单元测试覆盖普通场景、超长输出、特殊标点与异常 fallback。
- **状态：** 已完成

### Task 2.2: runtime-service 内部 HTTP 接口暴露
- **文件：**
  - `apps/runtime-service/src/runtime_service/http/title_summary.py`
  - `apps/runtime-service/src/runtime_service/webapp.py`
  - `apps/runtime-service/tests/http/test_title_summary.py`
- **改动：**
  - 编写 `POST /internal/threads/{thread_id}/title/summarize` 路由；
  - 支持传入 messages 或自动从 Checkpoint 捞取前两轮消息；
  - 在 `webapp.py` 中挂载路由；
  - 编写端点单元测试验证 200 响应与异常 fallback。
- **状态：** 已完成

### Task 2.3: platform-api 网关代理与元数据自动落库
- **文件：**
  - `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`
  - `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
  - `apps/platform-api/src/platform_api/modules/runtime_gateway/application/ports.py`
  - `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py`
  - `apps/platform-api/tests/test_thread_metadata_update.py`
  - `apps/platform-api/tests/test_runtime_gateway_http_matrix.py`
- **改动：**
  - 暴露 `POST /api/langgraph/threads/{thread_id}/title/summarize`；
  - 进行用户读取与写入权限检查；
  - 代理调用 runtime-service 并在返回后自动通过 `update_thread` 落库更新 `metadata.title`；
  - 补充 API 矩阵测试与单测。
- **状态：** 已完成

### Task 2.4: platform-web 侧边栏 ✨ AI 魔法棒手动触发与会话刷新
- **文件：**
  - `apps/platform-web/src/modules/chat/components/ChatThreadSidebar.vue`
  - `apps/platform-web/src/modules/dear-agent/components/DearAgentThreadSidebar.vue`
  - `apps/platform-web/src/modules/chat/pages/ChatPage.vue`
  - `apps/platform-web/src/modules/dear-agent/pages/DearAgentPage.vue`
  - `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
  - `apps/platform-web/src/modules/dear-agent/composables/useDearAgentSession.ts`
- **改动：**
  - 在 `ChatThreadSidebar.vue` 和 `DearAgentThreadSidebar.vue` 卡片悬浮操作栏增加 ✨ `sparkle` 魔法棒按钮，Tooltip 显示“AI 智能生成标题”；
  - 增加 `summarizingThreadId` 状态与微型 Spin 旋转加载动画；
  - 在 `ChatPage.vue` 和 `DearAgentPage.vue` 实现 `handleAiSummarizeTitle`，调用 `session.service.ts` 的 `summarizeTitle` 并原地更新该卡片标题；
  - 清理 `useChatSession.ts` 和 `useDearAgentSession.ts` 中 `onCompleted` 里的自动静默调用，消除时序抢跑；
  - 补充单测并验证。
- **状态：** 已完成



