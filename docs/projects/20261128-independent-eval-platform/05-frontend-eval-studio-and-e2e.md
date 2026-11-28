# 专题 05：前端工作台设计（借鉴 LightRAG）与全链路浏览器验收

> 所属项目：[独立评测中台迁移与平台原生化改造方案](README.md)｜状态：**正在进行前端全面升级对齐与全栈联调（in_progress）**

## 1. 设计目标：彻底告别 MLflow 壳层，融合两家之长

前端设计要解决“原先在 MLflow 页面里展示用例集、多轮对话、对比矩阵和运行进度非常别扭且频繁卡死”的问题，同时避免 `AuthoringPage.tsx` 四千行单文件泥潭。

整体视觉与交互**借鉴 `../LightRAG` 评测工坊（`DatasetPanoramaView` + `考题表格汇总` + `EvaluationTaskCenter` + `EvaluationComparisonModal`）的清晰工作台动线**，并**完整保留 `../mlflow-eval-platform` 已经打磨出来的硬核 Agent 评测细节**（多轮动态博弈时间轴、隐藏事实/延迟夹具表单、Step 1~4 降噪、AI 出题 Copilot 与诊断专家抽屉），统一遵循 `apps/platform-web/docs/frontend-development-playbook.md`（Vue 3 + ECharts 6 + 平台标准组件）。

> **载体与工程规范已确认**：放弃旧 MLflow 前端及 iframe 方案，直接以 **Vue 3 + ECharts 6 原生重构进 `apps/platform-web`**。设计必须严格遵循：
> - `apps/platform-web/docs/frontend-development-playbook.md`（模块结构、Zod 契约与单组件粒度拆解）
> - `apps/platform-web/docs/control-plane-page-standard.md`（控制面页面骨架与数据状态规范）
> - `apps/platform-web/docs/frontend-visual-baseline-standard.md`（统一使用 `PageHeader`、`pw-card`/`pw-panel`、`BaseSelect`、`DataTable`、`MetricCard`、`FilterToolbar`、`PaginationBar`、`SurfaceCard` 与双栏编排；严格禁止原生 `<select>`、高圆角毛玻璃等违规样式，支持平台统一深浅主题）。
> **导航专栏约定**：在 `AppSidebar.vue` / `useNavigation.ts` 中设立独立侧边栏分组 **「评测中心」**（位于 `Dear Agent` 之后），精简收口为 3 个直达入口：`题库资产全景`、`考题表格与出题`、`打擂任务大厅`；**多版本对比 PK 与门禁直整合入「打擂任务大厅」内发起与展示（不再单独设置左侧对比页面，旧 `/evaluation/compare` 路径重定向至打擂任务大厅）**，定时巡检自动调度执行确认后置实现；默认推理与裁判模型优先选择启用中的 `xiaok` DeepSeek 模型。

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

## 4. 本专题规划任务（实施与验证清单）

### Task 5.1：搭建 `platform-web` 评测工作台基础骨架（初版）
**状态：** 已完成（done，基础路由、服务层、初版组件、`vue-tsc` 与 Vitest 通过；首轮联调暴露出开考弹窗未自动触发 Readiness 导致 HTTP 400 进 ErrorBoundary、默认选错故障测试模型、侧边栏缺独立评测专栏，且交互深度未对齐 LightRAG）。
**完成标准：** 建立 `modules/evaluation/` 基础目录与前后端联调通路。
**涉及位置：** `apps/platform-web/src/modules/evaluation/`、`apps/platform-web/src/router/routes.ts`。

- [x] 搭建模块服务层与基础 Composable。
- [x] 建立初版全景/编辑/开考/对比页面并通过初轮静态构建。

