# Showcase Demo 验收专项：图谱发现与多租户隔离架构缺陷深度剖析

- **日期**：2026-09-09
- **阶段**：验收联调期发现的架构缺陷
- **关联 ADR**：[`docs/decisions/20260909-runtime-graph-discovery-and-isolation-architecture.md`](../../../decisions/20260909-runtime-graph-discovery-and-isolation-architecture.md)

---

## 1. 问题复盘

在完成 `showcase_demo` 核心能力开发后，进入平台前端（`platform-web`）在实际项目环境下的全链路验收。
在 `/workspace/assistants` 页面点击【同步后端 Agent】时，暴露了深层次的架构设计矛盾：

1. **上游搜索隔离陷阱**：
   - 预期图谱数为 3 个（`reference_agent`、`workflow_demo`、`showcase_demo`）。
   - 实际提示仅有 2 个后端 Agent 就绪，`showcase_demo` 丢失。
   - 根因：`RuntimeCatalogService.refresh_graphs` 依赖上游 GraphHarbor 的 `POST /assistants/search`。GraphHarbor 底层在 `AssistantRow` 表及 `_scope()` 辅助函数中对查询强行实施了 `project_id` 过滤。未在当前项目实例化过的 `showcase_demo` 被过滤，导致 `mark_missing_graphs_deleted` 将其标记为软删除。

2. **跨服务本地扫描的分布式隐患**：
   - 临时通过 `_load_static_graph_configs()` 向上查找本地 Monorepo 的 `apps/runtime-service/langgraph.json`。
   - 经审查，该方案具有严重的单机本地环境依赖：在生产分布式部署（微服务/容器化 Pod 隔离）下，`platform-api` 无法访问 `runtime-service` 的文件系统，必然导致图谱加载失败、生产系统不可用。

---

## 2. 核心架构裁决

针对上述两项缺陷，已建立独立技术决策文档：
详见架构决策文档：[`docs/decisions/20260909-runtime-graph-discovery-and-isolation-architecture.md`](../../../decisions/20260909-runtime-graph-discovery-and-isolation-architecture.md)

**核心要点：**
1. **职责复位**：
   - Graph（图谱）是运行时只读代码能力，属于全局资产，严禁受业务租户或项目上下文隔离。
   - Assistant（助手）是项目内的配置实例，由业务控制面管理。
2. **能力发现标准化**：
   - `runtime-service` 通过 `webapp.py` 暴露无租户概念的全局能力端点：`GET /internal/capabilities/graphs`。
   - `platform-api` 彻底废除跨服务磁盘文件扫描，统一通过微服务网络契约发现能力。

---

## 3. 当前现状与后续安排

- **当前代码状态**：
  - 维持当前已验证通过的稳定状态（单机环境下 3 个 Agent 可正常同步与对话，E2E 测试通过）。
  - 未经方案评审和正式规划前，**暂不执行代码重构**。
- **后续任务拆解**：
  - 待团队对该 ADR 进行评审批准后，正式立项推进 `Phase 1~3` 重构落地。
