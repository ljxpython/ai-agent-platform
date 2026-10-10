# F07 前端交付与实施方案规范（老王架构审查修订版）

> **状态：** 2026-10-10 前端方案架构审查完成。已修复原交接中的 `ChatSessionPool` 事件管道断链、SDK 类型报错、状态响应式断层、GET 对账模糊及侧栏权限缺失五大隐患，确认为最终实施事实源。
> **前置约束：** 后端/Runtime/引擎配套已就绪，当前进入 T06 前端接线阶段；B01 正式 CAS 双包发布前，自动开关在生产环境保持默认关闭，本地联调使用候选双包。

---

## 1. 架构全景与文件职责矩阵

原方案遗漏了关键的会话池化宿主层，导致组件事件无法冒泡。修复后的完整事件与状态流转矩阵如下：

| 文件路径 | 现有责任 | 本期必须增量与规范要求 |
|---|---|---|
| `apps/platform-web/src/services/threads/session.service.ts` | 会话底层通信服务 (`create`, `update`, `summarizeTitle` 等) | 1. 补齐 `TitleSummarizeRequest` / `TitleSummarizeResponse` 强类型 DTO；<br>2. 扩充 `create()` 签名支持顶层 `auto_title: true`（通过安全类型断言或底层 fetch 避免 SDK `ThreadCreateOptions` 类型校验报错）；<br>3. 扩展 `summarizeTitle(threadId, payload?, signal?)` 支持 auto 模式传参及取消信号。 |
| `apps/platform-web/src/modules/chat/composables/useChatSessionPool.ts` | 多会话池管理接口 (`PoolView`, `PoolEntry`) | **[关键补齐]** 在 `PoolView` 接口中增加 `onTitleUpdated?: (threadId: string, title: string) => void` 视图回调定义。 |
| `apps/platform-web/src/modules/chat/components/ChatSessionPool.vue` | 实际挂载并 Teleport `ChatSession` 组件的池化宿主 | **[关键补齐]** 在 `renderEntry` 渲染 `ChatSession` 时，监听 `@title-updated="handleTitleUpdated"` 并安全转发给当前 entry 的 `view.value?.onTitleUpdated`。 |
| `apps/platform-web/src/modules/chat/composables/useAutomaticThreadTitle.ts` | **(本次新增)** 自动标题生成的核心逻辑封装 | 严格遵循单一职责（≤ 150 行）。实现四重门禁检查、单飞防重、单次有界 GET 对账以及完全静默的异常保底。 |
| `apps/platform-web/src/modules/chat/components/ChatSession.vue` | 单会话 UI 组合根 | 1. 接入 `useAutomaticThreadTitle`；<br>2. 声明并触发 `emit("title-updated", title)`；<br>3. 严禁污染现有 transcript 渲染和运行状态机。 |
| `apps/platform-web/src/modules/chat/composables/useChatSession.ts` | 会话运行与消息状态机 | 保持现状。为组件提供响应式的 `accessThread`（用于读取 `auto_title_pending`）、`run`、`messages` 与 `send`。 |
| `apps/platform-web/src/modules/dear-agent/composables/useDearAgentSession.ts` | re-export `useChatSession` | 自动复用，不重复编写。 |
| `apps/platform-web/src/modules/chat/pages/ChatPage.vue` | 对话主页面、路由及侧边栏协调 | 1. 在 `attachView` 中接入 `onTitleUpdated`；<br>2. 维护 `threadEpochs`（用户手动改名/AI提炼时自增），拒绝迟到响应回滚；<br>3. 同步更新 `threads` 列表、当前激活标题及 `chatSessionStore` 缓存；<br>4. 侧栏 AI 按钮补齐 `comment + edit` 权限门禁。 |
| `apps/platform-web/src/modules/dear-agent/pages/DearAgentPage.vue` | Dear Agent 对话主页面 | 与 `ChatPage.vue` 保持同等行为和竞态守卫。 |
| `apps/platform-web/src/modules/chat/components/ChatThreadSidebar.vue`<br>`apps/platform-web/src/modules/dear-agent/components/DearAgentThreadSidebar.vue` | 侧栏历史列表与重命名/AI 提炼交互 | 修复 AI 提炼按钮门禁：从单纯检查 `edit` 升级为 `canWrite && threadCan(id, 'edit') && threadCan(id, 'comment')`。 |

---

## 2. 接口契约与 TypeScript 类型定义

