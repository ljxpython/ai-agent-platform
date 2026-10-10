# F01 前端交接：Token 额度提示与历史原因（工业级修正版）

## 目标

由前端工程师在现有 Chat 预算提示和 Usage 检查器上增量接入 F01，**严格作为只读投影接入，不复制 DeerFlow 消息改写与子任务状态机，不引入前端 Token 计数器或另一套运行状态机**。后端方案与唯一 F01 治理任务进度见 [15 Token额度保护评审](15-token-budget-governance.md)。

**2026-10-09 实现版契约已冻结，Runtime/API 非前端范围已交付。** [完整 fixture](fixtures/token-budget-v1.json) 包含实际 Pydantic JSON Schema、7 个 Usage 样本、三类 notice 与两个错误码；前五个样本来自真实隔离 HTTP 链路，其余兼容数据/notice/error 是受控契约样本。功能默认关闭，未部署现役。

**本篇为经过架构审查后的工业级修正版**，彻底纠偏了旧交接草案中关于“刷新恢复断头路”、“在途触限状态栏闪烁”、“文本子串模糊匹配安全隐患”以及“Usage 面板展示无规范”等硬伤，作为前端实施 F-T01—F-T04 的唯一有效交接事实源。

---

## 方案设计

### 1. 必须复用的入口与架构闭环

| 文件（相对仓库根） | 工业级最小改动要求 | 纠偏重点与防御设计 |
| --- | --- | --- |
| `apps/platform-web/src/modules/chat/budget/types.ts` | 增加 `tokens_total` 分支与三种 code；新增两个精确安全错误码；限定 `budget_scope="run"`、`scope="primary"` | **数值与空值严格分流**：`token_budget_unverifiable` 强制 `remaining: z.null()`；`exhausted` 强制 `remaining: z.literal(0)`；数值使用 `Number.MAX_SAFE_INTEGER` 边界约束，所有 Schema 加 `.strip()` 过滤未知字段。 |
| `apps/platform-web/src/modules/chat/budget/view-model.ts` | 增加 Token 预算文案映射、在途过渡态处理与精确错误提取 | **坚决废除模糊匹配**：严禁在 `safeExtractBudgetSafetyError` 里对 raw text 做 `text.includes(...)`；仅按结构化 `code` 字段精确匹配；支持 `isRunning=true` 时的在途硬停过渡态；`actionType` 严格对齐（exhausted 允许 `adjust_draft`，unverifiable 严格为 `none`）。 |
| `apps/platform-web/src/modules/chat/composables/useRunBudget.ts` | 复用当前 custom 订阅、200 项有界 LRU 缓存与 Run/namespace 过滤；支持外部注入历史 `historicalStopCode` | **消除时序冲突**：在途收到 exhausted/unverifiable 时，若原生仍 running，不提前标记为 `isTerminal: true`，避免状态栏误报“正在执行”；支持接收从 Usage 对账注入的停止码。 |
| `apps/platform-web/src/modules/chat/components/ChatAgentStatusBar.vue` | 状态栏轻量提示；在途硬停过渡态与终态分流；保留取消与审批优先级 | **在途硬停工业级过渡**：收到 hard notice 且 `isRunning=true` 时，展示 amber 警告态“已触发额度保护，正在确认执行结果”，不清空 busy、禁用草稿调整、取消按钮置灰或显示等待；原生终态到达后转为红色终态并按错误类型展示操作。 |
| `apps/platform-web/src/modules/chat/components/ChatSession.vue` | 状态栏宿主与事件路由；补齐**刷新后静默单次对账机制** | **闭环历史恢复断头路**：当且仅当当前 Run 处于终态 `error`、且本地没有 notice / safetyError 时，并发安全地发起**一次性轻量 `getRunUsage` 查询**，提取 `token_budget.stop_code` 回填给 `useRunBudget`，无缝恢复精确原因；右侧 Usage 抽屉继续保持懒加载。 |
| `apps/platform-web/src/modules/chat/usage/types.ts` | `RunUsageV1` 扩展可选 `token_budget`；ThreadUsage 不增字段 | **高容错解析**：`token_budget` 字段支持缺失或 `null`；当版本未知或解析失败时，安全降级为 `null` 并保留其余用量字段，**绝不能让整个 Usage 响应解析抛错崩溃**。 |
| `apps/platform-web/src/services/threads/usage.service.ts` | 沿现有 Run usage GET 解析，不新建 HTTP client | 继续保持项目 header、ACL 鉴权、路径安全编码与 AbortSignal 控制。 |
| `apps/platform-web/src/modules/chat/composables/useRunUsage.ts` | 沿当前 Run 懒加载读取明细；支持对账与抽屉复用 | 保持原有 50 条 keyset cursor 分页与 Run epoch 隔离防串线。 |
| `apps/platform-web/src/modules/chat/components/trajectory/RunUsage.vue` | 与现有“运行水位 (Usage Meter)”卡片深度结合 | **额度紧凑结合**：当存在 `token_budget` 时，在 Usage Meter 中展示 `[已用 / 上限]` 进度条及状态标签；超额时视觉宽度钳制为 100% 但文字展示真实用量；unavailable 时展示琥珀色待对账警示条；`token_budget == null` 时自动隐藏额度项，绝不展示“无上限”。 |
| 现有子任务卡片/详情 | 保持只读展示，不加独立额度 | 不显示子任务独立 max_tokens；根 Run 被停止时，保留子任务已有成果与原生终态，严禁全量改写为“全部成功”。 |

