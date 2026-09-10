# 落地：Agent 一键同步、流式配置补齐、清除特判与基线修复

## 改动时间
2026-09-09

## 相关背景与任务
1. 在 `/workspace/assistants` 新增一键【同步后端 Agent】（方案二）：解决新建 Agent 页面 Graph ID 为空置灰死锁，自动刷新图谱并将后端 Agent 自动批量导入到当前项目。
2. 拆除炸弹 2：在前端消息提交链路中注入 `streamSubgraphs: true` 与 `streamMode: ['values', 'updates', 'messages']`。
3. 清除特判硬编码：重构 `stream-messages-to-ui.ts`，消除写死的 `showcase_demo`、`implementor_subagent` 等 Agent 名称，实现通用子智能体名称显示。
4. 修复后端基线单测：更新 `test_r0_baseline.py` 中关于生产图谱的断言，纳入 `showcase_demo`。

## 改动文件
- `apps/runtime-service/tests/test_r0_baseline.py`
- `apps/platform-web/src/modules/chat/stream-messages-to-ui.ts`
- `apps/platform-web/src/modules/chat/composables/platform-chat-stream/actions.ts`
- `apps/platform-web/src/modules/chat/composables/platform-chat-stream/types.ts`
- `apps/platform-web/src/modules/assistants/pages/AssistantsPage.vue`
- `apps/platform-web/src/modules/assistants/pages/AssistantCreatePage.vue`

## 具体改动与理由
1. **`test_r0_baseline.py`**：将生产注册图谱断言与 `langgraph.json` 对齐为 `["reference_agent", "workflow_demo", "showcase_demo"]`。
2. **`stream-messages-to-ui.ts`**：消除多重分支特判，统一按 `**[${name}]**` 渲染 AI 消息发送者标识。
3. **`actions.ts` & `types.ts`**：提交 run 时显式携带 `streamMode: ['values', 'updates', 'messages']` 与 `streamSubgraphs: true`，穿透子图推流。
4. **`AssistantsPage.vue`**：新增【同步后端 Agent】按钮，调用刷新 operation 后拉取图谱与当前助手差集，自动调用 `createAssistant` 进行补齐并 Toast 提示。
5. **`AssistantCreatePage.vue`**：在 Graph ID 旁常驻【同步后端 Graph】操作按钮，选项为空时提示引导，消除死锁。

## 验证结果
- 前端 `vue-tsc --noEmit`：0 error
- 前端 `vitest run`：41 个测试文件 146 passed 全部通过
- 后端 `pytest tests`：213 passed, 0 failed 全部通过
- 后端 `pytest test_showcase_demo.py`：9 passed 全部通过
