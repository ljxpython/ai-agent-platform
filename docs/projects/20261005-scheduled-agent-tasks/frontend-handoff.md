# 定时 Agent 任务 - 前端实施标准与交接规范

> **最后更新：** 2026-10-05
> **文档定位：** `apps/platform-web` 定时任务模块前端实施唯一事实源。已吸纳参考项目 `/Users/lijiaxin/PyCharmMiscProject/research/deer-flow` 的优秀交互实践，并彻底对齐平台控制面与前端开发规范。

---

## 1. 架构定位与设计基准

### 1.1 页面定位与规范对齐
- **技术栈**：Vue 3 + TypeScript + Pinia + Vite，UI 组件优先复用平台通用组件（`BaseButton`、`BaseSelect`、`SurfaceCard`、`PageHeader`、`PaginationBar`、`StatusPill`、`StateBanner`、`BaseIcon` 等）。
- **页面 Archetype**：
  - **列表页**：采用 **List Archetype**（标杆对齐 `src/modules/agents/pages/AgentsPage.vue`），使用现代化卡片网格（Card Grid）呈现，具备防挤压搜索栏、状态统计与过滤、分页条、空态与加载态。
  - **创建/编辑载体**：采用 **右侧工作台大抽屉（`ScheduledTaskFormDrawer.vue`）**，内部采用 **双栏工作台布局**（左侧 1.25fr 表单输入卡片，右侧 0.75fr Live Inspector 实时预览服务端下发的排期计划），避免跳转新页面破坏用户列表上下文。
  - **执行历史载体**：采用 **右侧历史抽屉（`ScheduledTaskRunsDrawer.vue`）**，按需懒加载指定任务的原生 Run 执行历史与审计错误，杜绝主列表 N+1 请求。
- **粒度与代码规范**（强制约束）：
  - 严格遵守 `apps/platform-web/docs/frontend-development-playbook.md`：
    - 单文件组件 `<script setup>` 行数 ≤ 150 行，超出必须抽取 Composable 或子组件。
    - `<template>` 嵌套深度 ≤ 5 层，Props 数量 ≤ 6 个。
    - 禁止把所有状态和逻辑堆砌在一个巨型文件内（坚决不学 DeerFlow 900 行单文件 `page.tsx`）。

### 1.2 路由与导航配置
- **路由路径**：`projects/:projectId/scheduled-tasks`
- **路由名称**：`workspace-scheduled-tasks`
- **路由元信息**：
  ```ts
  {
    path: "projects/:projectId/scheduled-tasks",
    name: "workspace-scheduled-tasks",
    component: () => import("@/modules/scheduled-tasks/pages/ScheduledTasksPage.vue"),
    meta: {
      title: "定时任务",
      requiredPermissions: ["project.runtime.read"],
      permissionProjectSource: "route",
    },
  }
  ```
- **侧边栏导航映射**（`src/router/routes.ts`）：
  ```ts
  "workspace-scheduled-tasks": {
    group: "项目管理",
    label: "定时任务",
    icon: "clock",
  }
  ```

---

## 2. 模块结构与组件拆分

```text
apps/platform-web/src/
└── modules/scheduled-tasks/
    ├── pages/
    │   └── ScheduledTasksPage.vue          # 列表主页面（卡片网格、筛选、分页、SFC script ≤ 150 行）
    ├── components/
    │   ├── ScheduledTaskCard.vue           # 单个任务卡片（展示标题、Agent、调度周期、下次执行、操作项）
    │   ├── ScheduledTaskFormDrawer.vue     # 创建/编辑抽屉（双栏：左表单卡片，右 Inspector 预览）
    │   ├── CronScheduleInput.vue           # Cron 预设与高级自定义输入联动组件
    │   ├── OnceScheduleInput.vue           # 单次执行时间选择器（安全时区偏移换算）
    │   └── ScheduledTaskRunsDrawer.vue     # 执行历史抽屉（分页 Runs、状态Tag、错误码解析、Thread跳转）
    ├── composables/
    │   ├── useScheduledTasks.ts            # 任务列表加载、启停、删除、防并发状态机
    │   ├── useScheduledTaskRuns.ts         # 历史记录按需分页加载
    │   └── useSchedulePreview.ts           # 防抖（300ms）调用 /preview 服务端预测
    ├── services/
    │   └── scheduled-tasks.service.ts      # 10 条产品 API 规范封装，带 x-project-id 与 http-error 解析
    ├── utils/
    │   ├── cron.ts                         # 移植自 DeerFlow 的纯函数预设生成与反解析算法
    │   ├── timezone.ts                     # IANA 时区与本地壁钟时间带偏移 ISO 换算工具
    │   └── error-mapping.ts                # scheduled_task_* 专有错误码人话字典
    └── types/
        └── index.ts                        # 前端 TypeScript 完整契约定义
```