### 2.1 请求与响应 DTO 规范

在 `apps/platform-web/src/services/threads/session.service.ts` 中明确定义并导出：

```typescript
export type TitleSummarizeMode = "auto" | "manual";

export interface TitleSummarizeRequest {
  mode?: TitleSummarizeMode;
  run_id?: string;
  messages?: Array<{
    role: "user" | "assistant" | "human" | "ai";
    content: string;
  }>;
}

export type TitleOutcome = "applied" | "skipped" | "degraded";

export type TitleSkippedReason =
  | "disabled"
  | "not_pending"
  | "not_first_round"
  | "run_not_ready"
  | "materials_missing"
  | "conflict";

export type TitleDegradedReason =
  | "model_unavailable"
  | "timeout"
  | "provider_failure"
  | "empty_output";

export type TitleOutcomeReason = TitleSkippedReason | TitleDegradedReason | null;

export interface TitleSummarizeResponse {
  thread_id: string;
  title: string;
  metadata?: Record<string, unknown> & {
    title?: string;
    auto_title_pending?: boolean;
  };
  outcome: TitleOutcome;
  reason: TitleOutcomeReason;
}
```

### 2.2 服务方法签名扩展

#### 1. `create` 方法：支持顶层 `auto_title: true`
在创建新普通会话时，无论后端开关是否开启，前端统一声明 `auto_title: true`，由后端根据当前全局开关裁决是否种下内部 seed 并返回只读投影 `metadata.auto_title_pending`。

```typescript
// 扩展创建选项以避免超过4个入参违反规范：
export interface CreateThreadOptions {
  graphId: string;
  agentId?: string;
  title: string;
  accessPolicy?: AccessPolicy;
  preview?: string;
  autoTitle?: boolean;
}

// 在 session.service.ts 中：
create: async (
  graphId: string,
  agentId: string | undefined,
  title: string,
  accessPolicy?: AccessPolicy,
  preview?: string,
  options?: { autoTitle?: boolean },
) => {
  // ... 既有 pendingThreadId 对账逻辑保持不变 ...

  // 构造请求 Payload，支持顶层 auto_title 投递：
  const bodyPayload = {
    graph_id: graphId,
    ...(options?.autoTitle ? { auto_title: true } : {}),
    metadata: {
      graph_id: graphId,
      agent_id: agentId,
      title,
      ...(preview ? { preview } : {}),
      ...(accessPolicy ? { access_policy: accessPolicy } : {}),
    },
  };

  // 通过客户端安全发送（兼容 SDK 与平台顶层参数）：
  return (client.threads.create as unknown as (opts: unknown) => Promise<ChatThread>)(bodyPayload);
}
```

#### 2. `summarizeTitle` 方法：支持 payload 与 AbortSignal
```typescript
summarizeTitle: (
  threadId: string,
  payload?: TitleSummarizeRequest,
  signal?: AbortSignal,
): Promise<TitleSummarizeResponse> => {
  const validId = assertValidThreadId(threadId);
  return read<TitleSummarizeResponse>(
    `/threads/${encodeURIComponent(validId)}/title/summarize`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload ?? {}),
      signal,
    },
  );
}
```
**严格约束：**
- 当 `mode === "auto"` 时，body **只能且必须**为 `{ mode: "auto", run_id: "<run_id>" }`。严禁携带 `messages` 字段（传 `messages: null` 也会被后端 400 校验拦截拒绝）。
- 当 `mode === "manual"` 或手动按钮调用时，传 `{}` 或由前端筛选的有界 `{ messages }`。

---

## 3. 核心 Composable 规范：`useAutomaticThreadTitle.ts`

新建文件：`apps/platform-web/src/modules/chat/composables/useAutomaticThreadTitle.ts`

### 3.1 关注点与输入契约
该 Composable 只负责单会话首轮的“尽力而为（best-effort）”标题升级，生命周期内仅触发至多一次有效请求。

```typescript
export interface UseAutomaticThreadTitleOptions {
  projectId: MaybeRefOrGetter<string | undefined>;
  threadId: MaybeRefOrGetter<string | undefined>;
  runStatus: MaybeRefOrGetter<string | undefined>;
  runId: MaybeRefOrGetter<string | undefined>;
  accessThread: MaybeRefOrGetter<ChatThread | undefined>;
  messages: MaybeRefOrGetter<readonly unknown[]>;
  visible?: MaybeRefOrGetter<boolean | undefined>;
  canWrite?: MaybeRefOrGetter<boolean>;
  isBusy?: MaybeRefOrGetter<boolean>;
  turnState?: MaybeRefOrGetter<string | undefined>;
  onTitleUpdated: (title: string) => void;
}
```

