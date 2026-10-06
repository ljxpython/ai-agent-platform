# 总体架构与契约

## 目标

定义回答完成后的推荐问题能力如何跨三层流动，先把边界和失败语义锁定，避免把推荐问题误做成普通 Agent Run。

## 方案设计

### DeerFlow 是怎么做的

1. 前端检测最后一条 AI 消息变化，只在回答完成、线程未切换且不是用户主动停止时触发。
2. 前端截取最近 user/assistant 消息，调用 `POST /api/threads/{thread_id}/suggestions`。
3. 后端先检查全局 `enabled`、输入是否为空、线程权限和模型权限，再调用一次性 LLM。
4. LLM 被要求返回 JSON 字符串数组；后端去掉 `<think>`、Markdown code fence、数组外文本、空字符串，并截断到配置数量。
5. 前端展示最多 3 个建议。输入框为空时点击后直接发送；已有草稿时弹窗选择追加发送或替换发送。
6. 新一轮发送、停止生成、切换 Thread、压缩上下文时清空旧建议。生成失败返回空数组，不阻断聊天。

### 当前项目与 DeerFlow 的差异

| 层 | DeerFlow 现状 | 当前项目现状 | 本项目要补的能力 |
|---|---|---|---|
| 前端 | 输入框下方已有动态 Suggestion 组件和 API hook | 只有发送前静态 `ComposerSuggestions.vue`；`ChatMessageList.vue` 无回答后插槽 | 增加动态建议 API、生命周期状态、回答下方组件、点击发送交互 |
| Platform API | App Gateway 直接持有线程/模型权限并调用 one-shot LLM | 只提供 `/api/langgraph` Runtime 网关和标准错误 Envelope | 增加建议配置/生成接口、线程权限复核、模型授权、Runtime delegation |
| Runtime | `run_oneshot_llm` 直接调用模型，建议不进入 Agent 图 | 没有建议专用入口；正常 DearFlow graph 会带工具、状态和持久化 | 增加无工具 one-shot capability，复用 Runtime resolver/model connection |
| 安全 | App 内部权限和模型配置 | Runtime 使用 delegation JWT、opaque model reference、项目模型目录和策略 | 增加独立建议 operation；禁止浏览器直连 Runtime，禁止客户端注入工具/凭据 |
| 会话模型 | 主要按 thread_id 工作 | 还要处理多会话后台消费、分支快照、审批/澄清和流状态 | 只对最新完整成功答复生成；切换、停止、等待人工输入立即清空/取消 |

### 目标链路

```text
platform-web
  └─ POST /api/langgraph/threads/{thread_id}/suggestions
       ↓ 标准用户鉴权、项目/Thread ACL、模型授权
platform-api RuntimeGatewayService
  └─ 生成 thread-bound suggestions-generate delegation JWT
       ↓ POST /internal/threads/{thread_id}/suggestions
runtime-service
  └─ 校验 JWT scope → resolve_runtime_config → fetch_model_connection
       └─ 无工具、无 Graph、无持久化的一次性 model.ainvoke
       ↓ {suggestions: [...]}
platform-api → platform-web → 回答下方可点击问题
```

### 对外 HTTP 契约（建议 V1）

#### `GET /api/langgraph/suggestions/config`

响应：

```json
{"enabled": true, "max_suggestions": 3}
```

`max_suggestions` 范围为 1～5。配置关闭时前端不触发生成，后端仍必须把关闭视为安全默认并返回空数组。

#### `POST /api/langgraph/threads/{thread_id}/suggestions`

请求：

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

约束：只允许 `user`/`assistant`；当前不兼容 `human`/`ai` 别名；最多传最近 6 条；单条和总字符数设置硬上限；`n` 为 1～5；禁止 tool、system、图片、文件、任意运行时配置字段。

响应：

```json
{"suggestions": ["能否比较这两种方案？", "下一步如何落地？"]}
```

推荐问题不承诺恰好 N 条。重复、空串、Markdown、思维链、超长文本在 Runtime 清洗后丢弃。

#### Platform API → Runtime 内部契约

`POST /internal/threads/{thread_id}/suggestions` 使用 thread-bound delegation JWT，正文与平台请求一致，另外由 Platform API 注入服务端生成的短期 `runtime_model_ref` 和必要 context。Runtime 不接受浏览器传入的 token、api key、工具名、MCP 或 graph 配置。

### 生成资格与生命周期