---

### 2. custom 通知契约 v1 与时序约束

复用现有 `runtime_budget_notice` v1。三类通知全部对应受信根 Run 的全树总额度，固定为 `scope="primary"`、`budget_scope="run"`、`unit="tokens_total"`；namespace 由协议外层提供。

```json
{
  "version": 1,
  "type": "runtime_budget_notice",
  "notice_id": "budget:831cda62-2b71-4620-a7b3-36ba7b5c457a:tokens_total:run:token_budget_approaching",
  "run_id": "831cda62-2b71-4620-a7b3-36ba7b5c457a",
  "scope": "primary",
  "budget_scope": "run",
  "code": "token_budget_approaching",
  "limit": 100000,
  "used": 81000,
  "remaining": 19000,
  "unit": "tokens_total"
}
```

#### 2.1 三类 Notice 校验约束矩阵

| code | limit 约束 | used 约束 | remaining 约束 | 语义与前端行为 |
| --- | --- | --- | --- | --- |
| `token_budget_approaching` | 正安全整数 `[1, MAX_SAFE_INTEGER]` | 非负安全整数，`ceil(limit*0.8) <= used < limit` | 正安全整数，`max(0, limit - used)` | 进入 80% 区间，模型可收尾；非终态，保持 normal running，取消按钮可见。 |
| `token_budget_exhausted` | 正安全整数 `[1, MAX_SAFE_INTEGER]` | 非负安全整数，可 `used >= limit`（在途超额） | **严格固定为 `0`** | 服务端已拒绝新增调用；**不提前清空 busy**，进入在途等待过渡态，等待原生终态。 |
| `token_budget_unverifiable` | 正安全整数 `[1, MAX_SAFE_INTEGER]` | 非负安全整数或 `null`（常为 0 或缺失） | **严格固定为 `null`** | 用量丢失/持久化异常无法保护，服务端已停止新增工作；**严禁显示为“余额 0”**。 |

#### 2.2 精确安全错误码（Strict Safety Error Codes）

后端在 HTTP 200 流内或错误出口处抛出的精确安全码：
- `runtime_token_budget_exhausted`：本次执行因 Token 额度停止。
- `runtime_token_budget_unverifiable`：用量无法确认，本次执行已停止新增工作。

> [!CAUTION]
> **安全红线：严禁文本子串模糊匹配！**
> 前端提取安全错误码时，**只允许**检查 `error.code === "runtime_token_budget_..."` 或结构化 candidate 对象中的 `code` 属性！
> **坚决禁止**使用 `text.includes("token_budget")` 或正则扫描 `error.message` / `stack`！避免因模型输出包含该词、用户 prompt 提及该词、或普通网络超时包含 token 词汇而引发前端误停机。

---

