# F05：前端交接（修订版）

> 本文为人工评审与技术审查后的实装方案。针对前期交接中存在的“错误提取漏查 code”、“轨迹组件脱节”、“i18n 冗余”以及“联调环境测完即销毁”等缺陷进行了彻底修正与细化。
> 整体策略采用分阶段推进：**先完成 F01 离线代码重构与单测闭环，再满足前置条件后推进 F02 浏览器全栈联合验收**。

## 1. 前端设计原则与职责边界

1. **核心原则**：**前端只消费后端已经冻结的错误契约，不在浏览器重复实现脱敏逻辑。**
2. **纯展示消费**：策略由 Runtime 部署环境变量控制，浏览器不提供配置开关、密钥输入表单、检测器选择或客户端 PII 扫描。
3. **保持事实真相**：用户输入、历史记录、附件和工具回执均为原始事实；模型回答可能带 `[EMAIL_...]` 等占位符，UI 绝不逆向还原，也不在前端建立原值↔占位符映射表。
4. **拒绝冗余与过度设计**：
   - **不修改 i18n 语言包**：Chat 模块与 Runtime 错误常量统一在 TypeScript 内部维护，未接入 vue-i18n，不引入无用翻译文件（遵循 YAGNI 原则）。
   - **轨迹视图保持原生事实（方案 A）**：步骤详情忠实记录实际执行结果，被阻断的 Assistant 步骤保持 `status: "error"`，不强行注入模拟的 PII 错误对象；全局隐私阻断原因统一由 Chat 顶部状态栏与横幅承载，避免侵入轨迹核心契约。

## 2. 核心代码接入位置

| 位置 | 改造内容 | 详细设计要求 |
|---|---|---|
| `apps/platform-web/src/modules/chat/composables/useChatSession.ts` | 重构 `extractRuntimeModelErrorMessage` 提取函数 | 修复现存函数只匹配 `message` 导致无法解析对象错误码的致命缺陷；严格按优先级提取 `code`，匹配冻结码；支持对象、字符串与 HTTP Envelope。 |
| `apps/platform-web/src/modules/chat/components/ChatSession.vue` | 错误计算属性与交互防线对齐 | 确保 `streamError` 复用统一提取逻辑；遭遇隐私阻断时不展示误导性的“恢复连接”按钮；保留草稿与上下文。 |
| `apps/platform-web/src/utils/http-error.ts` | 错误解包与 Envelope 规范复用 | 直接复用现有 `unwrapPlatformHttpError` 与 `extractPlatformHttpError`，解包后暴露标准 `code` 属性。 |
| `apps/platform-web/src/modules/chat/trajectory/trajectory-adapter.ts` | 验证失败步骤标记 | 验证当 Run 失败或 `hasError` 时末尾步骤标记为 `status: "error"`；不泄漏任何未脱敏异常堆栈。 |
| Dear Agent 现有 Chat 页面 | 复用共享组件验证 | Dear Agent 深度复用 `ChatSession` 底层，确认共享逻辑天然生效，不单独增加特殊处理分支。 |

## 3. 实装契约与错误提取技术规范

### 3.1 契约定义

- **唯一业务码**：`runtime.privacy.redaction_failed`
- **固定说明文案**：`隐私保护处理失败，本次模型请求未发送。`

### 3.2 可信错误槽位输入形态

必须且仅在以下**可信错误槽位**（`stream.error`、`session.error`、Run failure cause、HTTP 502 Envelope）中识别错误，**绝不在普通消息列表（`messages`）中进行文本模糊搜索**：

1. **实时 Lifecycle 错误对象**（SSE / Stream）：
```json
{
  "type": "RuntimePrivacyError",
  "code": "runtime.privacy.redaction_failed",
  "message": "隐私保护处理失败，本次模型请求未发送。"
}
```

2. **持久化重放字符串**（Task / Checkpoint 错误码）：
```text
runtime.privacy.redaction_failed
```

