# Token 看板前端交接

> 2026-10-12。非前端范围已完成，B01容量门禁已解除，可以继续真实联调。前端W01–W04由前端同事负责；当前工作区已有同事的Web改动，本轮未改动或验收这些内容。全栈Final/人工验收及生产发布仍待接续，状态与证据以[05](05-delivery-and-verification.md)为准。

## 工作区与联调

本轮源码位于 **b2b1 Worktree**，基线 `116cc26f`，当前为 detached HEAD，改动尚未提交。请通过本项目文档所在目录定位仓库根；原路径后缀为 `.codex/worktrees/b2b1/ai-agent-platform`。不要只切到基线提交后认为已经取得这些改动，也不要复用其他 Worktree 的可写依赖或环境文件。

| 项目 | 本轮地址/标识 |
|---|---|
| 环境 | `wt_43d02afc6100` |
| Web | `http://127.0.0.1:28226` |
| Platform API | `http://127.0.0.1:29493` |
| Runtime | `http://127.0.0.1:24138`，前端不直接请求 |
| 资源 | Worktree 自有原生 PostgreSQL/Redis、独立 Worker，`RUNTIME_BACKEND=local` |

在仓库根执行；文档命令不加 RTK 前缀：

```bash
bash "scripts/local-stack.sh" status
bash "scripts/local-stack.sh" start
bash "scripts/local-stack.sh" restart-one platform-api
```

实际地址始终以 `status` 为准；本地账号遵循 Worktree 规范中的 `admin / admin123456`。JWT、内部签名密钥与数据库密码保留在 `.local-stack/`，不复制进前端配置。另开 Worktree 时遵循 [资源隔离规范](../../standards/worktree-development.md)，独立初始化和安装依赖。

## 已提供的接口与职责边界

| 方法与路径 | 作用 | 权限要求 | 注意事项 |
|---|---|---|---|
| `GET /api/usage/dashboard` | 当前租户的跨项目汇总、前窗、趋势与一种排行 | `platform.usage.read` | 默认包含租户下全部有效项目；可带 `project_ids` 重复参数筛选 |
| `GET /api/projects/{project_id}/usage/dashboard` | 单项目相同报表 | `project.usage.read` | 严禁带 `project_ids` 参数；锁定路径项目 |
| `GET /api/projects/{project_id}/usage/runs` | 当前项目可查看的运行分页，数字只覆盖筛选期间 | `project.usage.read` 加当前 Thread ACL | 必须指定单一 `project_id`；平台无跨项目 runs 接口 |

沿用现有 HTTP 客户端和登录认证。项目聚合由路径项目决定；打开旧 Run Usage 详情时必须携带该行数据的 `x-project-id`，不能使用顶栏另一个项目。公共接口拒绝 `x-usage-query-*` 内部签名头，前端无须实现 HMAC。

**权限与角色映射守卫：**
- 角色真实名称：平台 `platform_super_admin / platform_operator` 获平台汇总权限；`platform_viewer` 没有。项目 `project_admin / project_editor` 获项目用量权限；`project_executor` 没有，系统不存在 `project_viewer` 角色。
- **守卫原则**：菜单和路由必须以服务器返回的权限码判断（`authorization.can('platform.usage.read')` / `authorization.can('project.usage.read')`），严禁根据角色名称字符串硬编码判断。平台 operator 可看平台数字，但没有对应项目权限时项目明细返回 403。

**数据安全与内容隔离：**
- 聚合权限不会赋予私有会话读权限。明细先检查现有 owner/share/限时接管规则；汇总数字可能比可见明细的和大。
- 删除 Thread 后明细不再返回，原消费数字保留；删项目退出默认聚合范围。Run 删除记录过滤依赖现有成功审计，直接引擎删除或审计丢失的限制见 03，前端仍需处理旧详情 404。

## 参数规范与严苛校验守卫（防 400 避坑指南）

后端对参数配置了 `extra="forbid"` 并执行严苛校验，任何多余参数或格式偏差都将直接触发 400 `invalid_usage_analytics_query`。

### 1. 核心参数契约

`from/to` 同时必填，使用带 UTC 时区的 ISO8601，必须使用大写 `T` 和 `Z`（例如 `2026-10-01T00:00:00Z`），严禁传本地时间或带空格的日期。时间窗正向且跨度满足：`0 < to - from <= 90 天`。