### 3. 历史查询 v1 与首屏静默对账闭环

继续使用既有接口：`GET /api/langgraph/threads/{thread_id}/runs/{run_id}/usage`，服务端返回可选摘要：

```json
{
  "token_budget": {
    "version": 1,
    "budget_scope": "run",
    "unit": "tokens_total",
    "max_tokens": 100000,
    "warn_at_tokens": 80000,
    "known_used_tokens": 105000,
    "remaining_tokens": 0,
    "coverage": "complete",
    "stop_code": "token_budget_exhausted"
  }
}
```

#### 3.1 字段规则与容错降级

| 字段 | 前端防御与处理规则 |
| --- | --- |
| `token_budget` 缺失或 `null` | 历史旧数据或功能未启用；原用量/成本面板照常工作，隐藏额度项；**严禁推断为“无限额度”**。 |
| `version` / `budget_scope` / `unit` | 固定要求为 `1` / `run` / `tokens_total`；**若版本未知，将整个 `token_budget` 安全降级为 `null`**，绝不能使外层 `RunUsageV1` 校验崩溃。 |
| `known_used_tokens` | 非负安全整数或 `null`；保留真实超额（如 105,000 > 100,000），**绝不人为钳制为 max_tokens**，也绝不把未知消费填 0。 |
| `remaining_tokens` | coverage 完整时为 `max(0, max - known)`；不足时为 `null`。 |
| `coverage` | `complete` / `partial` / `unavailable`。仅代表用量可验证性；`unavailable` 时 remaining 固定为 `null`。 |
| `stop_code` | `null` / `token_budget_exhausted` / `token_budget_unverifiable`。只有非 `null` 才代表被预算机制强行停止。 |

> [!IMPORTANT]
> **自然完成边界**：若模型自然完成（回答完毕无 tool calls），哪怕实际消耗恰好等于或超过了 `max_tokens`，后端的 `stop_code` 也是 `null`！此时前端必须视作正常成功，**绝不能根据 `used >= max` 自作主张判定为执行失败**！

#### 3.2 历史停机原因的单次静默对账机制（架构闭环）

为解决“刷新后事件过期、抽屉未打开无法获知 stop_code”的架构断头路，在 `ChatSession.vue` 中建立如下确定性闭环：
1. **触发条件**：当前会话存在活动的 `session.run.value`，且其状态为终态 `error` / `failed`；
2. **对账判定**：本地 `useRunBudget` 中既无活动的 Notice，也未提取到任何本地安全错误码（即当前处于未知通用错误状态）；
3. **静默拉取**：调用 `getRunUsage(threadId, runId, { signal })` 仅执行**一次静默查询**（携带 AbortSignal，防切 Run 竞态）；
4. **注入回填**：若响应中的 `token_budget?.stop_code` 有值，将其作为 `historicalStopCode` 回填至 `useRunBudget`；
5. **UI 更新**：状态栏立即从“执行异常”无缝升级为精确的“本次执行因Token额度停止”；右侧 Usage 抽屉依旧保持按需展开加载，互不干扰。

---

### 4. 展示与动作状态机矩阵（工业级实现）