3. **握手前 HTTP 502 错误 Envelope**（Runtime 500 经 Platform API 转换）：
```json
{
  "error": {
    "code": "runtime.privacy.redaction_failed",
    "message": "隐私保护处理失败，本次模型请求未发送。",
    "details": [],
    "extra": {
      "upstream": "langgraph",
      "upstream_status_code": 500
    }
  },
  "request_id": "req-example"
}
```

### 3.3 提取逻辑算法规范

重构 `extractRuntimeModelErrorMessage(cause: unknown): string | null` 如下：

1. **空值守卫**：若 `!cause` 直接返回 `null`。
2. **纯字符串形态**：若 `typeof cause === "string"`：
   - 若等于 `"runtime.privacy.redaction_failed"`，返回固定文案 `"隐私保护处理失败，本次模型请求未发送。"`。
   - 若命中 `RUNTIME_MODEL_ERROR_MESSAGES[cause]`，返回对应的白名单文案。
3. **对象形态优先解析 `code`**：
   - 提取候选码 `candidateCode`：
     优先读取 `raw.code`，若无则读取 `raw.error?.code`，若无则读取 `raw.cause?.code`。
   - 若 `candidateCode === "runtime.privacy.redaction_failed"`，**立刻返回固定文案**。
   - 若 `candidateCode` 命中 `RUNTIME_MODEL_ERROR_MESSAGES[candidateCode]`，返回白名单映射文案。
4. **回退解析 `message`（兼容旧模型错误抛出习惯）**：
   - 提取候选消息 `candidateMsg`：
     读取 `raw.error?.message` 或 `raw.message`。
   - 若 `candidateMsg` 命中 `RUNTIME_MODEL_ERROR_MESSAGES[candidateMsg]`，返回对应文案。
5. **未命中**：返回 `null`，交由通用错误处理器处理。

## 4. 界面展示与交互行为准则

| 场景 | 界面行为要求 |
|---|---|
| 正常对话 / 脱敏功能未开启 | 维持完全一致的既有行为，无任何额外徽章、提示或布局位移。 |
| 脱敏功能开启，用户发送包含 PII 的文本 | 用户界面始终展示用户原本输入的真实文本；助手回复中可能包含 `[EMAIL_xxx]` 占位符，UI 照常渲染，不逆向还原。 |
| 主模型隐私保护阻断 | 顶部状态栏与横幅展示固定文案：“`隐私保护处理失败，本次模型请求未发送。`”；**完整保留输入框草稿、原始用户消息、已挂载附件及已完成的工具产物**；不宣称“整个 Run 一次模型都没调用”或“所有副作用已回滚”。 |
| 交互防线（禁止误导重试） | 隐私错误横幅上**严禁提供“恢复连接”或“忽略隐私继续发送”按钮**（阻断非网络偶发故障，重试毫无意义）；用户修改草稿中的敏感数据后可重新正常提交。 |
| 安全防线（无破坏性副作用） | 遭遇隐私错误时，**绝不退出登录、绝不清空项目/Thread 权限、绝不自动重建 Thread、绝不自动使用新 key 重试**。 |
| 用户消息正文包含错误码（负例） | 仅作为普通文本聊天气泡渲染，绝不触发系统错误横幅，绝不误判为系统故障。 |
| 切换 Thread / 项目 | 错误状态与当前 Thread 生命周期严格绑定，切换后错误原因绝对不可跨 Thread 串扰。 |

---

## 5. 分阶段实施任务规划

### 阶段一：F01 错误消费与前端离线闭环（当前实施重点）