### 3.2 四项黄金触发门禁（必须全部满足）

1. **服务端 Seed 待消费判定：**
   `toValue(options.accessThread)?.metadata?.auto_title_pending === true`
   （从响应式的 `accessThread` 中实时提取；若已被用户手动改名或 seed 已消费，直接为 false，阻断执行）。
2. **已确认 Run Success：**
   `toValue(options.runStatus) === "success"` 且 `Boolean(toValue(options.runId))`。
3. **根图最终助手消息就绪：**
   - 消息列表中找到最后一条消息；
   - 消息角色为 `ai` 或 `assistant`；
   - 消息已包含非空纯文本正文（非仅推理链 `reasoning_content`，非未完成工具调用流）；
   - 无待决工具调用（`tool_calls` 为空）、无待审批（`hasPendingInterrupts` 为 false）、非 `stopping/stopped/timeout/error` 态。
4. **单飞与身份一致性：**
   - 校验当前 `projectId`、`threadId`、`runId` 与派发时完全一致；
   - 页面/实例未销毁，未处于后台失焦阻塞态（若处于隐藏态标记 `pendingCatchUp`，切回后单次补偿）。

### 3.3 状态机与容错处理流程

```text
[监听门禁满足]
       │
       ▼
[生成 requestKey: projectId:threadId:runId]
  -> 若与已请求/已处理 key 重复则忽略 (单飞)
       │
       ▼
[发起 POST /threads/{id}/title/summarize]
  带 AbortSignal; body: { mode: "auto", run_id }
       │
       ├─────────────────────────────────┐
       ▼ (200 OK)                        ▼ (HTTP 503 或 网络超时)
根据 outcome 分支处理:                     执行单次有界 (≤3s) GET 对账:
• applied:                                 const latest = await service.get(threadId);
  应用 response.title;                     • 若 latest.metadata.title 已更新:
  调用 onTitleUpdated(response.title)        调用 onTitleUpdated(latest.metadata.title)
• skipped (如 conflict):                   • 否则:
  使用 response.title (保持用户改名)         静默退出，保留原有规则标题
• degraded:
  保留现有规则标题                         ▼ (其他 4xx / 5xx)
       │                                  静默捕获，绝不弹窗报错，绝不重试
       ▼
[标记本地该轮完成，清空 abortController]
```

**关键原则：**
- **静默失败：** 自动标题属于辅助功能，任何网络错误、超时、5xx 或权限异常，**严禁向全局 toast 或控制台抛出未捕获错误**，静默保留原首消息规则标题。
- **不循环重试：** 单个 Run 仅尝试一次。遇到 503 `title_write_unconfirmed` 执行单次 GET 对账，对账后无论成功失败均标记为最终态，绝不轮询重试。

---

## 4. 架构接线与事件通道（消除组件断层）

### 4.1 会话池层打通 (`useChatSessionPool.ts` & `ChatSessionPool.vue`)

#### 1. `PoolView` 增加回调定义
在 `apps/platform-web/src/modules/chat/composables/useChatSessionPool.ts`：
```typescript
export type PoolView = {
  // ... 既有字段保持 ...
  onTitleUpdated?: (title: string, threadId?: string) => void;
};
```

#### 2. `ChatSessionPool.vue` 代理事件
在 `apps/platform-web/src/modules/chat/components/ChatSessionPool.vue` 的 `renderEntry` 函数中，为 `ChatSession` 补齐事件监听：
```typescript
h(ChatSession, {
  // ... 既有 props ...
  onTitleUpdated: (title: string) => {
    const currentThreadId = entry.threadId.value;
    const view = entry.view.value;
    if (currentThreadId && view?.onTitleUpdated) {
      view.onTitleUpdated(title, currentThreadId);
    }
  },
})
```

### 4.2 会话组合根接入 (`ChatSession.vue`)

在 `apps/platform-web/src/modules/chat/components/ChatSession.vue` 中：
1. `defineEmits` 增加：
   ```typescript
   const emit = defineEmits<{
     // ... 既有 emits ...
     "title-updated": [title: string];
   }>();
   ```