---

## 3. 接口契约与数据模型

全部接口统一经由 `src/services/` 或模块内部 service 发送，统一携带 `x-project-id` 请求头，走已认证 Axios client，错误统一经由 `src/utils/http-error.ts` 处理。

### 3.1 API 路由矩阵（基础路径：`/api/scheduled-tasks`）

| 方法 | 路径 | 参数 / Body | 成功响应 | 权限要求 | 备注 |
|---|---|---|---|---|---|
| GET | `/` | `limit=20`, `offset=0`, `enabled` (可选) | `200`，`{ items: ScheduledTask[], total: number, limit, offset }` | `runtime.read` | 主列表，不含 last_run |
| POST | `/` | `TaskCreate` | `201`，`ScheduledTask` | `runtime.write` | 创建新任务 |
| POST | `/preview` | `Schedule`, `count=5` | `200`，`{ times: string[], timezone: string }` | `runtime.read` | 预测下发时间 |
| GET | `/:id` | 无 | `200`，`ScheduledTask` | `runtime.read` | 任务详情 |
| PATCH | `/:id` | `TaskUpdate` (仅脏字段) | `200`，`ScheduledTask` | `runtime.write` | 增量编辑（禁止改不可变字段） |
| POST | `/:id/pause` | 无 | `200`，`ScheduledTask` | `runtime.write` | 暂停任务（`enabled=false`） |
| POST | `/:id/resume` | 无 | `200`，`ScheduledTask` | `runtime.write` | 恢复任务（`enabled=true`） |
| DELETE| `/:id` | 无 | `204`，无正文 | `runtime.write` | 删除任务（不取消已入队 Run） |
| POST | `/:id/trigger`| 请求头 `Idempotency-Key` (UUID) | `202`，原生 Run (`{ run_id, thread_id, status }`) | `runtime.write` | 手动立即派发运行 |
| GET | `/:id/runs` | `limit=20`, `offset=0` | `200`，`{ items: ScheduledTaskRun[], total, limit, offset }` | `runtime.read` | 历史抽屉分页查询 |

### 3.2 实体类型定义 (`types/index.ts`)

```ts
export type ScheduleType = "cron" | "once";
export type ThreadMode = "fresh" | "reuse";
export type ScheduleStatus = "active" | "paused" | "exhausted";

export interface ScheduledTask {
  id: string;
  title: string;
  prompt: string;
  agent_key: string;
  schedule_type: ScheduleType;
  cron?: string | null;
  run_at?: string | null;
  timezone: string;
  end_time?: string | null;
  thread_mode: ThreadMode;
  thread_id?: string | null;
  context: Record<string, any>;
  enabled: boolean;
  schedule_status: ScheduleStatus;
  next_run_at: string | null;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface ScheduledTaskRun {
  cron_id: string;
  run_id: string;
  thread_id: string;
  status: "pending" | "running" | "success" | "error" | "timeout" | "interrupted";
  trigger: "scheduled" | "manual";
  created_at: string;
  updated_at: string;
  error_code: string | null;
}
```

---

## 4. 关键交互机制与边界治理

### 4.1 列表数据与历史数据彻底解耦（防 N+1 灾难）
- **事实基准**：主列表接口 `GET /api/scheduled-tasks` 仅返回调度定义，不包含任何 `last_run` 字段。
- **治理原则**：**主列表卡片坚决只展示调度本身的状态**（`schedule_status` 的 Pill 标签：活动中 `active`、已暂停 `paused`、单次已派发 `exhausted`，以及 `next_run_at` 下次执行时间、时区、Cron 表达式、目标 Agent）。
- **历史查询**：点击卡片上的【运行记录】按钮，打开 `ScheduledTaskRunsDrawer` 抽屉。抽屉展开时，才触发调用 `GET /api/scheduled-tasks/:id/runs`。抽屉顶部集中呈现该任务的最新运行状态与统计。

