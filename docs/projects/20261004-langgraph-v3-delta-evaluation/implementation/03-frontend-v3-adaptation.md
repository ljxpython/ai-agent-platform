# 前端 v3 消费适配与防洪加固实施记录

## 改动时间
2026-10-04

## 相关任务
- Task 2.4：前端 v3 消费适配与防洪加固

## 改动文件
- `apps/platform-web/src/modules/chat/run-actions.ts`
- `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts`
- `apps/platform-web/src/modules/chat/run-actions.test.ts`
- `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.spec.ts`

## 具体改动

### 1. `platformCommand` 支持 `version` 白名单校验与透传
**位置：** `apps/platform-web/src/modules/chat/run-actions.ts:25-35`

**改动内容：**
在 `platformCommand` 解析 `run.start` 参数时，提取并校验 `version` 参数。若显式传入，必须为 `"v2"` 或 `"v3"`；传入非法版本直接抛出明确错误 `不支持的运行版本`。这使得前端在调试或回滚场景下具备显式选择 `version: "v2"` 的能力，缺省时不传则由服务端统一注入默认 `v3`。

**测试：**
在 `run-actions.test.ts` 中新增单元测试：
- `validates and allows explicit version v2 and v3 in platformCommand, rejects invalid versions`

### 2. `useTranscriptMessages` 防御 v3 `values` 膨胀与流式推理保护
**位置：** `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts:40-68`

**改动内容：**
针对 v3 下每帧 `values` 膨胀约 60 倍（~20KB/帧）的性能问题：
- 在流式运行中（`stream.isLoading.value === true`），若到达的 `values` 消息总条数未变、首尾消息 ID 一致且尾部 tool_calls 数量一致，判定为高频重复的 step 快照，跳过无谓的 `coerce(value.messages)` 全量深拷贝与响应式轰炸。
- 保护 `liveReasonings`：流式中途避免被重复的中间 values 帧误清空，确保思考卡片在逐 token 输出时不发生闪烁。
- 终态完备水合：当流结束（`!stream.isLoading.value`）或新消息追加时，完整水合最终 snapshot 并清理临时 live 状态。

**测试：**
在 `useTranscriptMessages.spec.ts` 中新增单元测试：
- `debounces redundant values frames during live stream and protects live reasoning until final hydration`

## 验证
- [x] 单元测试通过：
  - `run-actions.test.ts`：5 passed
  - `useTranscriptMessages.spec.ts`：9 passed
  - `useChatSession.spec.ts`：24 passed
  - `transcript.test.ts`：10 passed
- [x] 类型检查通过：`vue-tsc --noEmit`（0 errors）
- [x] Lint 检查通过：`eslint`（0 errors, 25 warnings 存量告警）
- [x] 生产打包通过：`pnpm build`（成功产出 dist）