### Task 5.1b：缺陷根治、侧边栏评测专栏与 LightRAG 同级体验全面重构
**状态：** 已完成（done，全部交互改造、StatusPill 文本对齐与雷达图切 Tab 重绘均已修复并通过 `vue-tsc`、Vitest 9 passed 及 Vite 构建）。
**完成标准：**
1. **缺陷与模型默认值根治**：开考弹窗打开与切换项目/Agent 时自动执行 Readiness Guard 并显式弹出非沙箱风险勾选；全部异步操作由 `resolvePlatformHttpErrorMessage` 收口到页面内提示，杜绝 Axios 异常触发全页 `ErrorBoundary`；默认推理模型与裁判模型优先选中平台启用中的 `xiaok` DeepSeek 模型。
2. **侧边栏独立「评测中心」专栏**：在 `routes.ts` 与 `useNavigation.ts` 注册独立大组「评测中心」，拆出「题库资产全景」「考题表格与出题」「打擂任务大厅」「对比 PK 与门禁」直达入口。
3. **资产全景重构（对标 LightRAG 全景）**：宽体题库资产卡（来源项目徽标、版本哈希、题目数、默认图、展开显示来源文档/会话血缘与前 3 题预览 + 「前往表格查看全部 N 题 →」 + 删除题库）；顶部接入「全部 / 专属 / 基准」分段筛选与「从线上会话导入」（复用 `PickSessionMaterials`）和「导入 JSONL」（带默认目标 Graph 选择）入口。
4. **考题表格汇总与 AI Copilot 真接入（对标 LightRAG 表格编辑）**：全宽内联可编辑高密度表格（序号、标识/分区、Question 内联编辑、Ground Truth/期望答案内联编辑、上下文与工件摘要芯片、批量保存与单行删除）；右侧滑出「Agent 高级配置抽屉」保留多轮、动态博弈 `hidden_facts` / `delayed_fixtures` 与物理产物断言；右侧滑出真连通 `runtime-service` 图 `eval_copilot` 的流式对话抽屉并支持识别候选考题一键采纳。
5. **打擂任务大厅、7 维取证与诊断专家真接入（对标 LightRAG 任务大厅）**：顶部 4 张大卡（总打擂场次/并发进行中/历史平均分/最高通过率）；按题库折叠聚合打擂组（最高均分 + 最新得分 & Delta 涨跌）；运行进度/日志折叠、重跑/对比/`MLflow ↗` 按钮；单场 7 维 Scorecard 与逐题白盒详情（真实回复/得分/L1-L2 理由/L3 人工标注）；真连通 `eval_diagnosis` 图的三层 Gap 归因对话抽屉；`ComparisonPkDialog` 完整 3 Tab（宏观雷达、Case Diff 过滤、成本 TTFT 延迟）。
**涉及位置：** `apps/platform-web/src/router/routes.ts`、`apps/platform-web/src/composables/useNavigation.ts`、`apps/platform-web/src/modules/evaluation/`、`apps/platform-api/src/platform_api/modules/evaluation/`。

- [x] 修复开考自动 Readiness 检查、全局错误处理（告别 ErrorBoundary）、以及 `xiaok` DeepSeek 默认模型选择。
- [x] 在侧边栏新增独立「评测中心」专栏及 4 个子能力入口，更新 `routes.spec.ts` 与导航测试。
- [x] 重构 `DatasetPanoramaPanel` 对齐 LightRAG 全景卡片、三源筛选、样例预览与会话/JSONL 导入（含后端删除/导入/样例摘要支撑）。
- [x] 重构 `CaseEditorPanel` 为全宽内联可编辑考题表格 + `CaseAdvancedDrawer` 高级抽屉 + 真连通 `eval_copilot` 抽屉与候选考题一键采纳。
- [x] 重构 `RunResultsPanel` & `ComparisonPkDialog` 为 4 大卡 + 题库折叠打擂组 + 7 维单题取证舱 + MLflow 跳转 + 真连通 `eval_diagnosis` 诊断抽屉，并修补 `StatusPill` 插槽文本与雷达图切 Tab 保留。
- [x] 通过 `vue-tsc --noEmit`、Vitest 全部单测与 `pnpm build`。

### Task 5.2：全栈联调与 `/browser` 端到端真实验证（每个功能点关键步骤截图）
**状态：** 已完成（done，三轮 `/browser` 全链路真实端到端回归通过，核心链路 0 报错且已留存全套真实流式响应、TTFT 实测、7 维白盒详情与五维差异 PK 雷达图截图；其中 `eval_copilot` 首次工具调用偶发一次 `runtime.execution_failed`，清空重置会话后流式生成与 2 道候选 JSON 识别正常完成，StatusPill 插槽与切 Tab 雷达图也已补充修复并通过单测构建）。
**完成标准：** 启动 `platform-web` + `platform-api` + `runtime-service` + `eval-runner` 完整链路，通过 `/browser` 依次验证全部功能点、零阻塞故障，并逐点留存关键步骤截图。
**涉及位置：** `docs/projects/20261128-independent-eval-platform/implementation/`。

