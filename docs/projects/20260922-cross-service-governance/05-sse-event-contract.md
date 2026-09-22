# 05 - SSE 事件格式契约

## 目标

定义从 runtime-service 产出 → platform-api 过滤/脱敏 → platform-web 消费的 SSE 流式事件格式，防止 runtime-service 侧格式变更时三端出现不一致问题。

> **本子专题以文档为主，需要代码研究支撑。当前为初始版本，实施前需补充 runtime-service 侧实际 SSE 产出格式的代码调研。**

## 当前问题

- platform-api 文档定义了脱敏规则（删除 `runtime_model_ref` 等敏感字段），但 runtime-service 侧实际产出的 SSE 事件 schema 没有文档
- 前端 `usePlatformChatStream.ts` 消费 SSE，但期望格式只散落在 TypeScript 类型文件中
- 三端无对齐文档，runtime-service 格式变更时影响范围不可预测

## 待调研内容（实施前完成）

实施前需要读取以下文件，补充本文档的"runtime-service 产出格式"部分：
- `apps/runtime-service/src/` 中的 SSE 相关输出代码
- `apps/platform-web/src/modules/chat/types/stream.ts`（或类似文件）
- `apps/platform-api/src/` 中的 SSE 透传/脱敏代码

## 已知部分（从现有文档提取）

### platform-api 对 SSE 的处理规则（已确认）

**必须删除的字段：**
- `runtime_model_ref`（模型凭据引用）
- 内部委托 token
- API Key 原文

**已知的 SSE 协议约定（platform-api 侧）：**
- 授权和上游状态校验在发送 HTTP 200 前完成（不允许 200 后伪装前置失败）
- 断开 SSE 连接只关闭订阅，取消需显式调用 `POST /threads/{t}/runs/{r}/cancel`
- `cancel_on_disconnect=true` 当前被拒绝

### platform-web 消费侧约定（从 playbook 提取）

**LangGraph SDK 提交契约（冻结范式）：**
```js
useStream().submit(messages, {
  context: { model_id, temperature, max_tokens, enable_tools, tools },
  config: { recursion_limit },
  config.configurable: { thread_id, checkpoint_id }
})
```

**消费行为约定：**
- 发送 → `run.start` 只产生一次；ACK 后清空草稿
- 审批 resume：按 interrupt ID 映射
- 取消：前端 `useStream.stop()` + 显式 `client.runs.cancel()`（两步都要）
- 历史 checkpoint：只在用户主动打开时读取，不覆盖实时消息
- 禁止流式更新强制抢滚动焦点

## 任务拆分

### Task 5.1: 调研 runtime-service 实际 SSE 产出格式
- **改动内容：** 读取 runtime-service 中 SSE 相关输出代码，整理实际事件类型和 schema
- **代码位置：** `apps/runtime-service/src/` → SSE/stream 相关代码
- **预期结果：** 补充本文档的"runtime-service 产出格式"章节
- **验证项：** 文档中的格式与代码实现一致
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

### Task 5.2: 整理 platform-web 期望的 SSE 消费格式
- **改动内容：** 读取 `src/modules/chat/types/` 和 `usePlatformChatStream.ts`，整理前端期望接收的事件结构
- **代码位置：** `apps/platform-web/src/modules/chat/`
- **预期结果：** 补充本文档的"platform-web 消费格式"章节
- **验证项：** 文档中的格式与 TypeScript 类型定义一致
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

### Task 5.3: 创建 SSE 事件格式契约文档
- **改动内容：** 基于 5.1 和 5.2 的调研结果，创建 `docs/standards/sse-event-contract.md`
- **代码位置：** `docs/standards/sse-event-contract.md`（新建）
- **预期结果：** 三端有对齐的 SSE 格式参考文档，runtime-service 变更时能快速评估影响范围
- **验证项：** 文档覆盖所有已知的事件类型，platform-api 的脱敏规则明确写入
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

## 验证要求与记录

### 验证要求
- [ ] 文档中的格式与三端代码实现一致
- [ ] platform-api 的脱敏规则在文档中明确体现
- [ ] 包含"变更影响评估"指南（runtime-service 修改某类事件时如何判断前端是否受影响）

### 验证记录
<!-- 实施后填写 -->

## 状态

规划中（需要代码调研支撑，建议在 01/04 完成后开始）
