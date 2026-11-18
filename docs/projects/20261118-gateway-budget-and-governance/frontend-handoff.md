# Budgets 前端交接与实施规范 (frontend-handoff.md)

> **版本：** 2026-11-18（经老王工业级架构审查修订版）。
> **责任范围：** 对应 Task 4，由前端同事实施。后端已在 `feat/gateway-budget-and-governance` Worktree（`ai-agent-platform-gateway-budget`）中实现并通过全套后端验收。
> **涉及服务：** `apps/platform-web`。包含用量中心管理模块（`modules/usage/`）与聊天终态/错误处理模块（`modules/chat/`）。
> **核心原则：** 冻结现有后端契约；消除数据精度丢失、路由下钻冲突、Zod白名单崩溃与三态UI矛盾；保留已有代码风格与设计系统标准。

---

## 1. 涉及模块与文件变动全景

本次前端实施**不能仅限于用量中心**，必须同步补齐聊天流内拦截与错误白名单，否则聊天模块遇到预算超额会当场触发 Zod 校验崩溃。具体文件清单如下：

```text
apps/platform-web/src/
├── modules/
│   ├── usage/                                  # 用量中心（Budgets 管理与展示）
│   │   ├── pages/
│   │   │   ├── UsageDashboardPage.vue          # 顶栏主入口：增加 budgets Tab，URL query 双向绑定与下钻防冲突
│   │   │   └── UsageDashboardPage.spec.ts      # 页面及路由单元测试
│   │   ├── components/
│   │   │   ├── GatewayBudgetsTab.vue           # [新增] 策略列表视图组件（三态进度条、超额告警、操作区）
│   │   │   ├── CreateBudgetPolicyModal.vue     # [新增] 新建/编辑策略模态窗（作用域自适应、12位字符串输入守卫）
│   │   │   └── DeleteBudgetPolicyModal.vue     # [新增] 软删除确认二次弹窗
│   │   ├── composables/
│   │   │   ├── useGatewayBudgets.ts            # [新增] 策略拉取、CRUD、请求竞态防闪烁、定点百分比纯函数
│   │   │   └── useGatewayBudgets.spec.ts       # [新增] 状态机与定点比值单测
│   │   ├── types.ts                            # [扩展] 扩充 BudgetPolicy、BudgetItem、AccountingStatus 等契约类型
│   │   └── view-model.ts                       # [扩展] 复用并扩充金额与进度条展示模型
│   │
│   └── chat/                                   # 聊天模块（流内拦截、错误呈现与历史回显）
│       ├── completion/
│       │   ├── types.ts                        # [扩展] REASON_CODES 白名单增加 runtime.gateway_budget.exhausted 等枚举
│       │   ├── types.spec.ts                   # [扩展] 白名单契约单测
│       │   ├── presentation.ts                 # [扩展] REASON_CODE_MAP 增加预算超额的中文呈现文案与安全映射
│       │   └── presentation.spec.ts            # [扩展] 错误文案映射单测
│       └── composables/
│           └── useChatSession.ts               # [加固] 握手 429 / 503 拦截，流内预算终止时不触发自动重投
```

---

## 2. 路由与 URL Query 规范（消除下钻与历史栈冲突）

### 2.1 路由入口与双向绑定
沿用已有用量中心路由，支持通过 `?tab=budgets` 访问：
- 平台用量：`/workspace/usage?tab=budgets`
- 项目用量：`/workspace/projects/{project_id}/usage?tab=budgets`

### 2.2 路由同步与下钻防冲突准则（已纠偏）
1. **必须使用 `router.replace`**：Tab 切换（`gateway` / `logs` / `budgets` / `governance`）必须使用 `router.replace({ query: { ...route.query, tab: newTab } })`，**严禁使用 `router.push`**，杜绝用户反复点 Tab 污染浏览器后退历史栈。
2. **下钻（Drilldown）联动修复**：在 `UsageDashboardPage.vue` 的 `handleDrilldownToLogs` 中，必须通过 `router.replace` 显式写入 `tab: "logs"`，同时保留起止毫秒时间参数（`from` / `to`），保证图表点击下钻至日志时，URL、Tab 选中态与下钻日志过滤器严格同频。
3. **项目切换竞态隔离（防数据穿透）**：
   - 在 `useGatewayBudgets.ts` 内部必须维护 `currentRequestId` 序号或 `AbortController`。
   - 当 `projectId` 或 `selectedScopeMode` 改变时，立即作废前序慢请求，严禁上一个项目的异步响应覆盖新项目的看板数据。