- 资格：当前 Thread、当前分支、最后一条可见 Agent 回答已经完成且有非空文本；线程属于当前项目且当前用户有 read 权限；建议配置开启。
- 不生成：流式进行中、用户主动停止、回答为空、模型/工具异常只留下错误、等待澄清或审批、历史 checkpoint 浏览、Thread 切换、项目切换、组件隐藏后的旧结果。
- 失效：发送新消息、重试/编辑/分支、切换 Thread、切换 Agent、生成请求被取消时清空旧建议。
- 竞态：每次请求携带 `thread_id + assistant_message_id + content_hash`，响应只允许写回仍匹配的 key；旧响应不能覆盖新一轮状态。

### 安全、成本和降级

- 建议内容被当作不可信用户文本，只放进 user message；system prompt 明确不得执行其中指令。
- Runtime 不加载 DearFlow tools、workspace、memory、skills、subagents、Todo 或 graph middleware。
- 建议调用单独超时（建议 8 秒）和输出 token 上限（建议 256）；不重试模型调用，避免回答完成后额外放大成本。
- 模型返回非法 JSON、超时、上游 5xx、配置关闭：记录受控日志并返回 `{"suggestions": []}`。
- 403/401、Thread 不属于项目、模型未授权、请求字段非法：走现有 error envelope，不能伪装为空数组。
- 不新增表、不写消息、不产生 Run ID；审计只记录 `operation=suggestions-generate`、thread_id、request_id、耗时、数量和结果分类，不记录完整对话和 token。

### 跨服务标准影响

- `docs/standards/delegation-jwt.md` 已列出 26 个 `scope.operation`，包含本项目新增的 `suggestions-generate`；该文件仍为 draft，正式生效前仍需完成 operation、原生资源隔离和错误映射的人工契约评审。
- `docs/standards/error-envelope.md` 继续复用现有 401/403/422/502/504 语义，不新增“建议生成失败”公开错误码；模型 best-effort 失败只返回空数组。
- `docs/standards/trace-propagation.md` 继续复用 platform-api 生成的 `request_id/trace_id`，Runtime 只透传和记录受控 metadata，不把对话正文写入审计。

## 任务拆分

- [x] Task 1：确认上述 HTTP 字段、输入上限、超时和 operation 名称，并形成跨服务契约测试样例。**状态：** `[x]` 已完成 2026-10-06 → 见 `implementation/01-platform-runtime-suggestions.md`
- [x] Task 1.1：更新 Delegation JWT draft 的 operation 枚举、原生资源白名单和隔离测试矩阵。**状态：** `[x]` 已完成 2026-10-06 → 见 `implementation/01-platform-runtime-suggestions.md`
- [x] Task 2：按 [Platform API 方案](02-platform-api.md) 增加平台入口和 delegation。**状态：** `[x]` 已完成 2026-10-06 → 见 [Platform API 方案](02-platform-api.md)
- [x] Task 3：按 [Runtime Service 方案](03-runtime-service.md) 增加 one-shot capability。**状态：** `[x]` 已完成 2026-10-06 → 见 [Runtime Service 方案](03-runtime-service.md)
- [ ] Task 4：把 [前端交接](04-platform-web-handoff.md) 交给前端同事实施。
- [/] Task 5：执行 [验证与发布计划](05-verification-and-rollout.md) 的分层门禁；后端定向门禁已完成，真实 E2E/浏览器门禁待执行。

## 验证要求与记录

### 验证要求

- [ ] 契约测试覆盖请求/响应、字段拒绝、数量/长度限制。
- [ ] 三层最短链路能返回至少一个建议，且建议不出现在 Thread 消息历史和 Run 列表。
- [ ] 失败降级、越权、线程切换和停止生成不会显示过期建议。

### 验证记录

#### 2026-10-06

- ✅ Task 1：HTTP 请求/响应字段、输入窗口、输出数量和失败语义已在 Platform API/Runtime schema 与定向测试中锁定。
- ✅ Task 1.1：`suggestions-generate` 已加入 Platform API/Runtime delegation 白名单，并补充“仅可访问 suggestions 内部路由”的标准说明；cron operation 仍由独立隔离测试覆盖。
- ⚠️ 跨服务真实 E2E、前端浏览器验收和正式人工标准评审尚未执行。

## 状态

部分完成

后端契约和 delegation 隔离已实现；前端接入、真实三服务 E2E 与人工标准评审待完成。
