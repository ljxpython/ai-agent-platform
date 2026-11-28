# 专题 05：前端工作台设计（借鉴 LightRAG）与全链路浏览器验收

> 所属项目：[独立评测中台迁移与平台原生化改造方案](README.md)｜状态：**方案已对齐（方案 X + 原生 Vue 规范 + 风险预警 + 并发 1~5 已确认，待开始编码）**

## 1. 设计目标：彻底告别 MLflow 壳层，融合两家之长

前端设计要解决“原先在 MLflow 页面里展示用例集、多轮对话、对比矩阵和运行进度非常别扭且频繁卡死”的问题，同时避免 `AuthoringPage.tsx` 四千行单文件泥潭。

整体视觉与交互**借鉴 `../LightRAG` 评测工坊（`DatasetPanoramaView` + `EvaluationTaskCenter` + `EvaluationComparisonModal`）的清晰工作台动线**，并**完整保留 `../mlflow-eval-platform` 已经打磨出来的硬核 Agent 评测细节**（多轮动态博弈时间轴、隐藏事实/延迟夹具表单、Step 1~4 降噪、AI 出题 Copilot 与诊断专家抽屉），统一遵循 `apps/platform-web/docs/frontend-development-playbook.md`（Vue 3 + ECharts 6 + 平台标准组件）。

> **载体与工程规范已确认**：放弃旧 MLflow 前端及 iframe 方案，直接以 **Vue 3 + ECharts 6 原生重构进 `apps/platform-web`**。设计必须严格遵循：
> - `apps/platform-web/docs/frontend-development-playbook.md`（模块结构、Zod 契约与单组件粒度拆解）
> - `apps/platform-web/docs/control-plane-page-standard.md`（控制面页面骨架与数据状态规范）
> - `apps/platform-web/docs/frontend-visual-baseline-standard.md`（统一使用 `PageHeader`、`pw-card`/`pw-panel`、`BaseSelect`、`DataTable`、`MetricCard`、`FilterToolbar`、`PaginationBar`、`SurfaceCard` 与双栏编排；严格禁止原生 `<select>`、高圆角毛玻璃等违规样式，支持平台统一深浅主题）。
> 功能结构借鉴 `../LightRAG` 评测工坊（全景、就绪守卫、矩阵打擂、PK 对比）并原生融合 Agent 多轮博弈/工具轨迹特性。

---

## 2. 核心页面与交互模块设计

替换当前 `apps/platform-web/src/modules/evaluation/EvaluationMovedPage.vue` 占位页，构建 5 个职责清晰的视图模块：

### 2.1 资产全景与题库工作台（借鉴 `LightRAG/DatasetPanoramaView`）
- **顶部宏观指标卡**：纳管评测集总套数、覆盖来源项目、累计考题数、当前盲测集（Holdout）占比与最近一次门禁通过率。
- **三源资产筛选与标签**：支持按题库分类（业务黄金集 / 线上会话回流集 / 行业基准集 / 回归集）、Dev vs Holdout 分区、来源项目、关键词实时过滤；明确展示 `[来源项目]` 与 `[默认靶场]`，彻底消除旧版切换连接丢题库的困惑。
- **快捷入口**：
  - 「新建空白题库」 / 「导入标准 JSONL」
  - 「从线上会话挑选转化」（直接复用现有 `PickSessionMaterials.vue` + `SendSessionMaterials.vue`）
  - 「一键进入详情编辑」 / 「一键发起评测」

### 2.2 评测集与用例编辑器（融合 `Authoring` 降噪与 `Simulation` 配置）
采用 `PageHeader -> 三栏工作区`（严格控制单组件粒度，抽离 Composable）：
- **左栏（题目目录树）**：按 `dev` / `holdout` 分组展示用例列表与标签徽章，支持新增、复制、删除、拖动/筛选。
- **中栏（分场景清晰配置台）**：
  - **来源背景卡片**（默认收起冗长会话原文，点击弹窗查看双色 IM 对话流回放，保留脱敏标识）；
  - **执行模式互斥切换**：固定脚本多轮（每轮 Prompt + 期望产物/回复 + 预设审批决定） vs 动态用户博弈（`goal` / `user_mode` 角色风格 / 可增删 `hidden_facts` 与 `delayed_fixtures` 手风琴 / `interrupt_strategy` 澄清与计划审阅开关）；
  - **分级指标勾选区**：清晰分为 L1 硬规则（物理工件 `json_subset`/`csv_rows`/禁写/审批防偷跑/工具约束）与 L2 语义/DeepEval 指标（忠实度/业务事实/召回率等）；
  - **版本冻结与发布栏**：保存草稿不覆盖已发布版本，点击「冻结发布新版本」生成不可变 `content_hash` 版本号。