- [x] 通过 `scripts/local-stack.sh start` 升级本地 PostgreSQL（`20261128_0016`）并修复预算版本倒挂恢复模型网关/问答小助手可用性。
- [x] 拉起接入真实执行器与平台模型裁判的 `eval-runner` 后台轮询并跑通真实 `xiaok` DeepSeek（`070cced3-350b-42ec-b678-994dd07b7078`）并发批跑（实测批次 `#653fa186` 状态 `completed`、`TSR 100%`、`TTFT P50 18309 ms` / `P95 30344 ms`）。
- [x] 调用 `/browser` 对问答小助手恢复、侧边栏「评测中心」专栏、题库全景与新建/JSONL 导入、考题表格内联编辑、`eval_copilot` 流式出题与候选识别、冻结版本与自动 Readiness + `xiaok` 模型并发开考、打擂大厅与 7 维成绩白盒详情、`eval_diagnosis` 流式三层 Gap 诊断以及五维差异对比 PK 雷达图与 Diff Tab 逐项真实测试并全部截图。

### Task 5.3：将对比 PK 集成进打擂任务大厅、全面重做三维度 PK 工坊与 `/browser` 全链路复验
**状态：** 已完成（done，`vue-tsc` 0 错、`vitest` 9 passed、`vite build` 通过，`/browser` 实测 0 console/network error 并留存 6 张全链路截图，包括新打擂 `#77350f73` 的真实 Token `469` / `$0.000717`、Radar 图 `509x288`、Side-by-Side 对照、性能拓扑双卡及切回/对调稳定性）
**完成标准：**
1. **收口导航与整合进打擂大厅**：移除左侧边栏与页头中的独立「对比 PK 与门禁」页面（`/evaluation/compare` 重定向至 `打擂任务大厅`）；对比 PK 直接由 `打擂任务大厅` 顶部工具栏与历史打擂勾选触发（自动避开同场次自对比）；将专用靶场切换按钮集成至大厅/开考入口，未实现的定时巡检 Cron 明确后置。
2. **重做多版本横向对撞 PK 工坊（对齐 LightRAG 第三、四、五幅图设计）**：
   - **壳层与工程诊断横幅**：宽度升级为 `full`，顶部增加动态工程诊断建议横幅、`[⇄ 对调基准]` 与同排 `基准 VS 对比` 实时下拉切换。
   - **Tab 1（宏观概览对决）**：修复 `v-show` / `v-else` 模板分支错位，并用 `ResizeObserver` + 动画延迟重试彻底解决 `BaseDialog` 过渡期 ECharts 0 宽高白屏问题；右侧配齐 7 维核心指标并排对比表（综合分、TSR、L1、TTFT P50/P95、总耗时、死循环率、Token 与费用及红绿 Delta）。
   - **Tab 2（用例胜负榜 Side-by-Side Diff）**：扩充后端 `compare_runs` 接口返回题目原文、黄金答案、双方实际回复正文、L1/L2 逐项得分与裁判理由、工具调用步数及 `MLflow Trace ↗`；前端支持全/退化/提升/持平过滤 + 关键词筛选，左右并排卡片展示真实回答与裁决依据对照。
   - **Tab 3（性能与时延剖析）**：对齐 LightRAG 耗时拓扑双卡，分别拆解展示 **TTFT 首字延迟（P50/P95/P99）**、**首字后生成与工具耗时**、**Agent 端到端均耗与整场总耗时**、**L2 裁判打分耗时**、**Agent + 裁判 Token 与费用透传**及**死循环与异常分布**，底部附带指标采集口径真实度说明。
3. **全链路端到端复验**：重启更新后的服务端与前端，用真实新打擂运行两条不同配置并触发 `/browser` 逐点验证与关键截图。
**涉及位置：** `apps/platform-web/src/router/routes.ts`、`apps/platform-web/src/modules/evaluation/`、`apps/platform-api/src/platform_api/modules/evaluation/studio_service.py`、`apps/platform-web/src/services/evaluation/studio.ts`。

- [x] 移除独立对比页面与侧边栏入口，保留 `/evaluation/compare` 重定向并在 `打擂任务大厅` 整合双通道对比 PK 与靶场设置，定时巡检后端调度标记后置。
- [x] 扩展后端 `compare_runs` 返回题目、黄金答案、双方正文、分级指标理由、分段耗时及 Token/费用对比字段并补充单测。
- [x] 全面重构 `ComparisonPkDialog.vue`：修复雷达图白屏与模板分支错位，补齐右侧指标对比表、Side-by-Side 逐题对比卡片及 LightRAG 风格性能与成本拓扑卡。
- [x] 全栈校验（Pytest + `vue-tsc` + Vitest + Vite build + `check_docs.py`）并通过 `/browser` 跑通全链路测试与截图。