2. 引入并挂载 `useAutomaticThreadTitle`：
   ```typescript
   useAutomaticThreadTitle({
     projectId: () => props.projectId,
     threadId: () => session.threadId.value || props.threadId,
     runStatus: () => session.run.value?.status,
     runId: () => session.run.value?.run_id,
     accessThread: () => session.accessThread.value,
     messages: displayedMessages,
     visible: () => props.visible,
     canWrite: () => props.canWrite,
     isBusy: () => isSessionRunning.value,
     turnState: () => turnState.value,
     onTitleUpdated: (newTitle) => {
       emit("title-updated", newTitle);
     },
   });
   ```

### 4.3 页面层处理与竞态防护 (`ChatPage.vue` & `DearAgentPage.vue`)

在 `ChatPage.vue` 和 `DearAgentPage.vue` 中统一实现标题更新和防竞态逻辑：

```typescript
// 本地维护每个会话的 titleEpoch，防止用户手动操作被迟到的自动请求覆盖
const threadTitleEpochs = ref<Map<string, number>>(new Map());

function bumpTitleEpoch(threadId: string): number {
  const current = threadTitleEpochs.value.get(threadId) ?? 0;
  const next = current + 1;
  threadTitleEpochs.value.set(threadId, next);
  return next;
}

function handleTitleUpdated(newTitle: string, threadId: string) {
  if (!threadId || !newTitle.trim()) return;

  // 1. 同步侧栏列表
  const match = threads.value.find((t) => t.thread_id === threadId);
  if (match) {
    match.metadata = { ...match.metadata, title: newTitle.trim(), auto_title_pending: false };
    threads.value = [...threads.value];
  }

  // 2. 同步当前激活会话标题
  if (mountedThread.value === threadId || selectedEntry.value?.threadId.value === threadId) {
    // 触发 activeThreadTitle 重新计算
    touchLocalThread(threadId);
  }

  // 3. 同步全局缓存 Store
  chatSessionStore.patchSessionMetadata(activeProjectId.value, threadId, {
    title: newTitle.trim(),
    auto_title_pending: false,
  });
}

// 用户手动改名：递增 epoch
async function handleRenameThread(threadId: string, newTitle: string) {
  if (!canWrite.value || !threadCan(threadId, "edit") || !newTitle.trim()) return;
  bumpTitleEpoch(threadId);
  try {
    await service.value.update(threadId, { title: newTitle.trim() });
    handleTitleUpdated(newTitle.trim(), threadId);
  } catch (cause) {
    listError.value = cause instanceof Error ? cause.message : "重命名会话失败";
  }
}

// 用户手动点击侧栏 AI 提炼：递增 epoch 并检查双重权限
async function handleAiSummarizeTitle(threadId: string) {
  if (
    !canWrite.value ||
    !threadCan(threadId, "edit") ||
    !threadCan(threadId, "comment") ||
    summarizingThreadId.value
  )
    return;

  bumpTitleEpoch(threadId);
  summarizingThreadId.value = threadId;
  try {
    const res = await service.value.summarizeTitle(threadId, { mode: "manual" });
    if (res?.title) {
      handleTitleUpdated(res.title, threadId);
    }
  } catch (cause) {
    listError.value = cause instanceof Error ? cause.message : "智能提炼标题失败";
  } finally {
    summarizingThreadId.value = null;
  }
}

// 在 pool.attachView 中挂载：
detachView = pool.attachView(entry, {
  // ... 既有配置 ...
  onTitleUpdated: (title, tId) => {
    handleTitleUpdated(title, tId || entry.threadId.value || "");
  },
});
```

---

## 5. 侧栏按钮权限门禁一致性修复

在两个侧边栏组件中：
- `apps/platform-web/src/modules/chat/components/ChatThreadSidebar.vue`
- `apps/platform-web/src/modules/dear-agent/components/DearAgentThreadSidebar.vue`

定位 AI 提炼按钮的渲染门禁及点击事件，补齐 `comment` 权限检查：
```vue
<!-- 现有逻辑通常只检查 edit，修改为必须同时具备 edit 与 comment： -->
<button
  :disabled="!canWrite || !threadCan(thread.id, 'edit') || !threadCan(thread.id, 'comment') || isSummarizing(thread.id)"
  :title="
    !threadCan(thread.id, 'comment')
      ? '需要评论权限以使用 AI 提炼'
      : !threadCan(thread.id, 'edit')
        ? '需要编辑权限以更新标题'
        : 'AI 提炼标题'
  "
  @click.stop="emit('ai-summarize-title', thread.id)"
>
  ...
</button>
```

