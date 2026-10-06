# Platform Web 回答后推荐问题落地实现

## 改动时间
2026-10-06

## 相关任务
- Task 4.1：API 封装与配置缓存
- Task 4.2：数据清洗纯函数与单测
- Task 4.3：状态机 Composable 与生命周期治理
- Task 4.4：卡片末尾展示组件与草稿冲突确认组件
- Task 4.5：集成到 ChatMessageList 与 ChatSession
- Task 4.6：全套单测、类型检查与生产打包验证

## 改动文件
- `apps/platform-web/src/modules/chat/suggestions/types.ts`（新）
- `apps/platform-web/src/modules/chat/suggestions/api.ts`（新）
- `apps/platform-web/src/modules/chat/suggestions/api.spec.ts`（新）
- `apps/platform-web/src/modules/chat/suggestions/cleaner.ts`（新）
- `apps/platform-web/src/modules/chat/suggestions/cleaner.spec.ts`（新）
- `apps/platform-web/src/modules/chat/composables/useFollowUpSuggestions.ts`（新）
- `apps/platform-web/src/modules/chat/composables/useFollowUpSuggestions.spec.ts`（新）
- `apps/platform-web/src/modules/chat/components/FollowUpConfirmDialog.vue`（新）
- `apps/platform-web/src/modules/chat/components/FollowUpSuggestions.vue`（新）
- `apps/platform-web/src/modules/chat/components/FollowUpSuggestions.spec.ts`（新）
- `apps/platform-web/src/modules/chat/components/ChatMessageList.vue`
- `apps/platform-web/src/modules/chat/components/ChatMessageList.spec.ts`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`

## 具体改动

### 1. API 契约与单例缓存（`suggestions/api.ts`）
- 显式传递 `x-project-id` 请求头，对齐 `_require_project_id` 契约，彻底杜绝 400 Bad Request；
- `loadSuggestionsConfig` 采用模块级 Promise 缓存，应用生命周期内不重复请求；
- `generateThreadSuggestions` 遵守 best-effort 契约，网络或服务器异常时静默降级返回空数组。

### 2. 数据清洗纯函数（`suggestions/cleaner.ts`）
- `stripThinkingText`：剥离 `<think>` 及 `<thinking>` 思维链标签；
- `extractPureMessageText`：剥离 `reasoning`、`image`、`file` 块，提取正文；
- `extractRecentSuggestionMessages`：角色强制映射为 `user`/`assistant`，严格过滤只包含 `{ role, content }`，单条安全截断 ≤ 4000 字符，总字符安全修剪 ≤ 12000 字符，至多截取最近 6 条。

### 3. 生命周期与状态机（`composables/useFollowUpSuggestions.ts`）
- 状态机响应流式运行终态（`isRunning: true -> false`）且无中断时自动触发；
- 用户手动点击“停止”（Stop）时由 `markStoppedByUser()` 抑制推荐生成；
- KeepAlive 场景：监听 `props.visible`，当从后台切回前台时，补偿触发后台已完成问答的推荐请求；
- 换 Thread / Agent 时主动 `controller.abort()` 并清空旧建议；
- 维护 `threadId:msgId:contentHash` 竞态凭证，严格防串响应。

### 4. UI 展示与草稿冲突（`FollowUpSuggestions.vue` & `FollowUpConfirmDialog.vue`）
- 挂载于 `ChatMessageList.vue` 最后一个已完成 Agent 卡片末尾；
- 加载态采用微型紧凑骨架胶囊（Zero-CLS），禁止高度突跳；
- 渲染推荐问题气泡按钮，并提供右侧紧凑 `X`（Dismiss）主动收起按钮；
- 发生草稿冲突时弹窗提示“追加并发送 / 替换并发送 / 取消”，避免污染 `ChatSession.vue`。

### 5. ChatMessageList 与 ChatSession 外科手术式装配
- `ChatMessageList.vue` 接收建议并仅在尾部 Agent 卡片渲染；
- `ChatSession.vue` 保持极简装配（仅增加 37 行代码），完全坚守 Clean Architecture 规范。