---

## 3. 权限与作用域自适应（UI 就地守卫）

### 3.1 权限规则表
| 操作 | 后端检查权限 | 前端表现与守卫规则 |
|---|---|---|
| 不传 project_id 的平台预算列表 | `platform.usage.read` | 顶栏选 Platform 模式可见；无权时安全降级为 Project 模式 |
| 指定 project_id 的项目预算列表 | `project.usage.read` | 顶栏选 Project 模式可见；无权时展示现有 403 占位状态 |
| 创建 / 修改 / 删除 GLOBAL | `platform.super_admin.manage` | 仅在 Platform 模式且具备超管权限时开放；Project 模式下**强行隐藏或禁用** |
| 创建 / 修改 / 删除 PROJECT | `project.runtime.write` | Project 模式下只能为当前项目创建；Platform 模式下需下拉选择所属项目 |

### 3.2 弹窗自适应交互约束
- **在项目用量页**：打开 `CreateBudgetPolicyModal` 时，Scope 字段**锁定并硬编码为当前项目（PROJECT）**，禁用切换 GLOBAL，自动带出当前 `project_id` 与项目名称，绝不让普通管理员因误选 GLOBAL 吃到 403。
- **在平台用量页**：若当前用户不具备 `platform.super_admin.manage`，禁用“创建全局预算”按钮；若具备，允许用户在下拉框中选择“全局（GLOBAL）”或“指定项目（PROJECT）”。

---

## 4. HTTP 接口契约与异常交互规范

### 4.1 接口列表（后端已冻结）
- `GET /api/policies/budgets`（Platform 视图，返回当前租户所有策略）
- `GET /api/policies/budgets?project_id={uuid}`（Project 视图，仅返回当前项目策略）
- `POST /api/policies/budgets`（创建，201）
- `PUT /api/policies/budgets/{policy_id}`（全量更新，200）
- `DELETE /api/policies/budgets/{policy_id}`（软删除，200，返回带 `deleted_at` 的策略对象；**注意：不是 204**）

### 4.2 请求载荷规范
```json
{
  "scope": "PROJECT",
  "project_id": "11111111-1111-4111-8111-111111111111",
  "budget_amount": "200.000000000000",
  "budget_unit": "USD",
  "duration": { "unit": "MONTHS", "value": 1 },
  "action": "REJECT"
}
```
> [!IMPORTANT]
> - `budget_amount` 必须原样提交**十进制字符串**（最多 12 位小数），后端自动规范化为 12 位小数；**严禁使用 JSON Number 提交**。
> - `duration.unit` 仅支持 `DAYS`、`WEEKS`、`MONTHS`；`value` 必须为整数 `1`。
> - 动作为单选：`ALERT`（通知后继续）或 `REJECT`（阻止后续调用）。

### 4.3 响应处理与特殊异常指引
- **写响应中的 `sync_status`**：
  - 返回 `sync_status: "applied"`：策略已落库且 Runtime 已就绪；
  - 返回 `sync_status: "pending"`：规则已保存但 Runtime 正在异步同步中。**弹窗照常关闭，列表中该行打上“同步中（Pending）”黄色微胶囊**，提醒用户无需重复创建。
- **409 `budget_policy_limit`（200 条软删除上限死锁防范）**：
  - 若触发该错误，前端 Toast 提示必须具备行动建议：“当前租户预算策略历史存档已达上限（200条），请联系平台管理员清理归档”。
- **409 `budget_policy_changed`**：
  - 提示“策略已被他人修改，请刷新后重试”，并自动重新拉取列表。

