# Platform Web 前端交接

## 目标

将回答后的动态推荐问题（Follow-up Suggestions）交接给前端同事落地，明确现有代码插入点、数据清洗纯函数、状态机生命周期、交互体验（防 CLS 与关闭机制）以及验收标准。本轮不直接修改前端业务源码。

---

## 当前代码证据与核心事实

1. **灵感胶囊（冷启动）与追问推荐（上下文）天然时序隔离**：
   - `ChatSession.vue` 中现有的 `shouldShowComposerSuggestions` 已内置强约束：当 `hasConversationStarted`、`displayedMessages.length > 0` 或 `messages.length > 0` 时恒为 `false`。
   - 因此，**只要会话已有消息，输入框上方的 `ComposerSuggestions.vue` 就会自动退场**，无需在前端编写恶心的跨组件互斥状态机。
   - 语义分工：
     - `ComposerSuggestions.vue`：零消息、空草稿时的开局破冰灵感；
     - `FollowUpSuggestions.vue`：单轮问答完成后的上下文深度追问。
2. **挂载位置决议**：
   - 推荐问题挂载在 `ChatMessageList.vue` 中**最后一个已完成的 Agent 回答卡片末尾**，跟随回答上下文展示。
3. **架构解耦与防腐化要求**：
   - 项目刚完成 Clean Architecture 重构（`ChatSession.vue` 压降至 1770 行）。**严禁将草稿冲突弹窗、确认状态机、消息过滤逻辑直接平铺塞入 `ChatSession.vue`**。
   - 必须保持关注点分离：API 封装 → 数据清洗纯函数 → Composable 状态编排 → UI 组件展示与确认弹窗内聚。

---

## Platform API 契约与硬性白盒约束

### 1. 网络层必须携带 `x-project-id`

后端 `platform-api` 网关层通过 `_require_project_id(request)` 强制校验项目上下文，**缺失 `x-project-id` 请求头会直接报 `400 Bad Request`**。

- 前端所有建议相关接口必须通过统一的 `platformHttpClient` 调用；
- 显式传递 `{ headers: { "x-project-id": projectId } }`。

### 2. 接口定义

#### 配置查询：`GET /api/langgraph/suggestions/config`
- **请求头**：`x-project-id: {projectId}`
- **响应体**：`{"enabled": true, "max_suggestions": 3}`
- **缓存策略**：配置属于环境/项目级策略，前端必须使用单例 Promise 或 Store 模块级缓存，整个应用生命周期内不重复请求。

#### 建议生成：`POST /api/langgraph/threads/{thread_id}/suggestions`
- **请求头**：`x-project-id: {projectId}`
- **请求体格式**：
  ```json
  {
    "messages": [
      {"role": "user", "content": "请解释这个架构"},
      {"role": "assistant", "content": "……"}
    ],
    "n": 3,
    "model_id": "optional-catalog-model-id"
  }
  ```
- **响应体格式**：`{"suggestions": ["能否比较这两种方案？", "下一步如何落地？"]}`

### 3. 服务端白盒硬校验规则（违规直接 400/422）

1. **属性严格白名单**：每个 message 对象**严格只能有 `role` 和 `content` 两个 key**（后端校验 `set(item) != {"role", "content"}`）。**严禁携带 `id`、`name`、`timestamp`、`tools` 等多余属性**。
2. **角色枚举**：`role` 仅接受 `"user"` 或 `"assistant"`（不兼容 `human`/`ai`）。
3. **长度与字符硬上限**：
   - 单条 `content` 去空后长度必须满足 `1 <= len <= 4000`；
   - 消息总字符数 `total_chars <= 12000`；
   - 消息数组数量 `1 <= len <= 6`；
   - `n` 范围必须为 `1 <= n <= 5`（服务端硬上限）。
4. **失败降级**：
   - 模型超时、上游 5xx、非法输出或配置关闭时，服务端均按 `200 + {"suggestions": []}` 降级返回；
   - 401/403/422 等错误由客户端静默吞吐收起，绝不得清理用户登录态或弹出全屏阻断报错。

---

## 前端落地实施方案

### 建议文件结构

```text
apps/platform-web/src/modules/chat/
├── suggestions/
│   ├── api.ts                     # 配置拉取与建议生成 API（带 projectId 与缓存）
│   ├── cleaner.ts                 # 消息提取与安全清洗纯函数
│   └── types.ts                   # 契约与状态类型定义
├── composables/
│   └── useFollowUpSuggestions.ts  # 生命周期、防抖、竞态、KeepAlive 补偿状态机
└── components/
    ├── FollowUpSuggestions.vue    # 卡片下方渲染组件（含骨架、淡入、X关闭）
    └── FollowUpConfirmDialog.vue  # 草稿冲突确认弹窗（独立解耦，不污染 ChatSession）
```

---

### 详细模块职责

#### 1. `suggestions/cleaner.ts`（数据清洗纯函数）

