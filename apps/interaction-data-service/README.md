# Interaction Data Service

`apps/interaction-data-service` 是当前正式架构里的结果域服务。

它处在仓库总哲学 `AI Harness` 之下，负责承接“运行时产出的结构化结果”和“平台需要读取、管理、展示的结果域数据”，但不接管平台治理主数据，也不反向吞并 runtime 编排职责。

## 文档定位

文档类型：`Current Overview`

阅读这份 README 时，建议按下面这个优先级理解事实源：

1. 代码与接口：`app/api/**`、`app/db/models.py`
2. 当前说明：`README.md`、`docs/README.md`
3. 当前 API 设计：`docs/test-case-service-api-design.md`
4. 局部设计文档：`docs/service-design.md`
5. 历史设计记录：`docs/usecase-workflow-design.md`

## 这个服务当前在整体架构里的位置

当前正式链路里，它主要承接两条调用路径：

```text
platform-web-vue
  -> platform-api-v2
    -> interaction-data-service

runtime-service
  -> interaction-data-service
```

其中：

- `platform-web-vue` 不直接打本服务
- `platform-api-v2` 负责项目权限、治理边界、聚合视图和协议整形
- `runtime-service` 负责执行期生成结果，再通过稳定 HTTP 契约写入本服务

## 当前开发范式

对 `interaction-data-service` 来说，最重要的不是“抽一个万能结果中心”，而是先守住结果域边界。

核心原则：

1. 只做结果域，不吞平台治理，也不吞 runtime 编排
2. 一个 runtime 业务服务一组专属接口前缀，不回退到“大一统 records 入口”
3. 先固定资源模型、接口契约、落库存储，再继续扩展上层页面或 tool
4. 关键链路优先用真实 HTTP 请求和真实数据验证，不靠前端 mock 兜底
5. 平台读取结果时继续经过 `platform-api-v2`，而不是让正式前端直连本服务

## 当前真实职责边界

### 负责

- 承接 `runtime-service` 等上游写入的结果域数据
- 提供结果域资源的 HTTP CRUD / 聚合读取能力
- 维护本服务拥有的数据表与资源语义
- 为平台 testcase 工作区等结果域页面提供下游数据源

### 不负责

- 用户鉴权、登录、token 签发
- 项目、成员、RBAC 管理
- LangGraph graph 执行
- assistant / catalog 主数据
- 平台工作区聚合与项目权限判断

## 当前已落地的真实资源

当前已经落地并作为正式主线使用的是 `test-case-service` 这一条结果域切片。

当前真实前缀：

- `/api/test-case-service`

当前真实资源：

- `documents`
- `test-cases`
- `overview`
- `batches`

### `documents`

用于保存测试用例业务里的附件解析结果与原始资产索引。

当前真实接口：

- `POST /api/test-case-service/documents/assets`
- `POST /api/test-case-service/documents`
- `GET /api/test-case-service/documents`
- `GET /api/test-case-service/documents/{document_id}`
- `GET /api/test-case-service/documents/{document_id}/relations`
- `GET /api/test-case-service/documents/{document_id}/preview`
- `GET /api/test-case-service/documents/{document_id}/download`

### `test-cases`

用于保存正式测试用例记录。

当前真实接口：

- `POST /api/test-case-service/test-cases`
- `GET /api/test-case-service/test-cases`
- `GET /api/test-case-service/test-cases/{test_case_id}`
- `PATCH /api/test-case-service/test-cases/{test_case_id}`
- `DELETE /api/test-case-service/test-cases/{test_case_id}`

### 聚合读取

用于 testcase 工作区总览和批次视图。

当前真实接口：

- `GET /api/test-case-service/overview`
- `GET /api/test-case-service/batches`
- `GET /api/test-case-service/batches/{batch_id}`

## 当前真实数据表

定义文件：`app/db/models.py`

- `test_case_documents`
  - 保存附件解析结果、来源追踪和原始资产路径
- `test_cases`
  - 保存正式测试用例记录

这说明当前实现已经不是早期泛化设计里的“公共登记表 + record_type 分流”主形态，而是先以 testcase 业务切片落地专属资源。

## 当前与 runtime-service 的关系

当前 testcase 持久化链路是：

```text
runtime-service/test_case_service
  -> 文档即时持久化 / persist_test_case_results
  -> interaction-data-service HTTP API
  -> test_case_documents / test_cases
```

这里的核心约束是：

- 多模态解析结果和正式测试用例都通过稳定 HTTP 契约进入结果域
- `interaction-data-service` 不负责 graph 编排与 tool 选择
- `runtime-service` 不直接接管结果域表结构与查询页面

## 当前与平台层的关系

当前正式平台读取链路是：

```text
platform-web-vue
  -> platform-api-v2
    -> interaction-data-service
```

也就是说：

- 正式平台前端读取 testcase 页面时，应该打 `platform-api-v2`
- `platform-api-v2` 负责项目权限、导出、预览、聚合整形
- `interaction-data-service` 保持结果域所有权，不变成新的控制面后端

## 非当前事实源文档

下面这些文档不用于描述当前实现事实：

- `docs/service-design.md`：局部设计说明，保留为 `Local Design`
- `docs/usecase-workflow-design.md`：历史业务方案记录，保留为 `Historical-in-place`

## 推荐阅读顺序

1. `README.md`
2. `docs/README.md`
3. `docs/test-case-service-api-design.md`

如需补充理解设计背景，再按需查看：

- `docs/service-design.md`
- `docs/usecase-workflow-design.md`

## 当前目录建议这样理解

```text
apps/interaction-data-service/
  README.md
  docs/
  app/
    api/
    db/
    schemas/
    services/
  tests/
```

- `app/api/`：当前真实接口入口
- `app/db/`：当前真实表与数据访问
- `docs/README.md`：当前文档导航与运维入口
- `docs/service-design.md`：局部设计解释，不是当前 API 真相源
- `docs/usecase-workflow-design.md`：历史方案记录
