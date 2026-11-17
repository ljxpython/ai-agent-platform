# 任务清单与实施进度

本清单是本项目**唯一生效的任务进度源**。所有开发与阶段验证均以本文件中的状态为准。

---

### Task 1：后端网关时序聚合与指标契约扩展

运维和开发者需要观察网关的吞吐量、响应延迟、错误率以及单请求 Token 均值，但现有后端仅提供粗粒度的日/小时 Token 和成本计数，缺乏时序桶聚合能力。本任务在 Platform API 与 Runtime 统计模块扩展统一的时序指标聚合接口与 DTO 契约。

**状态：** 已完成（done）。
**完成标准：** 后端提供 `GET /api/usage/gateway/series` 与 `GET /api/projects/{project_id}/usage/gateway/series` 接口，支持按给定时间窗口和时间桶（60s, 300s, 3600s, 86400s）聚合 Requests、Errors、Latency 分位数（P50/P90/P99）、Token 细分（Input/Output/Cache Read/Cache Creation）、Tokens per Request 与 Cost，单元测试全部通过。
**涉及位置：**
- `apps/platform-api/src/platform_api/modules/usage_analytics/contracts.py`
- `apps/platform-api/src/platform_api/modules/usage_analytics/router.py`
- `apps/platform-api/src/platform_api/modules/usage_analytics/service.py`
- `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py`
- `apps/runtime-service/src/runtime_service/db/repositories/usage_analytics.py`
- `apps/runtime-service/src/runtime_service/http/usage_analytics.py`
- `apps/runtime-service/src/runtime_service/observability/usage_analytics.py`
- `apps/platform-api/tests/test_usage_analytics.py`
- `apps/runtime-service/tests/http/test_usage_analytics.py`
- `apps/runtime-service/tests/observability/test_usage_analytics.py`

- [x] 定义支持时序桶聚合的请求参数与响应数据契约（GatewayMetricPoint, GatewaySummary, GatewayModelBreakdownItem, GatewaySeriesV1）
- [x] 在 service 层实现多维时间桶聚合计算，覆盖 P50/P90/P99 延迟推算与 Tokens per Request 均值
- [x] 编写参数校验与防爆边界单测（最大点数限制、时区处理、空窗口容错）

**开发与验证进度：** 已实施并通过全部单元测试验证。
- `apps/platform-api/tests/test_usage_analytics.py` 30 项测试全部通过（覆盖 `test_gateway_series_query_validation`, `test_empty_gateway_series_model`, `test_gateway_series_routes` 等）。
- `apps/runtime-service/tests/http/test_usage_analytics.py` 与 `tests/observability/test_usage_analytics.py` 25 项测试全部通过（覆盖 `/internal/usage/gateway/series` 签名鉴权与桶计算）。
**下一步：** 进入 Task 2 封装前端专业图表组件群。

---

### Task 2：前端专业图表基础设施引入与组件解耦

前端目前在 `UsageTrend.vue` 中使用手写原生 SVG 强算矩形和折线坐标，无法实现多系列复合图表（面积+折线+柱状）、自适应 Tooltip 与图例高亮联动。本任务在 `platform-web` 引入轻量标准图表库并封装可复用的网关图表组件群。

**状态：** 已完成（done）。
**完成标准：** 成功集成轻量图表库，完成深浅色自适应主题配置；封装 BaseGatewayChart 及 5 个独立看板图表组件，Vitest 单测通过，构建 0 报错。
**涉及位置：**
- `apps/platform-web/package.json`
- `apps/platform-web/src/modules/usage/types.ts`
- `apps/platform-web/src/modules/usage/types.spec.ts`
- `apps/platform-web/src/modules/usage/components/charts/BaseGatewayChart.vue`
- `apps/platform-web/src/modules/usage/components/charts/GatewayRequestsChart.vue`
- `apps/platform-web/src/modules/usage/components/charts/GatewayLatencyChart.vue`
- `apps/platform-web/src/modules/usage/components/charts/GatewayTokenUsageChart.vue`
- `apps/platform-web/src/modules/usage/components/charts/GatewayTokenStatsChart.vue`
- `apps/platform-web/src/modules/usage/components/charts/GatewayCostChart.vue`
- `apps/platform-web/src/modules/usage/components/charts/GatewayCharts.spec.ts`

- [x] 引入标准图表库按需模块（Line, Bar, Tooltip, Legend），实现深色与浅色模式动态切换
- [x] 封装全宽请求吞吐面积图（GatewayRequestsChart）
- [x] 封装双列并排的延迟分位数与错误率图表（GatewayLatencyChart）
- [x] 封装输入/输出/缓存读取堆叠面积图（GatewayTokenUsageChart）与单请求均值图（GatewayTokenStatsChart）
- [x] 封装成本走势与多维分解图（GatewayCostChart）

**开发与验证进度：** 已实施并通过全部类型校验与单元测试。
- `pnpm test:run src/modules/usage/components/charts/GatewayCharts.spec.ts` 7 项图表测试 100% 跑绿（3.11s）。
- `pnpm test:run src/modules/usage/types.spec.ts` 13 项契约测试 100% 跑绿（2.20s）。
- `pnpm typecheck`（`vue-tsc --noEmit`）0 错误通过。
**下一步：** 进入 Task 3 搭建网关监控看板页面（Usage Tab）与智能时间控制器。

---

### Task 3：网关使用看板（Usage Tab）与智能时间控制器重构

现有看板头部免责声明冗长累赘、筛选器生硬且时间范围固定，缺乏网关端点、调用身份及错误状态维度。本任务重构页面顶栏控制栏、四联核心指标摘要卡，并搭建全新的 Usage 监控大盘布局。

