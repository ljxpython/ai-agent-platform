# ADR: Runtime 图谱发现机制与多租户/项目隔离边界解耦设计

- **状态**：PROPOSED（待评审 / 严禁盲目编码）
- **日期**：2026-09-09
- **影响范围**：`apps/runtime-service`, `apps/platform-api`, `apps/platform-web`
- **关联项目**：`docs/projects/20260908-showcase-demo/`

---

## 1. 背景与问题陈述 (Context & Problem Statement)

在 `showcase_demo` 全能力智能体验收及前端【同步后端 Agent】联调过程中，暴露了平台图谱目录（Runtime Catalog Graphs）发现与同步链路中的两项严重架构缺陷：

### 缺陷一：GraphHarbor 底层 `/assistants/search` 强制租户/项目隔离导致能力死锁
- **现象**：
  新项目进入 Agent 页面点击【同步后端 Agent】时，仅能同步出预先存在 Assistant 实例的 2 个图谱，未在当前项目实例化过的 `showcase_demo` 无法被发现，并在数据库 `runtime_catalog_graphs` 中被误杀标记为 `is_deleted = 1`。
- **源码根因**：
  1. **数据模型越权**：`langgraph_runtime_pg/models.py:47-48`（当时版本源码位置，历史引用） 在底层执行引擎的数据表 `AssistantRow` 中强行耦合了上层控制面的 `tenant_id` 和 `project_id`。
  2. **查询无差别过滤**：`langhost/core_api.py:96-102`（当时版本源码位置，历史引用） 的 `_scope()` 函数对所有查询强制添加 `WHERE tenant_id = principal.tenant_id AND project_id = principal.project_id`。
  3. **能力接口缺失**：GraphHarbor 底层没有暴露查看全局图谱的 `GET /graphs` 端点，而是让上层调用 `/assistants/search`；而 `langhost/core_api.py:217-226`（当时版本源码位置，历史引用） 将 `/assistants/search` 强行套上了 `_scope()`。
- **业务死锁悖论**：
  全新项目无 Assistant 实例 -> 上游 `/assistants/search` 返回空 -> `RuntimeCatalogService.refresh_graphs` 执行 `mark_missing_graphs_deleted` 误删图谱 -> 控制面认为 Runtime 无可用图谱 -> 前端无法新建/选择 Agent。

### 缺陷二：`platform-api` 跨服务直接读取本地 `langgraph.json` 在分布式部署下必崩
- **现象**：
  为了解决上述缺陷一，临时采用的 `_load_static_graph_configs()` 通过 `Path(__file__).resolve().parents` 递归查找上级目录中的 `apps/runtime-service/langgraph.json`。
- **致命缺陷**：
  - 该方案仅在**单机 Monorepo 本地开发环境**下偶然生效。
  - 一旦系统进行**容器化或分布式部署**（例如生产环境：`platform-api` 与 `runtime-service` 分别打包为独立 Docker 镜像并运行在不同的 K8s Pod 或虚拟机上），`platform-api` 容器内部根本不存在 `runtime-service` 的源码及物理文件。
  - 届时 `_load_static_graph_configs()` 必然返回空字典，分布式部署环境将直接瘫痪。

---

## 2. 根因剖析与架构职责倒错 (Root Cause Analysis)

### 2.1 概念混淆：Graph vs Assistant
| 概念 | 本质属性 | 生命周期与归属 | 适用场景 |
| :--- | :--- | :--- | :--- |
| **Graph（图谱）** | **代码级算子与工作流定义** | 全局静态、系统级无状态、属于整个 Runtime 引擎（由 `langgraph.json` 声明） | 定义系统能做什么（如 `showcase_demo`, `reference_agent`） |
| **Assistant（助手）** | **图谱的具体配置实例** | 业务级有状态、属于特定项目/租户（包含特定的 model_config、system_prompt、tools 覆盖等） | 在具体业务项目中运行的智能体实体 |

**架构反模式**：
GraphHarbor 本质是一个底层的 Agent 执行引擎（Runtime Execution Engine），却越俎代庖维护了业务控制面（Control Plane）的租户与项目隔离关系；同时控制面却把“查询全局 Graph 算子”的动作，错误地委托给了一个“查询项目内 Assistant 实例”的端点。

### 2.2 契约不一致性与半截子工程
在 `platform-api` 中：
- 刷新模型能力：调用 `GET /internal/capabilities/models`
- 刷新工具能力：调用 `GET /internal/capabilities/tools`
- **刷新图谱能力**：却使用了 `/assistants/search`

这表明最初的架构设计中规划了统一的 `/internal/capabilities/*` 运行时自省机制，但图谱自省接口（`/internal/capabilities/graphs`）未能落地，导致后续实现采用了错误的接口与文件跨界读取。

---

## 3. 目标重构方案 (Target Architecture & Decision)