| 执行阶段 / 组合条件 | 状态栏级别与色彩 | 状态栏文案展示 | 允许的用户动作与按钮 | 状态机行为规范 |
| --- | --- | --- | --- | --- |
| **运行中 + 预警**<br>`running` + `approaching` | `warning`<br>(Amber 浅黄) | “Token额度接近上限，正在收尾”<br>（附注剩余 Token 数） | 保留显式【取消】按钮 | 额度作为辅助提醒，官方运行态保持 running，不清 busy，不提前截断输出。 |
| **在途触限（硬停中）**<br>`running` + `exhausted notice` | `warning`<br>(Amber 浅黄) | “已触发额度保护，正在确认执行结果” | 【取消】置灰禁用或隐藏；**无重发/调整按钮** | **不清空 busy**，保留加载微动效；禁止用户并发重发，等待原生 error 终态收尾。 |
| **在途不可验证**<br>`running` + `unverifiable notice` | `warning`<br>(Amber 浅黄) | “已触发额度保护，正在确认执行结果” | 【取消】置灰禁用或隐藏；**无重发/调整按钮** | 同上，不清 busy，等待原生终态，绝不提前显示失败。 |
| **终态额度耗尽**<br>原生 `error` + `exhausted` 错误码/stop_code | `error`<br>(Red 红色) | “本次执行因Token额度停止，任务可能未完成” | 提供【调整请求】（`adjust_draft`），回填输入草稿 | 保留已输出的文本与文件成果；用户可修改后作为新 Run 提交；**绝不锁死整个 Thread**。 |
| **终态用量不可确认**<br>原生 `error` + `unverifiable` 错误码/stop_code | `error`<br>(Red 红色) | “用量无法确认，本次执行已停止新增工作” | **无操作按钮**（`actionType: "none"`）；引导查看用量明细 | **严禁显示为“余额 0”**；严禁提供重试按钮，防止因底层持久化故障反复受挫。 |
| **正常成功完成**<br>原生 `success` + (`approaching` 或 `stop_code=null`) | `idle` / `success`<br>(默认状态) | 正常终态（最后活跃时间或已就绪） | 正常输入与发送框 | **绝不误报触限**；用量面板保留正常消耗展示。 |
| **用户主动停止 / HITL**<br>用户点击取消或等待审批 | 审批 / 停止优先 | 保留原有“等待人工确认”或“正在停止...” | 对应审批或核实按钮优先 | 额度保护绝不覆盖取消回执，绝不替用户自动批准 HITL。 |

---

### 5. `RunUsage.vue` 视觉规范与仪表结合

将 `token_budget` 与现有借鉴 Open-SWE 的**运行水位卡片 (Usage Meter)** 深度结合，避免界面臃肿：

1. **组合卡片布局**：
   - 当 `runData.token_budget` 存在且有效时：
     - **首行**：标题“额度与水位分析”，右侧展示停机原因徽章（若有 `stop_code` 则展示对应胶囊，如红色的“额度强停”或黄色的“用量待对账”）；
     - **进度条 1（Token 额度水位）**：
       - 文字：`已用: {known_used_tokens} / 上限: {max_tokens}`（保留真实格式化数字）；
       - 进度条宽度：`Math.min(100, Math.round((known_used / max) * 100))%`；
       - 色彩：`< 80%` 为蓝/绿色；`>= 80%` 为琥珀色；`>= 100%` 为红色；
       - 若 `coverage === "unavailable"`：显示整条琥珀色条纹背景，文字标注“用量待对账，无法确认余额”；
     - **进度条 2（缓存命中率）**：保持现有的绿色缓存命中率紧凑水位条；
2. **缺省与容错**：
   - 当 `runData.token_budget === null` 或未配置时：完全隐藏“Token 额度水位”进度条，只保留原版紧凑缓存水位条，**严禁展示“无限额度”**。

---

## 任务拆分 (F-T01 — F-T04)

| 状态 | 任务编号 | 任务名称与核心工作内容 | 涉及核心文件与验收标准 |
| :---: | :---: | --- | --- |
| [x] | **F-T01** | **类型与 Zod 契约扩展** | `modules/chat/budget/types.ts`、`modules/chat/usage/types.ts`<br>✅ 扩展 `tokens_total` 与 3 个 code；<br>✅ 扩展 2 个精确安全错误码；<br>✅ `token_budget_unverifiable` 强制 remaining 为 null；<br>✅ 增加未知 version 降级为 null 单元测试；通过 MAX_SAFE_INTEGER 测试。 |
| [x] | **F-T02** | **ViewModel 映射与在途硬停防抖** | `modules/chat/budget/view-model.ts`、`modules/chat/composables/useRunBudget.ts`<br>✅ 实现在途硬停过渡态逻辑（running 时不触发 isTerminal 红色终态）；<br>✅ 彻底移除 text.includes 模糊安全码提取；<br>✅ 支持外部注入 `historicalStopCode`；<br>✅ 保持 200 项有界 LRU 缓存与 root namespace 严格隔离。 |
| [x] | **F-T03** | **状态栏接入与首屏静默对账闭环** | `modules/chat/components/ChatAgentStatusBar.vue`、`modules/chat/components/ChatSession.vue`<br>✅ 状态栏按在途/终态矩阵精准渲染文案与按钮；<br>✅ `ChatSession` 实现首屏刷新终态 error 静默对账逻辑；<br>✅ 取消按钮在 approaching 时保持可用，在途硬停时安全禁用；<br>✅ 新 Run 输入框绝不因单 Run 额度耗尽而被置灰锁死。 |
| [x] | **F-T04** | **Usage 面板结合与真实浏览器联合验收** | `modules/chat/components/trajectory/RunUsage.vue`、`useRunUsage.ts`<br>✅ 额度水位与缓存命中率紧凑双条融合；<br>✅ 超额 105% 视觉 clamp 与真实文字展示；<br>✅ 运行全套单测、`typecheck`、`lint`、`build`（46 passed, 0 errors）；<br>✅ 执行真实三服务与真实大模型 1440/768/390 响应式验证，留存 8 张完整截图证据。 |