| 参数 | 适用接口 | 约束与类型 | 前端联动与避坑规约 |
|---|---|---|---|
| `timezone` | 两类 Dashboard | `Asia/Shanghai`（默认）或 `UTC` | 仅决定服务端的按日/小时分桶切分与展示基准 |
| `granularity` | 两类 Dashboard | `day`（默认）或 `hour` | **大坑防呆**：`granularity=hour` 时跨度必须 `to - from <= 7 天`！前端必须做双向联动防呆：切换到小时时限制时间选择在 7 天内；时间跨度超过 7 天时自动回退为“天”并禁用“小时”选项 |
| `project_ids` | **仅平台 Dashboard** | 重复参数，每项 UUID，最多 200 项 | **序列化大坑**：Axios 必须配置 `paramsSerializer` 为原生重复键（如 `project_ids=uuid1&project_ids=uuid2`），严禁序列化为中括号 `project_ids[]=uuid1`（后端当未知字段报错）；**单项目 Dashboard 严禁携带此参数** |
| `model_id` / `model_mapping` | 全部接口 | catalog UUID 或明确枚举 `unmapped` | **互斥约束**：二者绝对互斥，选具体模型则不传 `model_mapping`，选未映射则不能传 `model_id`，不可同时发送 |
| `agent_id` | 全部接口 | 平台 Agent UUID | **致命大坑**：后端在多项目平台查询时**直接拒绝 `agent_id`**！仅当单项目看板、或平台看板已明确且仅勾选了 1 个项目时才允许使用。多项目状态下前端筛选栏必须禁用/隐藏 Agent 选项并提示“请先限定单项目” |
| `purpose` | 全部接口 | `agent / summarization / memory_extraction / vision / other` | 业务目的，未选则不传 |
| `scope` | 全部接口 | `primary / subagent / auxiliary` | 范围层级，未选则不传 |
| `group_by` | 两类 Dashboard | `project / model / agent / purpose / scope`，默认 `model` | **单项目防呆**：单项目看板中隐藏 `group_by=project` 选项（单项目无对比意义） |
| `rank_by` | 两类 Dashboard | `known_total_tokens / known_cost_usd / observed_call_count` | 排行维度，默认 `known_total_tokens` |
| `top_n` | 两类 Dashboard | 1–50，默认 10 | 必须为纯数字字符串，上限 50 |
| `limit` | **仅 Runs 接口** | 1–200，默认 50 | 候选扫描预算；单次扫描上限，不可超过 200 |
| `cursor` | **仅 Runs 接口** | 15分钟有效的密文字符串 | 绑定身份/租户/项目/全部筛选。**任何筛选变动必须立即丢弃并置空 cursor** |

### 2. 请求样例

```text
# 平台汇总
GET /api/usage/dashboard?from=2026-10-01T00%3A00%3A00Z&to=2026-10-08T00%3A00%3A00Z&timezone=Asia%2FShanghai&granularity=day&group_by=model

# 平台多项目筛选 (注意重复参数格式)
GET /api/usage/dashboard?from=...&to=...&project_ids=10000000-0000-0000-0000-000000000001&project_ids=10000000-0000-0000-0000-000000000002

# 单项目汇总 (不可带 project_ids)
GET /api/projects/10000000-0000-0000-0000-000000000001/usage/dashboard?from=...&to=...&group_by=agent

# 运行明细分页 (严格参数白名单，不可带看板专有参数)
GET /api/projects/10000000-0000-0000-0000-000000000001/usage/runs?from=...&to=...&limit=50&cursor=...
```

## DTO 与展示口径

冻结类型和全状态样例位于 [fixtures](fixtures/README.md)。`UsageDashboardV1` 与 `UsageRunPageV1` 的关键口径规则如下：

### 1. Token 集合与金融级精度规约
- `tokens` 完整对象：缺失时为 `null`；`known_tokens` 为已知小计（也可能为 `null`），**严禁将 `null` 视同补 0**。
- **集合从属关系（严防重复累加）**：
  $$\text{total\_tokens} = \text{input\_tokens} + \text{output\_tokens}$$
  其中 `cache_read_tokens` 与 `cache_creation_tokens` 属于 `input_tokens` 的子集；`reasoning_tokens` 属于 `output_tokens` 的子集。
  **铁律**：计算总 Token 时严禁把缓存和推理子集独立重复相加！测试样例中 input=1000、output=100、cache_read=200、cache_creation=100、reasoning=30，总 Token 必须严格为 **1100**。