---

## 6. F01-F10 联合验收依据（必须覆盖并闭环）

实施完成后必须以此表格逐项执行 Vitest 单元测试与真实浏览器 Playwright E2E 验证：

| 编号 | 验证场景 | 预期测试行为与断言依据 | 对应实现代码位置 |
|---|---|---|---|
| **F01** | Chat / Dear Agent 新建普通会话首轮 Run 成功 | 会话初始展示 40 字规则标题；首轮 Run 成功且正文输出后，自动升级为简洁标题（≤10字）；刷新页面后保持新标题。 | `useAutomaticThreadTitle.ts`<br>`ChatPage.vue`<br>`DearAgentPage.vue` |
| **F02** | SSE 时序乱序容错 (lifecycle success 先到 / 最终正文 values 先到) | 无论先收到 Run success 还是先收到完整助手正文，均在两条件齐备后仅发起 1 次 HTTP 标题请求；不出现空标题或提炼中断。 | `useAutomaticThreadTitle.ts` 门禁聚合 |
| **F03** | 工具调用中、仅思考链 (reasoning-only)、审批中断、Stop、Error | 只要处于工具执行中、等待人工审批、思考中或非 success 终态，绝不触发自动标题；UI 保持正常交互。 | `useAutomaticThreadTitle.ts` 拦截守卫 |
| **F04** | 自动请求在途期间用户手动改名或手动触发 AI 提炼 | 用户手动改名优先；后端 CAS 拦截冲突返回 `skipped/conflict`；前端本地 Epoch 守卫丢弃迟到响应，界面绝不回滚标题。 | `ChatPage.vue`<br>`DearAgentPage.vue`<br>后端 CAS 机制 |
| **F05** | 双标签页、快速切换会话/项目/退出登录 | 前端单飞守卫生效，切换后旧请求结果自动丢弃；后端 CAS 确保最终数据库中仅持久化一个合法的自动结果。 | `useAutomaticThreadTitle.ts` (AbortSignal & Key 校验) |
| **F06** | 慢模型超时、503 `title_write_unconfirmed`、网络抖动 | 自动请求失败静默保留原规则标题，不阻塞主聊天发送、Stop 或审批；503 时执行单次 GET 对账，不陷入死循环。 | `useAutomaticThreadTitle.ts` (GET 对账逻辑) |
| **F07** | 纯附件消息、多文件上传、无正文图片输入 | 沿用后端针对 runtime_file 的本地命名保底，不无谓调用大模型，标题不暴露临时路径、hash 或 base64。 | 后端 T03 契约保障与前端静默承接 |
| **F08** | 编辑与评论权限分离场景 (仅有 edit 无 comment) | 侧栏手动 AI 提炼按钮呈 disabled 状态；若绕过前端强制调用，API 返回 403 局部权限拒绝，页面不退出全局登录。 | `*ThreadSidebar.vue`<br>`ChatPage.vue` 门禁 |
| **F09** | 历史旧 Thread、Fork 会话、多轮已存在对话 | 不产生自动生成；侧栏手动改名与 AI 提炼按钮正常可用；不会对历史数据进行批量扫描生成。 | 服务端 `auto_title_pending: false` 门禁 |
| **F10** | 1440px / 768px / 390px 视口响应式自适应 | 长标题、长英文单词及特殊字符在侧栏文本截断（ellipsis）正常，tooltip 悬停完整可读，移动端不挤出横向滚动条。 | 样式与侧栏布局检查 |

---

## 7. 质量门禁与发布边界

1. **质量门禁（必须全绿）：**
   - `pnpm test:run`（包含 `session.service.spec.ts`、`useAutomaticThreadTitle.spec.ts` 等定向单测）
   - `pnpm typecheck`（`vue-tsc --noEmit` 零报错）
   - `pnpm lint`（ESLint 零错误零警告）
   - `pnpm build`（生产构建打包成功）
2. **浏览器联调环境：**
   - 依赖本地双包候选：`/tmp/f07-title-candidate-20261009/v2/`；
   - 开启环境变量：`PLATFORM_API_TITLE_AUTO_ENABLED=true`（仅隔离测试环境）；
   - 正式 PyPI 发布（B01）解除前，主干生产配置保持 `false`。
