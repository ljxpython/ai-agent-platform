# 04 Platform Web 图片与图表交互体验实现记录

## 1. 任务概述

按照前端交互方案 [07-platform-web-image-experience.md](../07-platform-web-image-experience.md) 与消息契约 [04-platform-image-contract.md](../04-platform-image-contract.md)，实现 Platform Web 的 Showcase 图片上传、安全展示、审批与图表恢复体验：
1. 实现 `images.service.ts`：图片上传与鉴权获取 Blob 服务、sha256 计算与 `RuntimeImageRef` 结构校验；
2. 封装 `ThreadImage.vue`：全生命周期管理 Blob URL（创建、清理、撤销），支持缩放预览、下载、失败优雅降级；
3. 扩展 `chat-content.ts`：增加图片附件元数据状态管理，实现 `createRuntimeImageTextBlock` 将上传后的图片转为无 Base64 的文本块契约；
4. 增强 `transcript.ts`：从消息流、工具产物与父任务输出中解析 `runtime_images`，并针对图表子任务提供基于正则的弱引用历史恢复；
5. 在 `useChatAttachments.ts` 中拦截 Showcase 场景下的动态 GIF 并给出明确阻止提示；
6. 在 `useChatSession.ts` 中打通 `send`（新线程自动先建线程->上传图片->提交流式执行）、`queueMessage`（同步/异步平滑调度）与 `fork`（同线程历史分叉预处理）三个入口；
7. 优化 `ApprovalPanel.vue`：对 `generate_image` 工具调用呈现清晰的中文审批卡片与参数确认；
8. 在 `ChatMessageList.vue`、`MessageContent.vue`、`ToolResult.vue`、`SubagentCard.vue` 与 `ChatSession.vue` 中透传 `projectId` 与 `threadId`，实现用户消息、工具产物、子任务图表图片的多端无缝渲染。

## 2. 涉及文件与改动明细

- `apps/platform-web/src/services/threads/images.service.ts`:
  - 导出 `RuntimeImageRef` 与 MIME 白名单；
  - 实现 `isValidImageRef`：严格校验 `version: 1`、路径白名单（`/workspace/{uploads,generated,charts}/`）、MIME、正数大小与 64 位哈希；
  - 实现 `calculateFileSha256`：使用 Web Crypto API 计算上传文件的 sha256 散列；
  - 实现 `uploadThreadImage`：PUT 原始文件二进制流至 Platform API；
  - 实现 `getThreadImageBlob`：带 `x-project-id` 请求图片二进制 Blob。
- `apps/platform-web/src/services/threads/images.service.spec.ts`:
  - 新增专属单元测试，覆盖校验器正反例、哈希计算、上传参数与读取响应。
- `apps/platform-web/src/modules/chat/components/ThreadImage.vue`:
  - 响应式加载图片 Blob 并通过 `URL.createObjectURL` 转换为展示 URL；
  - 侦听路径变化或组件卸载时立即调用 `URL.revokeObjectURL` 杜绝内存泄漏；
  - 提供加载骨架、错误提示（支持一键重试）、图片缩放预览弹窗（Teleport 到 body）与本地另存下载。
- `apps/platform-web/src/utils/chat-content.ts`:
  - `ChatImageAttachmentBlock` 扩展 `file?: Blob` 与 `uploadStatus?: 'pending' | 'uploading' | 'uploaded' | 'error'`；
  - 实现 `createRuntimeImageTextBlock` 与 `isRuntimeImageTextBlock`：将附件转换为包含 `extras.runtime_image` 的纯文本块，确保消息体中零 Base64。
- `apps/platform-web/src/modules/chat/transcript.ts`:
  - `ContentItem` 扩展 `imageRef?: RuntimeImageRef`；
  - `contentItems` 自动提取 `block.extras.runtime_image` 并映射为 `image` 块；
  - 导出 `extractRuntimeImages`：递归提取 artifact / structured_content / extras 中的有效图片引用；
  - 导出 `extractChartWeakImageRefs`：以正则 `/\/workspace\/charts\/[a-f0-9]{32}\.(png|jpg|webp)/g` 从模型文本输出中恢复弱引用图片。
- `apps/platform-web/src/modules/chat/transcript.test.ts`:
  - 新增图片引用提取与图表弱引用恢复的单元测试用例。
- `apps/platform-web/src/modules/chat/composables/useChatAttachments.ts`:
  - 接收 `options.graphId`；在 Showcase 场景下对 `image/gif` 文件直接阻止添加并提示“Showcase 场景暂不支持 GIF 动图”。
- `apps/platform-web/src/modules/chat/composables/useChatSession.ts`:
  - 增加 `prepareMessageAttachments` 预处理流程；
  - 针对无待上传附件的常规场景保持完全同步返回，保障原有 `queueMessage` 同步生成 `pendingMessage.value` 的生命周期与单测；
  - 针对包含文件附件的场景，并发执行计算 sha256 与上传，转换为 `RuntimeImageRef` 文本块；
  - 在 `send`、`queueMessage`、`fork` 统一复用该预处理逻辑。
- `apps/platform-web/src/modules/chat/components/ApprovalPanel.vue`:
  - 对 `generate_image` 提供中文人机交互审批：“生成图片需要确认”，格式化呈现提示词（Prompt）与尺寸说明。
- `apps/platform-web/src/modules/chat/components/SubagentCard.vue`:
  - 计算属性 `runtimeImages` 结合 `extractRuntimeImages` 与 `extractChartWeakImageRefs`；
  - 展开结果下方渲染 `ThreadImage`，透传 `projectId` 与 `threadId`。
- `apps/platform-web/src/modules/chat/components/ToolResult.vue`:
  - 从 `tool.artifact` 提取图片并在展开区域渲染 `ThreadImage`；透传 `projectId` 与 `threadId` 至 `SubagentCard`。
- `apps/platform-web/src/modules/chat/components/ChatMessageList.vue`:
  - props 接收 `projectId` 与 `threadId`，透传给所有 `MessageContent` 与 `ToolResult`。
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`:
  - 透传 `projectId` 与 `session.threadId.value || threadId` 至 `ChatMessageList`。

## 3. 验证结果

- 单元测试：`pnpm test:run` 全部通过（43 个测试文件，123 个用例全部 PASS，含图片服务与 transcript 新增用例）。
- 类型检查与构建：`pnpm build`（`vue-tsc --noEmit && vite build`）零 TS 错误，生产打包顺利完成。
