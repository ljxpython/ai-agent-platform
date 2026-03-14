# interaction-data-service 设计稿

本文定义 `apps/interaction-data-service` 的第一版正式设计。

它的定位不是新的平台主后端，也不是通用数据库代理，而是：

> 为 agent 与平台之间的结构化业务结果提供统一接入契约、类型路由、落库能力和查询能力。

## 1. 为什么要单独拆一个服务

当前仓库里：

- `apps/runtime-service` 负责 graph / agent 执行
- `apps/platform-api` 负责鉴权、项目、成员、RBAC、catalog、audit、平台聚合 API
- `apps/platform-web` 负责工作台展示和交互

后续新增更多业务 agent 时，会出现一个稳定需求：

- agent 产出结构化业务结果
- 这些结果需要落库
- 平台需要查询并展示这些结果

但这类数据不适合直接并入：

- `platform-api` 的核心平台主数据模型
- `runtime-service` 的 agent 执行模型

因为它本质上是“agent 与平台交互的业务结果层”，需要自己的边界。

## 2. 服务职责边界

### 2.1 负责

- 定义 agent 与平台共享的结果写入契约
- 根据 `record_type` 路由到不同业务数据表
- 对公共字段和类型字段做校验
- 提供统一 HTTP API 供 runtime / platform 调用
- 提供统一查询能力，支持平台列表、详情、检索
- 维护业务结果类型版本（`schema_version`）

### 2.2 不负责

- 用户鉴权、登录、token 签发
- 项目管理、成员管理、RBAC
- LangGraph graph 执行
- assistant / catalog 主数据管理
- 聊天 transcript 存储
- 把所有 agent 强行统一成一张业务表

## 3. 数据库策略

结论：

- 继续共用现有 PostgreSQL
- 新服务只维护自己的表
- 不复制 `platform-api` 的鉴权、项目、成员等表语义

这意味着：

- 共库
- 分表
- 分服务
- 分职责

## 4. 核心设计原则

### 4.1 统一入口，不统一业务表

不同 agent 的结构化结果最终会落到不同表。

例如：

- 需求分析 agent
- 用例分析 agent
- SQL 报告 agent

它们的结果结构天然不同，不应该为了“看起来统一”而硬压成同一张大 JSON 业务表。

### 4.2 统一契约，不统一 agent tool

统一的是：

- 写入契约
- 查询契约
- 类型注册规则
- 公共元数据字段

不统一的是：

- 每个 agent 暴露给模型的 LangGraph tool
- 每个业务结果表的字段设计

### 4.3 统一元数据，不统一 payload 细节

所有结果记录都要带一层公共元数据，便于：

- 平台统一查询
- 按项目过滤
- 按 agent 过滤
- 按类型展示
- 后续审计与回放

但 `payload` 内部由各个业务类型自己定义。

### 4.4 服务间通信优先 HTTP

第一期不把 `interaction-data-service` 设计成公共 MCP。

原因：

- 当前主要调用方是 `runtime-service` 内的 Python tool
- HTTP 更直白，调试和治理成本更低
- 若做成公共 MCP，函数变多后模型选择成本会上升
- 这里需要的是稳定服务契约，不是额外一层 agent-facing 协议抽象

因此推荐：

- `interaction-data-service` 暴露 HTTP API
- 每个业务 agent 在本地定义 LangGraph tool
- tool 内部调用不同 HTTP 接口

## 5. 调用链路

### 5.1 agent 写入链路

```text
runtime-service
  -> agent local tools
    -> interaction-data-service HTTP API
      -> PostgreSQL tables owned by interaction-data-service
```

### 5.2 平台读取链路

```text
platform-web
  -> platform-api
    -> interaction-data-service HTTP API
      -> PostgreSQL tables owned by interaction-data-service
```

说明：

- `platform-web` 不直接调用 `interaction-data-service`
- 平台侧仍通过 `platform-api` 做鉴权、项目上下文、聚合与转发
- `interaction-data-service` 只聚焦结果域，不接管平台主数据域

## 6. 数据模型建议

第一期推荐“两层表结构”：

1. 公共登记表
2. 各业务类型自己的结果表

### 6.1 公共登记表：`interaction_records`