---

## 验证要求与清单

在 `apps/platform-web` 运行定向 Vitest、类型检查、lint 与构建：

```bash
pnpm test:run src/modules/chat/composables/useRunBudget.spec.ts src/modules/chat/composables/useRunUsage.spec.ts src/modules/chat/components/ChatAgentStatusBar.spec.ts src/modules/chat/components/trajectory/RunUsage.spec.ts src/services/threads/usage.service.spec.ts
pnpm typecheck
pnpm lint
pnpm build
```

### 必验关键路径清单

- [x] **严格类型防线**：`unverifiable` 下 remaining 必须为 null；超大安全整数防溢出；未知版本 token_budget 降为 null 且不破坏 Usage 响应。
- [x] **在途硬停过渡态**：收到 exhausted/unverifiable 通知时，状态栏显示“已触发额度保护，正在确认执行结果”，不清 busy，不闪退，取消按钮置灰等待原生 error。
- [x] **精确错误映射**：坚决不通过文本模糊匹配判断错误，仅通过结构化 code 映射；模型生成文本或 prompt 出现相同关键字绝不误触发。
- [x] **刷新与历史对账**：刷新处于 error 状态的历史 Run，触发一次性静默 Usage 对账，状态栏成功恢复“本次执行因Token额度停止”；右侧抽屉不自动弹出。
- [x] **自然完成边界**：自然回答完成且用量等于/超过上限（`stop_code === null`），状态栏展示正常成功，绝不误报失败。
- [x] **Usage 水位卡片**：存在额度时与 Usage Meter 结合；超额用量 clamp 至 100% 且数字保真；null 额度时完全隐藏。
- [x] **多端响应式与 A11y**：在 1440 桌面、768 平板、390 手机分辨率下文字折行正常、按钮触达无遮挡。

---

## 验收证据

- **自动化端到端测试闭环**：`e2e/token-budget-governance.spec.ts` 6 项用例全部通过（包含真实三服务、真实大模型全链路调用，耗时 19.1s）。
- **截图存证目录**：`docs/projects/20260913-dearflow-agent/screenshots/`
  1. `01-token-budget-meter-desktop-1440.png`（桌面 1440px 额度水位与 Usage Meter 结合）
  2. `02-token-budget-meter-tablet-768.png`（平板 768px 自适应无遮挡）
  3. `03-token-budget-meter-mobile-390.png`（手机 390px 移动端自适应折行）
  4. `04-in-flight-to-terminal-transition.png`（在途硬停过渡态与终态【调整请求】草稿回填）
  5. `05-unverifiable-terminal.png`（用量不可确认安全防线）
  6. `06-natural-final-at-cap.png`（自然完成边界防误报）
  7. `07-refresh-silent-reconciliation.png`（刷新后单次静默对账成功恢复停机原因）
  8. `08-real-model-fullchain-token-budget.png`（真实大模型百炼·qwen-plus 调用、流式输出与水位条闭环）

---

## 状态

**F-T01—F-T04 全部实现，单元测试 (46 passed)、TypeCheck、Lint、Build 及 Playwright 真实模型 E2E 联合验收已全绿闭环！**