### 4.2 编辑模式强模式锁定（Mode Lock）与增量 PATCH
- **不可变字段锁定**：
  在编辑已有任务时，以下字段属于底层架构不可变属性：
  - `agent_key`（目标智能体）
  - `schedule_type`（调度类型：周期 vs 单次）
  - `thread_mode`（会话模式：fresh vs reuse）
  - `thread_id`（绑定的会话 ID）
  **UI 表现**：在抽屉中渲染为只读 Badge / Disabled 控件，提示“创建后不可更改，如需调整请新建任务”。
- **增量提交契约**：
  PATCH 提交的 Payload 必须经由 `exclude_unset` 过滤，仅提交用户实际修改的脏字段（dirty fields）：
  - 若为 `cron` 任务，禁止向后端发送 `run_at` 字段。
  - 若为 `once` 任务，禁止向后端发送 `cron` 或 `end_time` 字段。
  - `end_time` 支持传 `null` 清除；其余字段（`title`、`prompt`、`context`）禁止传 `null`。

### 4.3 调度输入与 DeerFlow 纯函数预设体系
全面吸纳 DeerFlow 的预设体验，移植纯函数解析算法至 `src/modules/scheduled-tasks/utils/cron.ts`：
1. **预设选项**：
   - `hourly`：每小时的第 N 分钟执行（`M * * * *`）
   - `daily`：每天几点几分执行（`M H * * *`）
   - `weekly`：每周特定几天（多选周一至周日）的几点几分执行（`M H * * D1,D2`）
   - `monthly`：每月第 N 天几点几分执行（`M H D * *`）
   - `custom`：高级自定义标准五段式 Cron 表达式
2. **服务端 `/preview` 防抖联动**：
   表单中的时区、预设或自定义表达式发生变化时，Composable `useSchedulePreview` 执行 300ms 防抖，向 `POST /api/scheduled-tasks/preview` 发起验证，将计算出的未来 5 次执行时间以时间线列表实时渲染在右侧 Inspector 中，给用户确定性反馈。

### 4.4 时区与本地壁钟时间换算（`utils/timezone.ts`）
- 后端强制要求 `run_at` 与 `end_time` 必须为未来时间、整秒、且携带精准 UTC 偏移（例如 `2026-10-06T09:00:00+08:00`）。
- **换算规则**：日期时间选择器获取的值为用户本地壁钟字符串（`YYYY-MM-DDTHH:mm:ss`）。
- 工具函数 `formatZonedIsoString(wallTime: string, timeZone: string): string` 必须通过 `Intl.DateTimeFormat` 计算目标 IANA 时区相对 UTC 的分钟偏移量，安全拼接输出符合 ISO 8601 标准且带有时区偏移的字符串，杜绝 12 小时时差与跨时区夏令时漂移。

### 4.5 会话模式（Thread Mode）与 Context 模型参数
- **会话模式**：
  - 默认选中 `fresh`（每次新建独立 Thread，隔离干扰，官方推荐）。
  - `reuse` 模式收起在“高级配置”折叠栏中。当用户切换到 `reuse` 时，展开黄色警示 Alert（提示“复用长期会话可能累积历史上下文并消耗更多 Token”），并提供合法 UUID 输入框与前端校验。
- **Context 模型配置**：
  - 不提供自由 JSON 文本域。
  - 提供标准的 `<BaseSelect>` 模型选择下拉框：默认选项为“跟随项目默认模型”（提交 `context: {}`）；若用户选择特定模型，则提交 `context: { model_id: selectedModelId }`。