- **金额精度**：金额为 **12 位小数的 USD 字符串**（如 `"0.002580000000"`），前端**禁止转为 JS Number 做浮点数算术计算**，防止精度丢失。复用既有 `formatCostUsd()`，极小正金额统一显示为 `< $0.0001`，绝不能显示为“免费”。

### 2. 统计维度与数据质量
- `recorded_run_count` 是当前期间匹配调用的去重 Run 数量，不能将各时间桶或各模型的数值简单加和。
- `coverage`：已报告与计价比例分母均为 `observed_call_count`，若分母为 0 则显示 `—`。
- `cache_read_ratio`：仅针对输入与缓存均已知样本的比值，非请求级命中率。
- `as_of`：快照时刻戳。若刷新导致服务端数据补齐，游标重置从第一页开始。
- **常驻用户提示说明条（参考 deer-flow 最佳实践）**：
  看板顶部常驻清晰提示条：**“已采集当前范围内 Agent 运行用量；辅助开销（标题生成、推荐问题等）及未落账调用未计入。由于系统重试、内部调用及供应商计费周期差异，汇总数据与供应商账单可能存在偏差。”**

### 3. 接口状态机矩阵

| 接口状态 | 页面呈现与交互动作 |
|---|---|
| `available`，完整 0 | 正常展示数字 0，附带说明“所选区间已记录用量为 0”，不暗示未发生调用 |
| `partial` | 显示已知小计，打上 partial 警戒标签与说明，全页正常可用不报错 |
| `disabled` | 显示“新采集功能已关闭”，若有历史数据则正常渲染并标注历史归档状态 |
| `unavailable/not_recorded` | 提示“尚未采集该时间范围数据”，图表留空或展示空态插图，禁止画成 0 消费 |
| `unavailable/backend_unavailable`，HTTP 200 | 数据查询故障，保留重试按钮与局部骨架，不弹全局报错弹窗 |
| HTTP 401 / 403 | 身份/权限过期或不足。单项目 403 展示项目无权说明，绝不误触全局登出 |
| HTTP 422 `usage_aggregate_range_exceeded` | 提示“查询结果超出最大上限，请缩小时间跨度或筛选范围” |
| HTTP 502 / 503 / 504 | 上游临时故障或超时，提供就地“重试”按钮，保留现有查询参数 |

新增503 `usage_query_capacity_exhausted` 表示看板整链路排队/执行超过5秒；使用原HTTP错误处理保留筛选并提供手动重试，不能显示成无权限或0消费。对应 `fixtures/error-query-capacity.json`；三个成功响应DTO、HMAC和权限规则均沿原版。

## 前端需求与验收清单（W01–W04 细化方案）

组件交互详细设计及同事已记录的完成状态以 [04](04-web-dashboard.md) 为准，以下保留原需求供最终后端联合复验对照：

### W01：类型契约、Service 层、权限守卫与路由导航
- **权限与类型**：在 `apps/platform-web/src/types/management.ts` 补充 `platform.usage.read` 与 `project.usage.read`；完善 Zod Schema 与 TypeScript 类型定义。
- **Service 实现**：在 `src/services/usage/usage.service.ts` 实现三个 GET 接口：
  - 严谨处理 Axios `paramsSerializer`（原生重复键 `project_ids`）；
  - 严格参数白名单过滤，禁止多余参数泄露；
  - 完整接入 `AbortSignal` 与共享错误解析 `extractPlatformHttpError`。
- **路由与导航**：
  - 平台路由 `/workspace/usage`（权限 `platform.usage.read`，导航组“平台管理”）；
  - 项目路由 `/workspace/projects/:projectId/usage`（权限 `project.usage.read`，导航组“项目管理”，`permissionProjectSource: 'route'`）；
  - **隔离守卫**：平台路由严格从路由 path 取参数，禁止被顶栏项目切换篡改为项目视图。

### W02：页面容器、筛选联动、指标卡与防竞态
- **页面组件**：创建 `UsageDashboardPage.vue`，实现平台与单项目双 scope 状态分流。
- **筛选工具栏联动**：
  - 粒度与时间跨度双向约束联动（小时粒度强制 ≤7 天）；
  - 平台多项目模式下自动禁用 Agent 下拉；
  - 单项目模式下自动锁定项目并隐藏 `group_by=project`；
  - 筛选与 URL Query 双向同步，URL 仅保留合法筛选参数。