从前端复杂的 `BaseMessage[]` 中安全提取符合后端严苛契约的消息快照：
- 过滤掉 `tool`、`system` 及无文本消息；
- **彻底剥离 `reasoning`（思维链/思考过程块）**，防止 DeepSeek 等大模型的长推理思考撑爆 4000/12000 字符上限；
- 剥离多模态附件图片等非文本块；
- 角色严格映射为 `"user"` 和 `"assistant"`；
- 过滤空白字符串，单条文本安全截断到 4,000 字符，累计总字符截断到 12,000 字符；
- 截取最近至多 6 条有效消息；
- 产出纯净的 `Array<{ role: 'user' | 'assistant', content: string }>`。

#### 2. `suggestions/api.ts`（API 封装与缓存）

```typescript
// 单例 Promise 缓存，避免重复拉取配置
let configPromise: Promise<SuggestionsConfigResponse> | null = null;

export function loadSuggestionsConfig(projectId: string): Promise<SuggestionsConfigResponse>;
export function generateThreadSuggestions(
  projectId: string,
  threadId: string,
  payload: SuggestionsPayload,
  signal?: AbortSignal,
): Promise<string[]>;
```

#### 3. `composables/useFollowUpSuggestions.ts`（状态与生命周期）

- **暴露状态**：
  - `suggestions`: `Ref<string[]>`
  - `loading`: `Ref<boolean>`
  - `dismissed`: `Ref<boolean>`
  - `clear()`: 清空并重置状态
  - `dismiss()`: 用户主动关闭
  - `triggerForCompletedTurn()`: 触发生成
- **状态维护与安全护栏**：
  - 维护 `threadId + assistantMessageId + contentHash` 竞态凭证，响应返回后核对 key，不匹配立即丢弃；
  - 切换 `threadId` 或 `agentId` 时，**立即执行 `controller.abort()` 并重置状态**；
  - **用户主动停止（Stop）抑制**：监听 `onStop`，设置 `stoppedByUser` 标记，中断的半截回复绝不触发推荐生成；
  - **KeepAlive 补偿拉取**：监听 `props.visible`。如果 Agent 在后台运行完成导致前台未触发请求，当用户切回前台（`visible` 由 `false` 变为 `true`）时，若满足生成条件且该回答尚未请求过，补偿发起一次请求；
  - **异常防御**：API 返回空数组或报错时静默处理，`suggestions` 置空，不抛未捕获异常。

#### 4. `components/FollowUpSuggestions.vue`（展示与交互）

- **挂载位置**：`ChatMessageList.vue` 的 `displayEntry.author === 'agent'` 且为最后一个已完成回合的尾部；
- **防视口突跳（Zero-CLS）规范**：
  - 生成过程耗时约 1 秒，**加载过程中使用微型紧凑指示器或骨架条，严禁使用大高度占位框砸开视口**；
  - 推荐项返回后，采用平滑淡入（`animate-fade-in`）展示；
- **主动关闭能力**：右侧提供紧凑的 `X` 按钮，点击触发 `dismiss()`，收起当前建议；
- **交互与草稿冲突**：
  - 用户点击建议项时，若当前输入框为空，直接触发发送；
  - 若输入框已有草稿，呼出轻量确认弹窗（可复用 `FollowUpConfirmDialog`），提供：“追加并发送”、“替换并发送”、“取消”，绝不静默覆盖用户打好的草稿；
  - 发送完成后，当前轮次的建议栏自动收起。

#### 5. `ChatMessageList.vue` 与 `ChatSession.vue` 改动边界

- `ChatMessageList.vue`：
  - 仅作为宿主插槽，在最后一个 Agent entry 的操作栏下方渲染 `FollowUpSuggestions`；
  - 接收建议相关 props 并透传点击事件，不承担业务状态机；
- `ChatSession.vue`：
  - 作为唯一调度协调点，引入 `useFollowUpSuggestions`；
  - 监听流结束事件（`isSessionRunning` 变为 `false` 且无 pending review/clarification）；
  - 接收执行发送事件并复用现有 `send()` 链路，**不新建任何 Run API 逻辑**。

---

## 前端交接验收 Checklist

- [x] **项目头校验**：所有 API 请求均显式携带 `x-project-id`，无 400 报错。
- [x] **数据清洗防护**：
  - [x] 传给后端的数组元素严格只包含 `role` 和 `content`；
  - [x] 成功剥离 DeepSeek 等模型的 `reasoning` 思维链文本，无超长 422 报错；
  - [x] 纯多模态/空消息能被安全过滤，不向后端传递无效轮次。
- [x] **时序与互斥体验**：
  - [x] 新会话无消息时：显示输入框 `ComposerSuggestions` 灵感胶囊；
  - [x] 有消息后：输入框灵感胶囊彻底消失；
  - [x] Agent 回答完成后：仅在最后一条 Agent 消息末尾淡入 `FollowUpSuggestions`，绝不出现双排胶囊。
- [x] **防突跳与关闭交互**：
  - [x] 建议生成期间页面视口平稳，微型紧凑加载骨架无剧烈突跳（CLS 友好）；
  - [x] 点击右侧 `X` 按钮能立即收起建议栏。
- [x] **草稿冲突保护**：
  - [x] 空草稿点击：直接发送；
  - [x] 有草稿点击：弹窗提供追加/替换/取消选项，用户文字不丢失。