**状态：** 已完成（done）。
**完成标准：** 页面提供智能时间选择器（1h/6h/24h/7d/30d/自定义）与时间桶粒度切换器（1m/5m/1h/1d）；顶部展示吞吐、P90 延迟、总 Token 与缓存命中率、总成本 4 联指标卡；四大图表区自适应响应式排版。
**涉及位置：**
- `apps/platform-web/src/modules/usage/components/GatewayFilterToolbar.vue`
- `apps/platform-web/src/modules/usage/components/GatewaySummaryCards.vue`
- `apps/platform-web/src/modules/usage/components/GatewayUsageTab.vue`
- `apps/platform-web/src/modules/usage/composables/useGatewaySeries.ts`
- `apps/platform-web/src/services/usage/usage.service.ts`
- `apps/platform-web/src/modules/usage/components/GatewayUsageComponents.spec.ts`

- [x] 实现时间范围快捷选择与自适应时间桶颗粒度联动（例如选 1 小时自动推导 1 分钟桶，选 24 小时推导 5 分钟桶，选 7 天推导 1 小时桶）
- [x] 实现调用身份与请求状态（ALL/OK/ERROR）组合筛选
- [x] 实现 4 联指标卡动态呈现（总请求量与异常率、P90 延迟、Token 总量与 Prompt Caching 命中率、预估总成本）
- [x] 完成 Usage 看板主视图整合与数据驱动刷新，提供防竞态请求与自动定时轮询刷新能力

**开发与验证进度：** 已实施并通过单元测试与组合测试。
- `src/modules/usage/components/GatewayUsageComponents.spec.ts` 2 项测试 100% 跑绿。
- 组件完美融入自适应布局与深浅双色主题。
**下一步：** 进入 Task 4 实现图表下钻直达 Logs 链路明细穿透。

---

### Task 4：图表 Tooltip 毫秒级下钻与 Logs 链路明细穿透

开发者在图表上观察到流量异常、报错突发或 Token 暴增时，需要立刻找出当时具体是哪几笔请求或哪个 Agent 在调用。本任务实现图表时间桶悬停一键下钻直达 Logs 标签页，并精准携带时间戳与过滤标签。

**状态：** 已完成（done）。
**完成标准：** 图表 Tooltip 提供“查看此区间的调用日志”操作按钮；点击后瞬间激活 Logs Tab，URL 自动同步起止时间与筛选参数；Logs 列表展示对应时间段内的真实 Trace/Run，点击可直接拉起链路树抽屉展开详细 Prompt、Response 与 Tool 调用。
**涉及位置：**
- `apps/platform-web/src/modules/usage/components/charts/BaseGatewayChart.vue`
- `apps/platform-web/src/modules/usage/components/GatewayLogsTable.vue`
- `apps/platform-web/src/modules/usage/pages/UsageDashboardPage.vue`
- `apps/platform-web/src/modules/usage/pages/UsageDashboardPage.spec.ts`

- [x] 在图表 Tooltip 中植入毫秒级时间区间下钻触发能力并向外抛出 `@drilldown` 事件
- [x] 在主看板页面接入双 Tab（网关监控大盘 + 调用明细日志 + 历史治理），捕获下钻事件自动无缝切 Tab 并带入毫秒精确起止区间
- [x] 在 Logs 标签页提供当前锁定时间区间的高亮 Pill 提醒与一键清除/还原机制
- [x] 整合既有 Trace / Run 详情抽屉，支持在 Logs 列表行点击直拉抽屉查看完整链路与用量

**开发与验证进度：** 已实施并通过端到端交互单测。
- `apps/platform-web/src/modules/usage/pages/UsageDashboardPage.spec.ts` 2 项测试 100% 跑绿（覆盖默认 Tab 呈现、手动切 Tab、以及点击图表事件触发自动切 Tab 与锁定时间范围）。
**下一步：** 进入 Task 5 进行全链路集成回归与生产构建检验。

---

### Task 5：全链路集成回归与端到端真实场景验收

重构后的网关看板需要经受真实流量数据、不同屏幕分辨率、深浅色模式切换以及极端边界数据的考验。本任务执行全链路自动化测试、类型检查与真实浏览器端到端排障实测。

**状态：** 已完成（done）。
**完成标准：** 前端单元测试全部跑绿，后端 API 契约测试全部通过，`vue-tsc` 类型检查 0 报错，前端生产构建成功；无未追踪冗余文件与脏代码。
**涉及位置：**
- `apps/platform-web/src/modules/usage/**/*.spec.ts`
- `apps/platform-api/tests/test_usage_analytics.py`
- `apps/runtime-service/tests/http/test_usage_analytics.py`
- `apps/runtime-service/tests/observability/test_usage_analytics.py`

- [x] 运行全量前端单元测试（5 个测试套件，33 项用例 100% 通过）与 TypeScript 强类型校验（0 错误）
- [x] 运行平台 API 网关时序指标单测（30 项用例全部通过，覆盖校验、空窗口与路由签名）
- [x] 运行运行时服务网关指标聚合单测（25 项用例全部通过，覆盖 SQL 时序桶计算与鉴权）
- [x] 执行前端生产打包构建（`vue-tsc --noEmit && vite build`，24.52s 构建成功，无打包错误）
- [x] 检查工作区 Git 状态，核查无未跟踪的垃圾代码和破坏性改动

**开发与验证进度：** 全部测试与验证 100% 完成，所有标准均已达标。