- **4 组指标卡**：
  - 已记录 Token（完整值 vs 已知小计，前窗对比率，null 渲染 `—`）；
  - 输入 / 输出（含缓存读/写与推理明细）；
  - 估算成本（保留 12 位字符串精度，极小值 `< $0.0001`）；
  - 已采集调用 / Run 数（质量与覆盖率）。
- **防竞态与生命周期**：
  - 切换项目、租户、筛选条件时：自增 epoch、中止（abort）旧请求、立即清空旧数据与快照，拒绝迟到响应上屏。

### W03：模块内原生 SVG 趋势图、排行分解与无障碍
- **原生 SVG 图表**（拒绝外部图表库，遵循 KISS/YAGNI 原则）：
  - `UsageTrend.vue`：日/小时输入输出堆叠柱状图与成本折线图（最多 200 点）；
  - 主题自适应：坐标轴与文字使用 Tailwind CSS 类（`stroke-gray-200 dark:stroke-dark-700`，`fill-gray-500 dark:fill-dark-400`）；
  - 空值断点：`tokens=null` 显示为视觉断口，不画成 0；`partial` 桶使用 SVG `<pattern>` 斜条纹填充；
  - A11y 与可替代性：提供“图表 / 数据表格”切换视图，保证键盘与读屏器无障碍支持。
- **排行与钻取**：
  - `UsageBreakdown.vue`：Top10 横向进度条 + “其他”分组折叠展开；
  - 点击排行项自动反填至筛选栏形成 Chip 钻取过滤。

### W04：运行明细分页、BaseDrawer 改造与联合回归
- **明细分页与引导态**：
  - 平台看板全量模式下显示引导卡：“请先在上方筛选具体项目以查看运行明细”；
  - 单项目模式下启用 Keyset 分页，按 `(project_id, run_id)` 去重；
  - **空页带 Cursor 处理**：当返回 `items: []` 但 `next_cursor` 存在时，给出明确提示：“当前批次候选已受权限过滤，可继续加载后续批次”，杜绝界面无响应死机假象。
- **抽屉与 `RunUsage.vue` 改造（解决双 Header 与双滚动条）**：
  - 为 `RunUsage.vue` 扩展 `headless: boolean` prop，在抽屉模式下隐藏自带的 `<header>` 栏与外层右侧边框；
  - `BaseDrawer.vue` 挂载时指定 `flush=true`，将抽屉标题统一定义为“完整运行用量”，操作按钮与关闭逻辑收敛由 `BaseDrawer` 管理；
  - 详情参数准确透传行级别的 `projectId/threadId/runId`，抽屉关闭立即卸载并 abort 请求。
- **联合回归与多视口验收**：
  - 覆盖 1440×900、1024×768、390×844 三种视口及深浅双主题；
  - 运行 Vitest、vue-tsc、ESLint 及生产打包验证。

## 当前后端状态与接续范围

**B01已解除。** 在完整30天的百万调用/50项目下，公开接口两轮均30/30可用，读p95 1220.89/1171.99ms、p99 1309.52/1172.77ms；两采集写入p95增幅16.01%/11.62%、无持久化失败，200项目/90天与Run ACL通过。重启后的真实模型核账、权限/撤权、私有内容隔离、数据库故障及保留迁移链回退也通过。证据及缓存/数据分布限制见[05](05-delivery-and-verification.md)。

后端已实施Runtime内部可重建桶和整链路并发预算，公开DTO继续沿本版。04已有同事的W01–W04完成及测试记录，本轮保留且不复验；请核对新增503、最终后端联调、三尺寸/主题/键盘及真实浏览器链，完成用户人工验收后记录全栈Final并另行发布。

## 可直接转发的话术

> Token看板后端和B01优化已在b2b1 Worktree完成，尚未提交。百万/50项目/完整30天公开接口两轮通过原门槛，B01已解除；三个GET接口、成功DTO和权限沿原版，新增503 `usage_query_capacity_exhausted` fixture。04中你已记录的W01–W04和测试结果保留；请核对503临时故障状态、与最终后端联调并完成浏览器联合复验和人工验收。503保留筛选手动重试，金额12位字符串/null/空页cursor等原规则继续沿用。Web/API地址为 http://127.0.0.1:28226 / http://127.0.0.1:29493，以local-stack status为准。后端没有复验前端；全栈Final和人工验收完成后再申请发布。
