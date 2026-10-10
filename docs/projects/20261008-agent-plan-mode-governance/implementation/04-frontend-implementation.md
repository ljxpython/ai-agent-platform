# 前端实施与全链路自动化闭环

## 改动时间与相关任务

2026-10-09；T30-T33、T41-F、T42-F、T43-F。进度以 `../tasks.md` 为准，完整命令与真实结果见 `../verification.md`。

## 前端核心改动与设计落地

| 完整代码位置 | 改动与理由 |
| --- | --- |
| `apps/platform-web/src/modules/chat/components/ChatComposer.vue` | 1. 左下角“+”号扩展功能菜单增加“先规划”功能项，采用 `<Teleport to="body">` 结合动态视口绝对定位，彻底根除父容器 `overflow-x-auto` 导致的浮层裁剪与 pointer-events 穿透拦截问题；<br>2. 激活后在输入框上方呈现“📋 规划模式已启用”胶囊徽章；<br>3. 在提交发送时即时复位 `draftPlanMode`（异常时自动回滚恢复），严格满足单次 Run 作用域契约，不污染后续消息。 |
| `apps/platform-web/src/modules/chat/components/ChatRunOptionsDialog.vue` | 运行选项弹窗同步增加规划模式开关，支持细粒度配置。 |
| `apps/platform-web/src/modules/chat/composables/useChatRunConfig.ts` | 实施两级能力判定：新会话通过 `PLAN_GRAPHS` 白名单推导，已有会话依据 thread capabilities 动态匹配；不支持的 Agent 严格安全禁用，不向下兼容静默降级。 |
| `apps/platform-web/src/modules/chat/plan-review.ts` | 新增纯函数模块严格解析 `agent_plan_review` interrupt，安全构造 `approve`、`request_changes`（1-2000 字符限制校验）、`abandon` 载荷。 |
| `apps/platform-web/src/modules/chat/components/PlanReview.vue` | 1. 待审态大卡片展示标题、版本、哈希，提供 Approve / Request Changes / Abandon 交互与 1-2000 字符反馈输入框；<br>2. 历史与规划态紧凑卡片，无缝联动右侧 `Inspector` 抽屉查看 64 KiB 完整正文与一键复制；<br>3. 强化 XSS Canary 防御，过滤 `javascript:` 与 `data:` 伪协议；正文局部滚动，防止破坏聊天视口；<br>4. 提供 `data-testid` 稳定测试选择器。 |
| `apps/platform-web/src/modules/chat/composables/useSessionInterrupts.ts` 与 `ChatSession.vue` | 从普通工具审批中严格分离 `planReview`；待审态将 `planReview` 纳入 `hasPendingInterrupts`，输入框安全锁定并禁用提交；捕获 409 状态自愈。 |
| `apps/platform-web/src/utils/markdown.ts` | 协议白名单清洗，严格拦截 `javascript:` 和 `data:` 伪协议，防御 XSS 攻击。 |
| `apps/platform-web/e2e/support/platform.ts` | 模型优先级匹配强化：优先锁定原生 Tool Calling 支持完善的真实大模型（如 `deepseek-v4-flash`），规避通义千问文本伪 Tool Calling 导致的循环缺陷。 |

## 自动化测试与验证

- **静态门禁**：
  - Vitest：`6 passed`（`approvals.test.ts`、`plan-review.test.ts`、`useChatRunConfig.spec.ts`），退出码 0
  - vue-tsc：类型检查 `0 errors`，退出码 0
  - ESLint：代码规范 `0 errors`，退出码 0
  - Vite build：前端生产打包通过，退出码 0
- **端到端测试（Playwright + Chromium 真实三服务栈）**：
  - 测试套件：`e2e/plan-mode-governance.spec.ts`
  - `F01-F04: Plan Mode toggle, badge, options dialog across viewports and themes`：耗时 2.8s，**PASSED**
  - `F05-F14: Real agent approval loop, input locking, and responsive plan review`：耗时 22.0s，**PASSED**（调用真实 `deepseek-v4-flash` 大模型，跑通分步调研 -> `save_plan` -> `submit_plan` 原生中断 -> 前端卡片渲染 -> 输入框锁定 -> request_changes -> 批准 -> 原生工具执行闭环）
- **多视口与双主题截图**：
  - `01-plan-mode-composer-badge-light-1440.png`（加号菜单与单次规划模式徽章）
  - `02-plan-mode-composer-badge-390.png`（390 移动端紧凑徽章与布局）
  - `03-plan-mode-review-card-light-1440.png`（待审状态卡片与输入框安全锁定）
  - `04-plan-mode-review-card-dark-1024.png`（1024 视口深色模式）
  - `05-plan-mode-review-card-light-390.png`（390 移动端视口审批态）
  - `06-plan-mode-request-changes-input.png`（修改建议 1-2000 字符展开输入态）
  - `07-plan-mode-approved-execution.png`（批准后原图流转与后续工具执行全景）

真实全景证据与 Thread/Run/interrupt 对账结果见 `../verification.md`。