```mermaid
flowchart TD
    subgraph Platform Control Plane ["platform-api (控制面)"]
        CatalogSvc["RuntimeCatalogService"]
        DB[(Platform DB\nruntime_catalog_graphs)]
    end

    subgraph Runtime Execution Plane ["runtime-service (执行面 / 8123)"]
        WebApp["FastAPI webapp.py\n(挂载于 LangHost 根路径)"]
        CapGraphs["GET /internal/capabilities/graphs\n(全局自省端点，无租户隔离)"]
        LangGraphConfig[("langgraph.json\n(引擎真理源)")]
        LangHost["LangHost / GraphHarbor Engine"]
    end

    CatalogSvc -->|1. HTTP GET\n/internal/capabilities/graphs| CapGraphs
    CapGraphs -->|读取自省配置| LangGraphConfig
    CatalogSvc -->|2. 落库同步 (权威更新)| DB
    CatalogSvc -.->|3. 彻底废弃| LocalFS["本地磁盘跨容器扫描 (DEL)"]
```

### 3.1 决策一：Runtime Service 暴露标准全局自省端点
1. **服务入口**：
   在 `apps/runtime-service/langgraph.json` 中已配置 `"http": {"app": "./src/runtime_service/webapp.py:app"}`，LangHost 启动时会自动将该 FastAPI 应用通过 `Mount("/", app=custom_app)` 挂载到根路径。
2. **端点定义**：
   在 [`apps/runtime-service/src/runtime_service/webapp.py`](../../apps/runtime-service/src/runtime_service/webapp.py) 中注册：
   ```http
   GET /internal/capabilities/graphs
   ```
   - **鉴权模式**：平台内部服务间鉴权（基于 `PLATFORM_RUNTIME_DELEGATION_SECRET` 或管理 API 密钥），**不接受也不需要 `project_id` 过滤**。
   - **返回数据结构**：
     ```json
     {
       "graphs": [
         {
           "graph_id": "reference_agent",
           "display_name": "reference_agent",
           "description": "R2 Runtime-aware create_agent reference service with explicit model resolution."
         },
         {
           "graph_id": "workflow_demo",
           "display_name": "workflow_demo",
           "description": "Model-backed workflow Agent with optional human confirmation interrupt."
         },
         {
           "graph_id": "showcase_demo",
           "display_name": "showcase_demo",
           "description": "Showcase agent demo for demonstrating all capability features in frontend."
         }
       ]
     }
     ```

### 3.2 决策二：Platform API 彻底剔除本地文件扫描
1. **清理代码**：
   彻底删除 `RuntimeCatalogService._load_static_graph_configs()`（当时版本源码位置，历史引用） 中所有依赖 `Path.parents` 和磁盘扫描的本地逻辑。
2. **更新契约**：
   `RuntimeCatalogService.refresh_graphs` 改为向 upstream 发送标准的微服务 HTTP 请求：
   ```python
   payload = await self._upstream.require_json(
       "GET",
       "/internal/capabilities/graphs",
       forwarded_headers=self._runtime_management_headers(actor=actor),
   )
   ```
3. **一致性保证**：
   无论在单机、Docker Compose、还是 K8s 多 Pod 分布式环境，两层服务均通过标准网络契约交互，无任何本地文件路径强耦合。

### 3.3 决策三：解耦 GraphHarbor 的图谱与助手生命周期
1. `/assistants/search` 仅作为业务租户/项目内部的助手实例查询接口，**彻底从图谱发现流程中剔除**。
2. 当项目在平台新建 Agent 或初次调度某图谱时，上层按需触发底层实例创建；或者依赖 LangHost 内部的 `_resolve_assistant()` 按需自举（Lazy Initialization），不再将“上游必须先有项目 Assistant 记录”作为平台发现图谱的前提条件。

---

## 4. 实施计划 (Action Items)

| 阶段 | 任务内容 | 涉及服务与文件 | 预期结果 |
| :--- | :--- | :--- | :--- |
| **Phase 1** | 在 `runtime-service` 暴露图谱自省端点 | `apps/runtime-service/src/runtime_service/webapp.py` | 启动后访问 `GET /internal/capabilities/graphs` 能正确返回 `langgraph.json` 中的 3 个图谱元数据 |
| **Phase 2** | `platform-api` 接入标准端点并移除本地扫描 | `apps/platform-api/app/modules/runtime_catalog/application/service.py` | 移除 `_load_static_graph_configs`；`refresh_graphs` 通过 HTTP 调用上游接口 |
| **Phase 3** | 分布式环境兼容性单测与集成测试 | `apps/platform-api/tests/test_runtime_catalog_delegation.py`, `apps/runtime-service/tests/` | 验证纯 HTTP mock 和容器隔离下图谱刷新仍然正常通过 |
