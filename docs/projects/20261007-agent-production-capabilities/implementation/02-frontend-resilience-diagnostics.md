# 前端运行准备与重试摘要实现

日期：2026-10-08；关联任务 T10。进度以 [tasks.md](../tasks.md) 为准。

## 改动范围

本次改动覆盖 `apps/platform-web`，扩展现有的 Run Diagnostics 诊断面板，安全消费后端冻结的 `preparations` 与 `retries` 摘要数据。

### 1. 类型与安全 Schema 契约 (`types.ts`)
- 扩展 `preparationSummarySchema`：包含 `observation_id`、`scope`、`namespace`、`component`、`outcome`、`duration_ms`、`error_code`。
- 扩展 `retrySummarySchema`：包含 `observation_id`、`scope`、`namespace`、`unit`、`role`、`attempts`、`outcome`、`code`、`duration_ms`。
- **strict 校验与防注入**：
  - `attempts` 严格限制为 `z.number().int().min(1).max(2)`，严禁 coercion；
  - `observation_id` 与 `role` 强制校验安全正则 `^[A-Za-z0-9_:.-]+$`，长度限制分别为 128 与 64 字符，防止 LLM 提示注入穿透至 DOM；
  - 子项所有 nullable 字段统一规范化为 `.nullable().optional().default(null)`，避免后端缺省 key 时解析失败；
  - 根级 `preparations` 与 `retries` 声明为 `.array(...).max(20).optional().default([])`，配合 `.strip()` 剥离未知字段（隔离 canary 探测），向后兼容旧 v1 响应。

### 2. View-Model 纯函数与视觉判定 (`view-model.ts`)
- `formatAttempts(attempts)`：1 显示“单次调用”，2 显示“重试 1 次”；
- `getPreparationComponentLabel`、`getPreparationOutcomeBadge`、`getPreparationErrorCodeLabel`：映射准备组件名、状态徽章（emerald/blue/amber/red）与异常码；
- `getRetryUnitLabel`：映射模型调用与带角色名的子任务；
- `getRetryOutcomeBadge` 与 `getRetrySeverity`（核心视觉防坑）：
  - 只要主 Run 的 `run_status === "success"`，内部失败（failed）或耗尽（exhausted）的重试记录一律降级为 `warning`（Amber 琥珀色警示），严禁整屏标红误报失败；
  - 仅在主 Run 失败时，失败调用才呈现致命红色。

### 3. 组件分层架构（对标 Playbook 规范）
现有 `RunDiagnostics.vue` 行数已超 500 行，严格遵循单一职责与代码粒度控制规范抽离子组件：
- `RunPreparationsSection.vue`：专职展示工作区准备结果、耗时与 namespace 截短；数组为空时完全不渲染；
- `RunRetriesSection.vue`：专职展示受管调用与重试尝试；列表标题明确命名为「调用尝试与重试」；数组为空时完全不渲染；
- `RunDiagnostics.vue`：主面板精简重构，挂载两个子组件并传入响应式数据与 `currentRunStatus`，增量代码控制在 15 行以内。

### 4. 自动化测试与验证
- 单元测试覆盖：
  - `view-model.spec.ts`：纯标签函数、attempts 格式化、核心视觉降级、旧版 DTO 默认空数组、新 DTO 解析、越界 attempts 拦截、非法 role 拦截、canary 字段剥离；
  - `RunPreparationsSection.spec.ts`：空态隐藏、准备结果列表与状态徽章渲染；
  - `RunRetriesSection.spec.ts`：空态隐藏、调用尝试渲染、主 Run 成功时的琥珀色降级及失败时的红框呈现；
  - `RunDiagnostics.spec.ts`：子组件集成挂载与空数组完全隐藏验证。
- 门禁总检：
  - `pnpm test:run`：6 套测试 49 项全部通过；
  - `pnpm typecheck`：0 errors；
  - `pnpm lint`：0 errors；
  - `pnpm build`：生产打包成功。