建议字段：

- `id`
- `project_id`
- `agent_key`
- `record_type`
- `schema_version`
- `title`
- `summary`
- `status`
- `run_id`（可空）
- `thread_id`（可空）
- `source_message_id`（可空）
- `created_by_kind`（如 `agent` / `platform` / `system`）
- `created_at`
- `updated_at`

这张表只承担：

- 统一索引
- 统一分页
- 统一检索
- 统一跨类型列表展示

### 6.2 业务结果表示例

- `requirement_analysis_results`
- `usecase_analysis_results`
- `sql_report_results`

每张业务表：

- 用自己的结构化字段表达业务含义
- 通过 `record_id` 与 `interaction_records.id` 关联
- 按业务节奏独立演进

## 7. 契约设计

这里真正需要统一的是“各层如何对接”。

推荐把契约拆成三层：

### 7.1 写入契约

每个 agent/tool 调服务写入时，至少传：

```json
{
  "record_type": "requirement_analysis",
  "schema_version": "1.0",
  "project_id": "project-uuid",
  "agent_key": "requirement_analysis_agent",
  "title": "需求分析结果",
  "summary": "提取了 8 个核心需求点",
  "status": "completed",
  "run_id": "optional-run-id",
  "thread_id": "optional-thread-id",
  "source_message_id": "optional-message-id",
  "payload": {
    "...": "业务结构化结果"
  }
}
```

### 7.2 类型契约

每个 `record_type` 都必须明确：

- 名称
- 当前 `schema_version`
- payload 字段定义
- 哪个 handler 负责处理
- 落哪张业务表

### 7.3 读取契约

平台不仅需要“能写”，还要“知道怎么读”。

因此每个 `record_type` 还要定义：

- 列表页需要哪些摘要字段
- 详情页需要哪些结构字段
- 前端如何渲染或降级展示

## 8. HTTP API 设计

这里不走“一个统一保存接口解决全部问题”的思路。

推荐按资源语义暴露多接口，至少包含增删改查基础能力。

对外路由保持资源化；对内分发保持 `record_type` 驱动。也就是说：

- HTTP 层不需要为每个 `record_type` 暴露一套完全不同的 URL 族
- 但服务内部必须根据 `record_type` 做校验、路由和落表
- `record_type` 是内部处理主轴，也是跨层契约的一部分

### 8.1 建议接口

- `POST /records`
  - 新建记录与业务结果
- `GET /records`
  - 按项目、类型、agent、状态分页查询
- `GET /records/{record_id}`
  - 获取单条记录详情
- `PATCH /records/{record_id}`
  - 更新状态、标题、摘要等允许变更字段
- `DELETE /records/{record_id}`
  - 删除记录（是否物理删除后续再定）

如后续有需要，再增加：

- `GET /record-types`
- `GET /projects/{project_id}/records/summary`

## 9. agent 侧 tool 设计

### 9.1 不进入公共 tools registry

这类 tool 不进入 `runtime-service` 的公共工具池。

理由：

- 它们是强业务语义工具
- 不同 agent 需要的字段不同
- 直接暴露成公共工具会让模型选择成本升高

### 9.2 每个 agent 自己定义本地 tool

例如：

- `save_requirement_analysis_result`
- `update_requirement_analysis_result`
- `get_requirement_analysis_result`
- `delete_requirement_analysis_result`

或者：

- `create_usecase_record`
- `list_usecase_records`

这些 tool 不要求名称统一，但要求内部遵循同一套服务契约，并分别调用不同的 HTTP 接口，而不是都打到一个统一保存入口。

### 9.3 共享的是 client，不是 tool

推荐在 `runtime-service` 内保留一个很薄的内部 client/helper，用于：

- HTTP 请求封装
- header 组装
- 错误处理
- 超时配置

但不要把业务 tool 本身做成公共注册工具。

### 9.4 推荐的接口与 tool 对应关系

推荐把服务暴露出的 HTTP CRUD 能力，按业务语义封装成 agent 本地 tool。

例如某个需求分析 agent：

- `create_requirement_analysis_result`
  - 调 `POST /records`
- `get_requirement_analysis_result`
  - 调 `GET /records/{record_id}`
