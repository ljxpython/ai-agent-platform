# 平台助手支持多渠道模型选择与切换（对齐 ChatModelSelector）

## 背景

用户在本地部署使用平台助手时，由于默认绑定的 `deepseek-v4.1-flash` 上游网关源站卡死超时（Cloudflare 524），且平台助手抽屉未提供模型切换入口，导致助手出现 SSE 空闲超时报错且无法手动切换为其他可用模型。为主对话区与平台助手提供一致的模型选择体验，需要在平台助手的输入栏中直接复用现有的 `ChatModelSelector` 组件。

## 改动内容

1. **Store 状态与模型加载扩展 (`usePlatformAssistantStore.ts`)**：
   - 增加 `selectedModelId`、`availableModels` 与 `modelsLoading` 状态，支持本地 `localStorage` 记住偏好模型并在模型失效时防呆回退。
   - 扩展 `currentModelId`、`defaultModelId` 与 `defaultModelName` 等 Getters，保持与主会话选择器数据契约一致。
   - 在 `ensureBootstrap` 成功获取绑定项目后，自动调用 `loadProjectModelBundle` 加载当前项目下可用模型。
2. **输入栏模型选择器集成与运行态可输入优化 (`AssistantComposer.vue`)**：
   - 引入 `ChatModelSelector` 并接收 `models`、`selectedModelId`、`defaultModelId`、`defaultModelName` 及 `projectId` 等属性。
   - 在底部按钮区（发送按钮左侧）挂载模型选择胶囊，支持渠道分组展示、名称搜索与一键切换。
   - 拔除 `textarea` 上粗暴的 `isRunning` 禁用条件（仅在真实待审批 `awaiting_review` 或加载中时禁用），支持用户在 Agent 思考与流式输出期间随时输入并保存下一轮提问草稿；按 Enter 防误触阻断发送并完整保留草稿。
3. **视图状态接线 (`AssistantChatView.vue`)**：
   - 将 Store 中的模型列表与选择事件双向绑定到 `AssistantComposer`，挂载时自动检查并补齐模型数据。
4. **单测增强与类型验证**：
   - 增加 `usePlatformAssistantStore.spec.ts` 与 `AssistantComposer.spec.ts` 针对模型选择、事件派发、默认回退与运行期允许编辑草稿的单测覆盖（全量 38 项单测 100% 通过）。
   - `vue-tsc --noEmit` 0 错误。

## 涉及文件

- `apps/platform-web/src/modules/platform-assistant/stores/usePlatformAssistantStore.ts`
- `apps/platform-web/src/modules/platform-assistant/components/AssistantComposer.vue`
- `apps/platform-web/src/modules/platform-assistant/components/AssistantChatView.vue`
- `apps/platform-web/src/modules/platform-assistant/stores/usePlatformAssistantStore.spec.ts`
- `apps/platform-web/src/modules/platform-assistant/components/AssistantComposer.spec.ts`
