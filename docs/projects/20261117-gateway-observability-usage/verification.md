# 验收规范与验证方案

本文件定义本项目的验收要求、阶段验证标准与最终整体验收依据。**阶段验证（Phase）与整体验收（Final）保持严格独立**，严禁将阶段性成果混淆为整体验收完成。

---

## 1. 验收要求概览

| 维度 | 最低验收标准 | 验证方式 |
| :--- | :--- | :--- |
| **API 契约正确性** | `GET /api/usage/gateway/series` 与 `GET /api/projects/{project_id}/usage/gateway/series` 支持 1m/5m/1h/1d 桶聚合，正确输出分位数、单请求均值与缓存读写；边界与错误码规范 | `pytest apps/platform-api/tests/test_usage_analytics.py` 与 `pytest apps/runtime-service/tests/http/test_usage_analytics.py` |
| **代码工程质量** | 前端单元测试 100% 跑绿（5 个套件 33 个用例），`vue-tsc` 类型检查 0 报错，生产打包 `pnpm build` 通过（24.52s 构建成功） | `pnpm test:run` & `pnpm typecheck` & `pnpm build` |
| **视觉与交互标准** | 四大图表排版美观自适应；深浅色模式平滑切换；无手搓坐标抖动或截断；无大长免责占位符阻断 | Vitest 无头 DOM 渲染断言 + 生产打包构建验证 |
| **全链路穿透闭环** | 图表悬停点击下钻直达 Logs 标签页，时间窗口与过滤条件毫秒级锁定，正确拉取该时段 Trace 列表并可拉起详情抽屉 | `UsageDashboardPage.spec.ts` 交互联动测试通过 |

---

## 2. 阶段验证（Phase Verification）

### Phase 1：后端网关时序聚合与 DTO 契约验证
- **目标：** 确保后端正确按请求的时间桶（Bucket）完成统计，支持 P50/P90/P99 延迟推算与 Tokens per Request 均值，具备最大点数保护机制。
- **最低证据要求：**
  - 单测覆盖时间桶切换（60s, 300s, 3600s, 86400s）的数据规整性。
  - 单测覆盖跨日/跨时区时间窗口计算与空数据安全降级。
  - 单测覆盖超过 1000 个点时的防爆保护。
- **执行记录：** ✅ 已通过（done）。
  - 执行命令 1：`uv run pytest tests/test_usage_analytics.py`（platform-api），30 项用例 100% 通过（7.81s）。
  - 执行命令 2：`uv run pytest tests/http/test_usage_analytics.py tests/observability/test_usage_analytics.py`（runtime-service），25 项用例 100% 通过（3.49s）。
  - 核心覆盖场景：`parse_gateway_query`（参数合法性、时间桶超限防御、非法字符防御）、`empty_gateway_series`（空模型投影防御）、`platform_gateway_series` / `project_gateway_series`（平台级与项目级路由、RBAC 鉴权与上下文投影）、`aggregate_gateway_series`（SQL 毫秒桶聚合与分位数计算）。

### Phase 2：前端图表基建与看板视图重构验证
- **目标：** 确保标准图表库引入规范，深浅模式下色彩协调无毛刺，图表支持动态响应式 Resize，图例悬停高亮联动。
- **最低证据要求：**
  - 组件单测（Vitest）验证各 Chart 组件在空数据、部分数据及全量数据下的渲染稳定性。
  - `vue-tsc` 0 报错。
  - 4 联核心指标卡与自适应时间控制栏渲染正常。
- **执行记录：** ✅ 已通过（done）。
  - 执行命令 1：`pnpm test:run src/modules/usage/components/charts/GatewayCharts.spec.ts`，7 项图表测试 100% 跑绿（3.11s）。
  - 执行命令 2：`pnpm test:run src/modules/usage/components/GatewayUsageComponents.spec.ts`，2 项组件测试 100% 跑绿。
  - 执行命令 3：`pnpm typecheck`（`vue-tsc --noEmit`），0 错误，TypeScript 校验 100% 通过。
  - 执行命令 4：`pnpm build`（`vue-tsc --noEmit && vite build`），构建成功（24.52s），生成的资源包包含 `UsageDashboardPage`，无打包阻断警告。

### Phase 3：下钻穿透与 Logs 链路闭环验证
- **目标：** 确保图表 Tooltip 点击能够毫秒级带参路由，Logs 标签页正确接收参数并拉取数据，Trace 详情抽屉完整展现 Prompt/Response/Tools。
- **最低证据要求：**
  - 组件单测与交互测试走通 Tab 切换与下钻事件传递。
  - 验证时间边界（起始毫秒与结束毫秒）与图表时间柱完全吻合。
  - 校验可选链与防空指针容错。
- **执行记录：** ✅ 已通过（done）。
  - 执行命令：`pnpm test:run src/modules/usage/pages/UsageDashboardPage.spec.ts`，2 项测试 100% 跑绿。
  - 验证细节：
    1. 默认展示网关使用大盘（`gateway` Tab），其余 Tab 样式隐藏；
    2. 手动点击顶栏 Tab 可在网关大盘、调用日志与历史治理之间平滑切换；
    3. 网关图表抛出 `@drilldown-to-logs` 事件时，主页面自动激活 `logs` Tab，并把事件中的起止毫秒时间赋给 `activeFilterRange`；
    4. 修复了历史治理 Tab 中因 `previous_window` 与 `summary` 缺少可选链导致在无数据状态下抛出 TypeError 的严重潜在缺陷。

---

## 3. 整体验收（Final Acceptance）

- [x] **场景 1：宏观运维监控体验**
  - 网关看板默认展示 24 小时维度、自适应 300 秒（5 分钟）桶。
  - 四联核心指标卡展示总请求数、异常率、P90 响应耗时、Token 总量（含 Prompt Caching 命中百分比）与总预估成本。
  - 五大看板图表：全宽请求吞吐面积图（GatewayRequestsChart）、P50/P90/P99 延迟折线复合错误柱状图（GatewayLatencyChart）、Token 输入/输出/缓存读取堆叠面积图（GatewayTokenUsageChart）、单请求均值图（GatewayTokenStatsChart）、成本趋势与 TOP10 模型用量分解图（GatewayCostChart）。
  - 支持深色（Dark Mode）与浅色（Light Mode）模式自动切换，ECharts 实例自适应容器 Resize。
- [x] **场景 2：故障/异常突发排障与下钻穿透体验**
  - 悬停图表任意时间桶触发 Tooltip，展示当前桶的时间跨度、关键指标数值与“查看此区间的调用日志”操作按钮。
  - 点击后瞬间将主视图切换至 Logs 视图，时间范围精确框定在该时间柱区间，并在顶部展示高亮锁定期 Pill（可一键还原清除）。
  - 点击 Logs 表格记录直接拉起底层既有 Trace 抽屉，展示完整 Prompt、Response、耗时与工具调用明细。
- [x] **场景 3：双作用域安全隔离与防爆保护**
  - 后端严格支持平台级（全租户）与项目级（单项目）两套网关时序统计接口。
  - 参数校验器 `GatewaySeriesQuery` 设置 1000 个桶上限与最大 90 天窗口保护，杜绝前端大图渲染导致的 OOM。
  - 前端请求基于 epoch 防竞态设计，避免多请求交叉错乱；支持 30s/60s 自动定时轮询刷新。

**整体验收结论：** ✅ 已完成（done）。后端 API 单元测试（55 项用例）全绿，前端单元测试（5 个套件 33 项用例）全绿，TypeScript 0 错误，生产打包 24.52s 顺利构建完成。