- `update_requirement_analysis_result`
  - 调 `PATCH /records/{record_id}`
- `delete_requirement_analysis_result`
  - 调 `DELETE /records/{record_id}`

如果该 agent 还需要列表查询，再额外提供：

- `list_requirement_analysis_results`
  - 调 `GET /records`

这样模型看到的是当前业务 agent 自己的一小组明确工具，而不是一个公共 MCP 或一个模糊的统一落库函数。

## 10. `record_type` 路由机制

`interaction-data-service` 的核心简单性来自“统一入口 + 类型分流”。

推荐内部维护一个类型注册映射：

```text
record_type
  -> schema validator
  -> handler
  -> table writer
  -> query mapper
```

例如：

- `requirement_analysis`
  - 校验 `RequirementAnalysisPayload`
  - 写入 `requirement_analysis_results`
- `usecase_analysis`
  - 校验 `UsecaseAnalysisPayload`
  - 写入 `usecase_analysis_results`

这样外部接入统一，内部落表可分化。

## 11. interaction-data-service 如何保持简单

第一期只做下面这些：

- 一张公共登记表
- 1~2 张真实业务结果表
- 5 个 HTTP CRUD 接口
- 一个清晰的类型注册机制
- 一套文档化契约

第一期不做：

- 公共 MCP server
- 通用规则引擎
- 动态建表
- 所有类型完全配置化
- 大而全的统一 JSON 结果仓库

## 12. 与 platform-api 的协作方式

`platform-api` 继续负责：

- 鉴权
- 读取当前用户
- 校验项目权限
- 决定哪些项目数据可见

然后由 `platform-api` 去调用 `interaction-data-service`。

这意味着：

- `interaction-data-service` 不复制 `platform-api` 的主数据模型
- 但所有写入和查询都必须带 `project_id`
- 后续需要更强一致性时，可通过内部 service token 或内网调用约束服务边界

## 13. 与 platform-web 的协作方式

`platform-web` 不直接理解底层业务表，只消费平台聚合后的视图。

推荐展示分两层：

- 列表摘要视图
- 详情结构视图

例如需求分析 agent 页面：

- 左侧列表：最近分析结果
- 右侧详情：结构化分析内容

如果某类结果未来要和 chat 结合展示，也应通过 `record_id / run_id / thread_id` 关联，而不是把业务结果塞进聊天 message 文本中。

## 14. 推荐目录结构

第一期建议目录：

```text
apps/interaction-data-service/
  docs/
    README.md
    service-design.md
  app/
    api/
    handlers/
    schemas/
    services/
    db/
  tests/
```

说明：

- `api/`：HTTP 路由
- `handlers/`：按 `record_type` 处理不同业务结果
- `schemas/`：请求/响应和 payload schema
- `services/`：应用服务与路由分发
- `db/`：表模型、session、访问层

补充说明：

- `app/api/__init__.py` 作为包级路由装配入口，和 `platform-api` 保持一致
- `app/bootstrap/lifespan.py` 当前刻意保持最小，只作为后续挂载 DB engine、HTTP client、type registry cache 等共享资源的预留缝

## 15. 第一批建议落地内容

建议第一批只选一个真实业务类型先落地，例如：

- `requirement_analysis`

配套落地：

1. `interaction_records`
2. `requirement_analysis_results`
3. `POST /records`
4. `GET /records`
5. `GET /records/{record_id}`
6. `PATCH /records/{record_id}`
7. `DELETE /records/{record_id}`
8. 一个需求分析 agent 的本地 LangGraph tools
9. `platform-api` 的转发/聚合接口
10. `platform-web` 的最小列表 + 详情展示

## 16. 最终结论

一句话总结这套方案：

> `interaction-data-service` 不是统一业务表服务，而是统一接入契约、类型路由和查询能力的结果服务；通信优先 HTTP，agent 侧按业务自定义本地 LangGraph tools，平台侧继续通过 `platform-api` 聚合访问。

这套方案的优点是：

- 保持服务边界清晰
- 不污染 `platform-api` 主数据模型
- 不把 `runtime-service` 变成平台结果数据库入口
- 允许每个 agent 用最适合自己的业务表
- 同时又为平台保留统一对接规范