- **任务目标**：完成前端代码重构与全面的单元测试验证，达到 100% 离线自包含绿色状态。
- **涉及文件**：
  - `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
  - `apps/platform-web/src/modules/chat/components/ChatSession.vue`
  - `apps/platform-web/src/modules/chat/composables/useChatSession.spec.ts`
  - `apps/platform-web/src/modules/chat/trajectory/trajectory-adapter.spec.ts`
- **单测覆盖清单（至少 7 项关键场景）**：
  1. `[Lifecycle 对象]`：传入 `{ type: "RuntimePrivacyError", code: "runtime.privacy.redaction_failed", message: "..." }`，验证输出固定文案。
  2. `[持久化字符串]`：传入字符串 `"runtime.privacy.redaction_failed"`，验证输出固定文案。
  3. `[HTTP 502 Envelope]`：传入解包后的 HTTP 502 错误对象（包含嵌套 `error.code`），验证输出固定文案。
  4. `[正文负例防误判]`：普通用户消息或工具结果内容包含 `"runtime.privacy.redaction_failed"` 字符串时，验证 `session.error` 保持为空，界面不报错。
  5. `[上下文切换隔离]`：Thread A 发生隐私阻断后切换到 Thread B，验证 Thread A 的错误不会串扰至 Thread B。
  6. `[数据防线保留]`：模拟阻断后，验证用户输入草稿未被清空，已有工具回执事实未被丢弃。
  7. `[零破坏性副作用]`：模拟阻断后，验证不触发 `auth.logout`、不发起自动 retry 请求、不重建 Thread。
- **质量门禁（必须全绿）**：
  - `pnpm --dir apps/platform-web test`（定向单测全部通过）
  - `pnpm --dir apps/platform-web type-check`（Vue-tsc 无类型报错）
  - `pnpm --dir apps/platform-web lint`（ESLint 检查通过）
  - `pnpm --dir apps/platform-web build`（生产构建打包成功）

### 阶段二：F02 浏览器联合验收（待前置环境就绪后执行）

- **任务目标**：在专用的隔离本地栈中，完成真实浏览器到各后端服务的联合链路验收并抓取不可伪造的收包证据。
- **前置条件清单（必须先满足）**：
  1. **Worktree 隔离环境就绪**：严格按照 `docs/standards/worktree-development.md` 规范，在当前 Worktree 根目录执行 `bash scripts/local-stack.sh init` 初始化专属端口（23000–29999）与专属数据库/Redis，禁止直连现役 2142 端口。
  2. **脱敏配置注入**：在 `.local-stack/runtime.env` 中显式配置：
     ```bash
     RUNTIME_PII_REDACTION_ENABLED=true
     RUNTIME_PII_REDACTION_SECRET_KEY=c8d3e2a1b5f67890123456789abcdef0
     ```
  3. **保活受控 Provider 就绪**：由于 `test_pii_platform.py` 测完即销毁，必须启动保活的本地受控 Provider（带有事实抓包输出功能），以便测试完成后导出 `facts.jsonl` 作为原始邮箱/手机号零外发的直接证据。
- **验证项要求**：
  - **合成数据**：仅使用 `alice@example.test`、`13800138000`、合成 API Key，严禁使用任何真实客户信息。
  - **正向链路**：完成一条完整的 `Browser -> Platform API -> Runtime -> Worker -> Provider -> SSE -> Browser` 对话链路；Provider 实际收包中无敏感数据，浏览器中正常展示用户原文本与占位符回复。
  - **阻断链路**：注入未知结构触发脱敏阻断；验证 Provider 调用增量为 0，Run 进入 `error`，浏览器展示固定文案，草稿保留，未自动重发。
  - **关闭回退**：关闭脱敏后重启服务，验证原有对话能力平滑恢复。
  - **视口兼容性**：覆盖 1440 桌面宽度与 390 移动端宽度；保存关键截图、`request_id`、`thread_id` 与 `run_id` 证据。

---

## 6. 验收与状态同步

只有在上述 F01、F02 以及整体 V02 联合验收全部通过后，才可在 `tasks.md` 中将 F01、F02 勾选，并将项目整体状态从 `partial` 推进为 `done`。
未经联合验收或缺少真实 Provider 零外发证据时，严禁提前宣称功能全部完成。