---

## 5. 账务三态进度条矩阵与高精度比值算法（核心改进）

### 5.1 三态视觉呈现矩阵（杜绝 UI 矛盾）

后端每行返回 `accounting_status`（`complete` / `unverifiable` / `reconciling`）、`known_spend`、`current_spend` 及 `is_exceeded`。前端必须严格按下表渲染，严禁在不可核实时盲目画出正常进度条：

| 账务状态 (`accounting_status`) | 超额状态 (`is_exceeded`) | 进度条视觉呈现 | 数值与文字呈现 | 状态徽标 (Badge) |
| :--- | :--- | :--- | :--- | :--- |
| **complete** (完整) | `false` (< 80%) | 标准中性主色进度条 | `$X.XX / $Y.YY (XX.X%)` | 正常（无特殊徽标） |
| **complete** (完整) | `false` (80% ~ 99%) | 警戒橙色进度条 | `$X.XX / $Y.YY (XX.X%)` | 橙色接近上限胶囊 |
| **complete** (完整) | `true` ($\ge 100\%$) | 危险红色进度条（截断至 100% 宽，文字保留实际如 115%）+ ⚠️ Warning 图标 | `$X.XX / $Y.YY (115.0%)` | 红色已超额胶囊 |
| **reconciling** (正在恢复中) | 任意 | **禁用进度条**，渲染浅灰脉冲骨架条 | 显示已知金额 `$X.XX`，百分比显示 `—` | 蓝色“正在校准”微胶囊 |
| **unverifiable** (不可核实) | `false` 或 `null` | **置灰斜纹进度条（Muted Striped）**，宽度固定为 0 或最小指示 | 显示已知部分 `$X.XX (总账受阻)`，百分比显示 `—` | 黄色“账务受阻”微胶囊 |
| **unverifiable** (不可核实) | `true` (已知部分已超标) | **危险条纹进度条（Striped Danger）** + ⚠️ Warning 图标 | 显示已知部分 `$X.XX (部分已超)`，强调总账仍在审计 | 红色“部分已超·账务审计中”胶囊 |

### 5.2 定点高精度比值计算纯函数（拒绝 BigInt 截断与 Number 浮点溢出）
在 `useGatewayBudgets.ts` 中封装导出纯函数：

```typescript
/**
 * 定点高精度比值与百分比计算（避免 Number 精度丢失和 BigInt 除法整除抹零）
 * @param spendStr 十进制金额字符串（如 "1.100000000000"）
 * @param limitStr 预算限额字符串（如 "200.000000000000"）
 * @returns ratio (0~1 或更高浮点数供宽度使用), percentStr (如 "55.0%", "110.5%")
 */
export function calculateBudgetRatio(
  spendStr: string | null | undefined,
  limitStr: string | null | undefined
): { ratio: number; percentStr: string; isOverBudget: boolean } {
  if (!spendStr || !limitStr) {
    return { ratio: 0, percentStr: "—", isOverBudget: false };
  }
  const spend = Number(spendStr);
  const limit = Number(limitStr);
  if (!Number.isFinite(spend) || !Number.isFinite(limit) || limit <= 0) {
    return { ratio: 0, percentStr: "—", isOverBudget: false };
  }
  const rawRatio = spend / limit;
  const percentNum = rawRatio * 100;
  const percentStr = `${percentNum.toFixed(1)}%`;
  const isOverBudget = spend >= limit;
  // ratio 用于 CSS 宽度百分比，最小 0，封顶 100% 避免撑破容器；percentStr 保留真实比例
  const clampedRatio = Math.max(0, Math.min(1, rawRatio));
  return { ratio: clampedRatio, percentStr, isOverBudget };
}
```

### 5.3 表单输入框绝对防线
- 表单组件中的金额输入框必须使用常规文本框：`<input type="text" v-model="form.budget_amount" />`；
- 输入时做正浮点正则校验：`/^\d*(\.\d{0,12})?$/`，阻止非法字符输入；
- 提交前校验大于 0，禁止走 `Number(form.budget_amount)` 重新序列化。