- [x] **状态机生命周期**：
  - [x] 用户点击“停止生成”后，不触发建议；
  - [x] 审批/澄清/流式进行中，不触发建议；
  - [x] 切 Thread/切 Agent 立即中止网络请求并清空残留建议；
  - [x] 后台会话切回前台（KeepAlive）时，能正常补录触发最后一条未请求的建议。
- [x] **质量红线**：
  - [x] `api.spec.ts`、`cleaner.spec.ts`、`useFollowUpSuggestions.spec.ts`、`FollowUpSuggestions.spec.ts`、`ChatMessageList.spec.ts` 27 项单测全绿；
  - [x] `vue-tsc` 0 错误；
  - [x] ESLint 0 错误；
  - [x] `pnpm build` 生产构建成功。

---

## 任务拆分

### Task 4.1: API 封装与配置缓存
- **改动内容：** 实现带 `x-project-id` 请求头与单例 Promise 缓存的建议服务封装
- **代码位置：** `apps/platform-web/src/modules/chat/suggestions/api.ts`
- **预期结果：** 正确请求配置与生成接口，异常安全降级为静默空数组
- **验证项：** `pnpm --dir apps/platform-web test:run src/modules/chat/suggestions/api.spec.ts` → ✅ 4 passed
- **状态：** `[x]` 已完成 2026-10-06 → 见 implementation/02-platform-web-followup-suggestions.md

### Task 4.2: 数据清洗纯函数与单测
- **改动内容：** 实现剥离思维链、剔除多模态附件、截断字数与严格构造 `{ role, content }` 的数据清洗函数
- **代码位置：** `apps/platform-web/src/modules/chat/suggestions/cleaner.ts`
- **预期结果：** 产出严格符合后端白盒约束的消息数组
- **验证项：** `pnpm --dir apps/platform-web test:run src/modules/chat/suggestions/cleaner.spec.ts` → ✅ 8 passed
- **状态：** `[x]` 已完成 2026-10-06 → 见 implementation/02-platform-web-followup-suggestions.md

### Task 4.3: 状态机 Composable 与生命周期治理
- **改动内容：** 实现 `useFollowUpSuggestions.ts`，内置竞态凭证、用户停止抑制、切 Thread 中断与 KeepAlive 补偿拉取
- **代码位置：** `apps/platform-web/src/modules/chat/composables/useFollowUpSuggestions.ts`
- **预期结果：** 状态机完整覆盖生命周期各个边角用例
- **验证项：** `pnpm --dir apps/platform-web test:run src/modules/chat/composables/useFollowUpSuggestions.spec.ts` → ✅ 5 passed
- **状态：** `[x]` 已完成 2026-10-06 → 见 implementation/02-platform-web-followup-suggestions.md

### Task 4.4: 卡片末尾展示组件与防 CLS/关闭交互
- **改动内容：** 实现 `FollowUpSuggestions.vue`（微型骨架防突跳、气泡按钮、X收起）与独立 `FollowUpConfirmDialog.vue`（草稿冲突确认）
- **代码位置：** `apps/platform-web/src/modules/chat/components/FollowUpSuggestions.vue`
- **预期结果：** 交互平滑无 CLS 抖动，支持手动 Dismiss 与草稿冲突分支确认
- **验证项：** `pnpm --dir apps/platform-web test:run src/modules/chat/components/FollowUpSuggestions.spec.ts` → ✅ 5 passed
- **状态：** `[x]` 已完成 2026-10-06 → 见 implementation/02-platform-web-followup-suggestions.md

### Task 4.5: 集成到 ChatMessageList 与 ChatSession
- **改动内容：** 在 `ChatMessageList.vue` 最后一个 Agent 卡片末尾挂载，在 `ChatSession.vue` 中仅增加 37 行调度胶水代码复用既有 `send()`
- **代码位置：** `apps/platform-web/src/modules/chat/components/ChatMessageList.vue`、`ChatSession.vue`
- **预期结果：** 成功接入消息流水线，严格恪守 Clean Architecture 规范
- **验证项：** `pnpm --dir apps/platform-web test:run src/modules/chat/components/ChatMessageList.spec.ts` → ✅ 5 passed
- **状态：** `[x]` 已完成 2026-10-06 → 见 implementation/02-platform-web-followup-suggestions.md

### Task 4.6: 全套单测、类型检查与生产打包验证
- **改动内容：** 执行建议模块全套单测回归、Vue TSC 静态类型检查、ESLint 代码规范与生产打包
- **验证项：**
  - `pnpm --dir apps/platform-web test:run ...` → ✅ 5 files, 27 tests passed
  - `pnpm --dir apps/platform-web typecheck` → ✅ vue-tsc 0 errors
  - `pnpm --dir apps/platform-web lint` → ✅ eslint 0 errors
  - `pnpm --dir apps/platform-web build` → ✅ built in 18.67s
- **状态：** `[x]` 已完成 2026-10-06 → 见 implementation/02-platform-web-followup-suggestions.md

---

## 状态

**已完成 (done)**

前端 Platform Web 的回答后推荐追问能力已全部落地并严格通过全部门禁验证。