### 4.6 立即触发（Trigger）与幂等防重
- 用户点击卡片上的【立即运行】按钮：
  1. 按钮进入 Loading 态，并立即通过 `crypto.randomUUID()` 生成唯一的 `Idempotency-Key`。
  2. 请求 `POST /api/scheduled-tasks/:id/trigger`，请求头携带该 key。
  3. 遇到网络超时或 502 时，重试沿用同一个 key。
  4. 后端返回 `202 Accepted` 后，按钮恢复，弹出全局成功 Toast，并提供两个快捷动作：
     - 【查看会话】：直接在当前窗口打开 `/projects/:projectId/chat/:threadId`。
     - 【查看记录】：自动呼出并刷新 `ScheduledTaskRunsDrawer` 抽屉。

### 4.7 错误码友好字典映射 (`utils/error-mapping.ts`)

| 后端错误码 / 场景 | 前端友好呈现标签 | 详情 Tooltip 与引导说明 |
|---|---|---|
| `scheduled_task_approval_required` | 🔴 **需人工审批中止** | 定时任务属于无人值守模式，智能体触发了人工审批（HITL）工具，系统已自动安全中止执行。 |
| `scheduled_task_execution_failed` | 🔴 **执行异常中断** | 智能体图运行发生未捕获异常，可点击会话链接排查执行详情。 |
| `scheduled_task_principal_revoked` | ⚠️ **凭据失效** | 任务创建者账号已失效或凭据被吊销，任务无法继续代行。 |
| `scheduled_task_project_revoked` | ⚠️ **项目权限失效** | 创建者已被移出当前项目。 |
| `scheduled_task_project_inactive` | ⚠️ **项目已停用** | 当前项目已被归档或处于非活跃状态。 |
| `scheduled_task_thread_deleted` | ⚠️ **绑定会话已删除** | 所复用的会话 Thread 已被清理删除。 |
| `scheduled_task_authorization_unavailable` | ⚠️ **授权校验超时** | 平台权限认证服务暂时不可达。 |
| `invalid_run_at` / `invalid_end_time` | 🟡 **时间无效** | 设定时间必须大于当前服务器时间，且年份不得超过 2099 年。 |

---

## 5. 权限接入规范（Permission Gate）

严格遵循 `apps/platform-web/docs/control-plane-page-standard.md`：
- **页面级守卫**：路由必须配置 `meta: { requiredPermissions: ["project.runtime.read"] }`。无只读权限者无法访问该页面。
- **按钮级控制**：
  使用 `const { can } = useAuthorization();`
  ```ts
  const canWrite = computed(() => can("project.runtime.write", activeProjectId.value));
  ```
  - 【新建任务】、【编辑】、【暂停】、【恢复】、【立即运行】、【删除】按钮受 `canWrite` 控制。
  - 若 `canWrite === false`，按钮禁用并置灰，Tooltip 提示“需要项目运行时写入权限 (project.runtime.write)”。

---

## 6. 实施步骤与验收路线

- **Step 1: 基础层搭建**
  - 创建类型定义 `types/index.ts`
  - 实现纯函数工具 `utils/cron.ts`、`utils/timezone.ts`、`utils/error-mapping.ts` 并编写对应的单元测试
  - 实现服务层 `services/scheduled-tasks.service.ts`
- **Step 2: 核心交互组件开发**
  - 实现 `CronScheduleInput.vue`（预设与自定义切换，防抖 preview 联动）
  - 实现 `OnceScheduleInput.vue`（本地壁钟时间转带偏移 ISO）
  - 实现 `useSchedulePreview.ts`
- **Step 3: 抽屉与详情组件开发**
  - 实现 `ScheduledTaskFormDrawer.vue`（双栏：左表单卡片，右 Inspector 预览；区分 Create 模式与 Mode Lock 的 Edit 模式）
  - 实现 `ScheduledTaskRunsDrawer.vue`（分页加载 runs，错误码转友好标签，Thread 跳转链接）
- **Step 4: 列表页组装与路由接入**
  - 实现 `ScheduledTaskCard.vue`
  - 实现 `pages/ScheduledTasksPage.vue`（卡片网格、筛选状态、分页条、空态与骨架屏）
  - 在 `src/router/routes.ts` 注册路由与导航项
- **Step 5: 验证与验收**
  - 运行 `pnpm test` 或 Vitest 跑通所有前端单元测试
  - 运行 `pnpm type-check`（vue-tsc）确保 0 类型错误
  - 运行 `pnpm build` 确保生产环境打包成功