- **右栏（可折叠 AI 出题 Copilot 抽屉）**：支持对话式扩题、补充边界条件与断言规则，生成候选后用结构化 Diff 卡片逐题勾选采纳/忽略，保护手工修改不被覆盖。

### 2.3 发起评测与矩阵打擂弹窗（融合隔离靶场风险警告 + 能力分级 Readiness + 并发设置）
- **目标隔离项目选择器与风险警告（已确认规则）**：允许用户从全部具有 `project.runtime.execute` 权限的项目中选择目标隔离靶场；若选中**非专用测试靶场项目**，弹窗显著展示**黄/红风险警告条**（提示将写入真实项目 Thread/预算/Trace），需勾选/二次确认后方能开考；若为专用评测项目则绿色标识。
- **开考前能力分级与就绪度守卫（Readiness Guard，已确认）**：选定目标项目、待测 Graph（开放 `dearflow_agent` / `showcase_demo` / `reference_agent` / `workflow_demo`）与**平台模型目录中的裁判 LLM / Embedding 模型**后，实时校验环境状态与用例兼容性；若用例包含当前 Graph 不支持的断言（如对无工作区的 `reference_agent` 配了文件工作区断言），弹窗直接标红拦截或提示降级处理。
- **打擂矩阵与并发配置（已确认范围）**：
  - 支持单配置运行，也支持勾选多组参数矩阵（对比不同模型 `model_id`、不同 Graph 或配置）；
  - 配置 **并发度 `concurrency`（默认 `3`，可调范围固定 `1 ~ 5`）**、抽测 vs 全量、**重复次数 $k$（默认 1，核心题可选 3/5 测 Pass^k）**。

### 2.4 任务运行大厅与多维结果诊断页（借鉴 `EvaluationTaskCenter` + `SimulationTimeline`）
- **任务大厅**：按题库聚合展示历史运行趋势、最高分/最新分与质量涨跌（Delta +/-）；实时进度条与并发执行日志流；提供 **【⏸ 暂停】、【▶ 继续未完成】、【🔁 仅重跑失败题】、【⚡ 同证据重评】、【🛑 中止】** 按钮。
- **7 维全景成绩带（Scorecard）**：
  - 展示门禁状态（PASS / FAIL / ERROR）、L1 规则通过率、L2 语义均分、TSR / Pass@1、死循环率、TTFT & P95 耗时、总 Token 与费用、异常分层分布（业务未达标 vs 服务端故障 vs 裁判异常）。
- **单题深度取证舱**：
  - 左栏：**动态博弈与中断轴**（用户发言 → 澄清填表 → Plan 打回与核准 → 延迟夹具上传 → HITL 审批前文件基线核对 → 终态）；
  - 右栏 Tab：对话流 & 工具调用明细 / **物理工件基线 vs 产出文本 Diff** / L1 & L2 逐指标得分与裁判理由 / **L3 人工抽检标注栏**（一键标 Pass/Fail 并记录校准一致率）；
  - **MLflow 链路追踪直达**：每题旁挂载 `Trace ↗` 按钮，直接跳转到 MLflow 对应 `project-{target_project_id}` 的 Trace Waterfall 页面查看底层 Span 耗时与模型原始报文，各司其职不重复造轮子。
- **右侧独立诊断专家抽屉**：一键提问当前运行或单道失败题，返回三层 Gap 归因（Data / Retrieval / Reasoning Gap）与具体修改建议。

### 2.5 多版本横向对比 PK 视图（借鉴 `LightRAG/EvaluationComparisonModal`）
任意勾选 2 场评测运行（或矩阵打擂中的两个组别）点击【横向对撞 PK】：
1. **宏观对比 Tab**：综合分/通过率 Delta、胜/平/负战绩统计、**严重退化预警（Regressed：老版本过、新版本挂的题目数标红告警）**、**ECharts 7 维能力雷达图** + 指标差分表；
2. **用例胜负榜（Side-by-Side Diff）Tab**：支持筛选“仅看分歧题 / 严重退化 / 对比组胜出”，展开左右并排查看输入输出、工具调用序列与检索切片重合度 Diff；
3. **成本与性能 Tab**：对比 Token 消耗、费用、TTFT 首字延迟、P50/P95 延迟与异常率差异。

---

## 3. 全链路浏览器验证与截图计划（开发完成后执行）

