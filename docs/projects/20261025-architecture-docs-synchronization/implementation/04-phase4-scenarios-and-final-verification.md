# Phase 4 实施记录：全新端到端场景时序闭环与总览看板刷新

## 概述
- **日期：** 2026-10-26
- **执行人：** @laowang-engineer
- **任务目标：** 补齐 4 大端到端高频新场景时序，刷新 `docs/architecture/README.md` 全景地图与总看板，完成六维工业级规范最终核查。

## 变更文件清单
1. `docs/architecture/06-scenarios/04-plan-mode-flow.md` (新增)
   - 先规划后执行模式端到端全链路时序：入参消杀、只读工具裁剪、原生规划中断（`plan_approval`）、前端 `PlanReview.vue` 双重视图及三种分支（批准/修改建议/放弃）。
2. `docs/architecture/06-scenarios/05-trace-to-logs-flow.md` (新增)
   - Trace-to-Logs 毫秒级分布式排障日志穿透时序：前端错误触发、API 代理向 Loki 发起 LogQL、自回声阻断、甘特瀑布流渲染与 Langfuse 三级自适应跳转。
3. `docs/architecture/06-scenarios/06-knowledge-studio-flow.md` (新增)
   - 知识资产上传、异步入库与只读检索时序：多模态入库切片、Scoped HMAC 动态令牌、Canvas 力导向图谱工坊 2.0 与只读 MCP 检索证据溯源。
4. `docs/architecture/06-scenarios/07-model-resilience-fallback-flow.md` (新增)
   - 大模型瞬态故障毫秒级主备容灾降级时序：429 限流/5xx 宕机捕获、受管备用模型自动切换、不可变快照重组与前端微胶囊 Tag 回显。
5. `docs/architecture/README.md`
   - 刷新系统知识全景索引树，涵盖新增的 1 篇跨服务文档、1 篇 API 读模型、3 篇核心概念专篇、4 篇端到端时序。
   - 概念透析总字典追加 08（轻量可观测）、13（异步记忆MMR）、14（弹性MCP容错）三篇直达链接与核心痛点说明。

## 最终验证
- 自动化相对链接测试通过：全量目标新增与重构文件相对链接 100% 有效，0 坏链。
- Mermaid 语法校验全部绿灯。
- 四态判定：`done`。