---

## 6. 聊天与执行端契约适配（重点补齐，防 Zod 崩溃）

在智能体运行时，超额将直接作用于模型调用拦截。前端必须在 `modules/chat/` 落地防线：

### 6.1 `completion/types.ts` 枚举白名单扩充
在 `REASON_CODES` 中追加两个点分枚举：
```typescript
export const REASON_CODES = [
  // ...已有枚举
  "runtime.gateway_budget.exhausted",     // 预算超额截断
  "runtime.gateway_budget.unverifiable",  // 预算账务不可核实拒绝
] as const;
```

### 6.2 `completion/presentation.ts` 错误呈现映射
在 `REASON_CODE_MAP` 中增加对应的中文文案与胶囊配置：
```typescript
"runtime.gateway_budget.exhausted": {
  badgeText: "预算已耗尽",
  bannerTitle: "模型调用已终止：当前预算限额已达上限",
  bannerMessage: "当前项目或平台的自然周期预算已耗尽。请联系管理员在用量中心调整限额，或等待下一个重置周期。",
  badgeVariant: "error",
  icon: "warning",
},
"runtime.gateway_budget.unverifiable": {
  badgeText: "预算状态受阻",
  bannerTitle: "模型调用已中断：账务状态不可核实",
  bannerMessage: "由于账务服务正在恢复或数据同步延迟，执行已受保护中断。请稍后刷新重试。",
  badgeVariant: "warning",
  icon: "warning",
}
```

### 6.3 `useChatSession.ts` 流式与请求拦截加固
- 当请求收到 HTTP 429 且 `error.code === 'BUDGET_LIMIT_EXCEEDED'` 时：
  - 提取 `error.extra.resets_at`，格式化为本地可读重置时间；
  - 弹出清晰错误提示，**彻底禁止调用 `submitQueuedMessage` 自动重投**，草稿安全保留在输入框。
- 当流内接收到 `runtime_gateway_budget_exhausted` 停止事件时：
  - 正常进入终止态，保留当前回合已有消息和产物，允许用户正常使用右侧产物抽屉和会话历史。

---

## 7. 前端交付与验收清单（对应 Task 4 & P6）

实施完成后，按以下清单逐项验证：

- [ ] **路由与 Tab 联动**：
  - 访问 `/workspace/usage?tab=budgets` 正确激活 Budgets 选项卡；
  - 点击 Gateway / Logs / Budgets / Governance，URL query 相应同步且使用 `replace`（不污染后退历史）；
  - 图表悬停下钻至 Logs 正常生效，无 Tab 状态倒挂。
- [ ] **三态进度条覆盖**：
  - `< 80%`：中性灰色/主色进度条；
  - `80% ~ 99%`：警戒橙色进度条；
  - `100% ~ 110%`：危险红色进度条截断 + 超额实际文本 + ⚠️ 警告图标；
  - `reconciling`：展示脉冲校准微胶囊，进度条禁用；
  - `unverifiable`：置灰/报警斜纹进度条，文案明确标注“总账受阻”。
- [ ] **高精度与表单防线**：
  - 创建 $200.000000000001 提交为原样字符串，无浮点截断；
  - 极小金额（如 $0.000001）正常展示，无科学计数法崩溃。
- [ ] **作用域与权限守卫**：
  - 项目用量页仅能建当前项目的 `PROJECT` 策略；
  - 平台用量页超管可建 `GLOBAL`，普通成员不可越权。
- [ ] **聊天防崩溃与回显**：
  - 模拟 `runtime.gateway_budget.exhausted` 终态，Zod 解析 100% 跑通，聊天气泡渲染“预算已耗尽”中文条，无白屏或红字报错。
- [ ] **代码质量门禁**：
  - `pnpm typecheck`（vue-tsc）0 错误；
  - 对应单元测试（`useGatewayBudgets.spec.ts`、`UsageDashboardPage.spec.ts`、`types.spec.ts`、`presentation.spec.ts`）全部跑绿；
  - 生产构建命令执行成功。