在后端 `apps/platform-api`、`apps/runtime-service`、`apps/eval-runner` 与前端 `apps/platform-web` 全部实施及单测/类型检查通过后，通过 `/browser`（调用 `browser` subagent，默认使用规定模型与沙箱隔离）在真实本地/测试全栈环境执行端到端验收并对关键步骤截图留痕：

| 验收步骤 | 验证动作与链路 | 关键预期与截图留痕点 |
|---|---|---|
| **S1. 资产全景与会话转化** | 在业务项目选中真实会话 → 转为评测集 → 进入工作台查看资产全景与血缘标签 | 验证不报错、异步通知跳转准确、全景卡片清晰（截图 1：`eval-panorama-and-conversion.png`） |
| **S2. 编辑、AI 辅助与发布** | 在评测集编辑器用 AI Copilot 补全/微调一题、手动修改断言并冻结发布新版本 | 验证草稿/发布隔离、Diff 采纳正常、不可变版本号生成（截图 2：`eval-editor-copilot-publish.png`） |
| **S3. 指定隔离靶场并发开考** | 发起评测时显式选择**隔离靶场项目**，通过 Readiness 守卫，设置 `concurrency >= 2` 与多配置矩阵启动 | 验证线上源项目无新增线程/污染，并发多 Case 同时推进与暂停/续跑（截图 3：`eval-launch-isolation-concurrency.png`） |
| **S4. 7 维指标、Trace 直达与诊断** | 任务结束后查看 Scorecard 7 维指标、单题物理工件与博弈轴、呼出诊断专家提问、点击 `Trace ↗` 打开 MLflow | 验证 L1/L2/TTFT/费用完整展示、Gap 归因输出、MLflow Trace 真实可打开（截图 4、5：`eval-results-7d-diagnosis.png`、`mlflow-trace-drilldown.png`） |
| **S5. 多版本 PK 对比** | 勾选两组运行结果打开横向对比 PK 视图，查看 ECharts 雷达图、退化标记与用例 Diff | 验证宏观差分、雷达图深浅主题与 Side-by-Side Diff 正常（截图 6：`eval-comparison-pk.png`） |

---

## 4. 本专题规划任务（待启动实施）

### Task 5.1：实现 `platform-web` 评测工作台核心模块
**状态：** 待开始（原生 Vue 载体、视觉基线与后端方案 X 均已对齐）。
**完成标准：** 替换 `EvaluationMovedPage.vue`，落地资产全景、编辑器、隔离靶场开考弹窗（含风险警告、能力分级 Readiness 与 `1~5` 并发调节）、并发任务大厅、7 维结果详情、PK 对比与诊断抽屉；完成 Vitest 单元测试、`pnpm typecheck`、`pnpm lint` 与 `pnpm build`。
**涉及位置：** `apps/platform-web/src/modules/evaluation/`、`apps/platform-web/src/router/routes.ts`。

- [ ] 搭建模块服务层、Zod 契约与状态 Composable（按组件粒度规范拆解，严格遵守既有视觉组件基线）。
- [ ] 实现资产全景页、三栏用例编辑器与连接 `runtime-service` `eval_copilot` 的 AI Diff 抽屉。
- [ ] 实现隔离靶场开考弹窗（含非专用项目风险警告、平台裁判模型选择、能力分级 Readiness 守卫、并发 `1~5` 与矩阵配置）。
- [ ] 实现任务大厅（暂停/续跑/重试失败）、7 维成绩带（含真实 TTFT）、单题博弈/工件取证舱、MLflow Trace 跳转与 `eval_diagnosis` 诊断抽屉。
- [ ] 实现基于 ECharts 的多版本横向对比 PK 视图与 L3 人工抽检标注界面。

### Task 5.2：全栈联调与 `/browser` 端到端真实验证
**状态：** 待开始（依赖全栈模块就绪）。
**完成标准：** 启动 `platform-web` + `platform-api` + `runtime-service` + `eval-runner` + `MLflow` + PostgreSQL + Redis 完整链路，完成 S1~S5 全部场景真实操作并通过 `/browser` 留存关键步骤截图。
**涉及位置：** `docs/projects/20261128-independent-eval-platform/implementation/`。

- [ ] 准备独立测试环境与隔离靶场项目（遵循 `docs/standards/worktree-development.md`）。
- [ ] 使用真实模型运行并发评测用例与对比矩阵，核对 MLflow Trace 写入与回查。
- [ ] 调用 `/browser` 完成 S1~S5 全链路走查并保存关键截图与验证报告。
