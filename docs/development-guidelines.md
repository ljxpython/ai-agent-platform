# 开发规范（接口与数据落库）

## 1. API 命名空间

当一个智能体（或工作流域）需要落库并提供对外查询/管理接口时，必须使用统一命名空间：

```
/api/<domain>/...
```

其中：

- `<domain>` 使用 `kebab-case`
- `<domain>` 表达“业务域/智能体能力”，而不是表名或实现细节
- 每个 domain 下的资源路由按 REST 资源拆分（例如 `workflows`、`use-cases`、`reports`）

### 示例：用例生成智能体（domain = usecase-generation）

- 工作流管理：
  - `/api/usecase-generation/workflows`
  - `/api/usecase-generation/workflows/{workflow_id}/snapshots`
  - `/api/usecase-generation/workflows/{workflow_id}/review`
  - `/api/usecase-generation/workflows/{workflow_id}/approve`
  - `/api/usecase-generation/workflows/{workflow_id}/persist`

- 正式用例 CRUD：
  - `/api/usecase-generation/use-cases`
  - `/api/usecase-generation/use-cases/{use_case_id}`

## 2. 数据模型

- 不同 domain 的数据结构不强制共用。
- 允许每个 domain 单独设计 schema/表结构。
- 所有可查询数据必须可按 `project_id` 过滤，以支持平台侧按项目维度管理。

## 3. 服务职责边界（默认约定）

- `interaction-data-service`：承接落库与 CRUD/查询接口（按 domain 命名空间组织）。
- `runtime-service`：执行智能体/工作流；需要持久化时调用对应 domain 的 `/api/<domain>/...`。
- `platform-api`：对外统一鉴权/项目隔离；需要时转发/聚合 `interaction-data-service`。
- `platform-web`：当前正式平台前端宿主，按 domain 做页面入口与管理能力。
- `runtime-web`：可选调试入口，用于运行时交互验证，不承担正式平台治理页面职责。

本地部署补充说明：默认本地部署成员以 `docs/local-deployment-contract.yaml` 为准；当前默认本地启动集已经包含 `interaction-data-service` 与 `platform-web`。
