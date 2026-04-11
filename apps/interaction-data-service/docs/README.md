# interaction-data-service 当前说明

文档类型：`Operational`

本文用于说明 `interaction-data-service` 当前已经落地的接口、表结构、联调路径和阅读入口。

如果本文与代码冲突，以代码为准；建议优先参考：

1. `app/api/test_case_service/**`
2. `app/db/models.py`
3. 本文
4. `docs/test-case-service-api-design.md`
5. `docs/service-design.md`

## 当前定位

`apps/interaction-data-service` 现在采用“每个 runtime 服务一个专属接口前缀”的范式。

当前已经正式落地的业务前缀：

- `/api/test-case-service`

这意味着：

- HTTP API 不再走通用 `record_type` 大入口
- 旧的 `/api/usecase-generation/*` 业务接口已经退役
- 每个结果域切片使用自己的资源命名、自己的表、自己的 payload 约束

## 当前真实接口

### 1. 服务元信息

- `GET /api/meta`

### 2. 附件解析结果与原始资产

- `POST /api/test-case-service/documents/assets`
- `POST /api/test-case-service/documents`
- `GET /api/test-case-service/documents`
- `GET /api/test-case-service/documents/{document_id}`
- `GET /api/test-case-service/documents/{document_id}/relations`
- `GET /api/test-case-service/documents/{document_id}/preview`
- `GET /api/test-case-service/documents/{document_id}/download`

### 3. 正式测试用例

- `POST /api/test-case-service/test-cases`
- `GET /api/test-case-service/test-cases`
- `GET /api/test-case-service/test-cases/{test_case_id}`
- `PATCH /api/test-case-service/test-cases/{test_case_id}`
- `DELETE /api/test-case-service/test-cases/{test_case_id}`

### 4. 聚合读取

- `GET /api/test-case-service/overview`
- `GET /api/test-case-service/batches`
- `GET /api/test-case-service/batches/{batch_id}`

## 当前真实表

定义文件：`app/db/models.py`

- `test_case_documents`
  - 存 PDF / 图片 / 文本附件解析结果，以及原始资产路径
- `test_cases`
  - 存最终正式测试用例

## 当前与 runtime-service 的约定

当前 `test_case_service` 的持久化链路是：

```text
runtime-service/test_case_service
  -> 文档即时持久化 / persist_test_case_results
  -> interaction-data-service HTTP API
  -> test_case_documents / test_cases
```

约束：

1. 通用多模态中间件不负责 testcase 专属落库
2. `documents` 的即时写入由 `test_case_service` 私有层触发
3. `persist_test_case_results` 负责正式 `test_cases` 保存，并对缺失 `document_id` 的附件做补偿写入

`documents` 写入已支持幂等字段：

- `idempotency_key`

幂等范围：

- `project_id + batch_id + idempotency_key`

`test-cases` 写入也支持可选幂等字段：

- `idempotency_key`

幂等范围：

- `project_id + batch_id + idempotency_key`

## 当前与平台链路的约定

正式平台读取链路是：

```text
platform-web-vue
  -> platform-api-v2
    -> interaction-data-service
```

因此：

- `platform-web-vue` 不应把正式页面直接接到本服务
- `platform-api-v2` 负责项目权限、下载/预览代理、导出与聚合读取
- 本服务只维护结果域资源语义和结果域数据所有权

## 运行与排查

### 1. 查看服务元信息

```bash
curl "http://127.0.0.1:8081/api/meta"
```

### 2. 查看文档解析结果

```bash
curl "http://127.0.0.1:8081/api/test-case-service/documents?project_id=<project_id>&limit=20"
```

如需排查即时落库幂等，可带上 `batch_id`：

```bash
curl "http://127.0.0.1:8081/api/test-case-service/documents?project_id=<project_id>&batch_id=<batch_id>&limit=20"
```

### 3. 查看正式测试用例

```bash
curl "http://127.0.0.1:8081/api/test-case-service/test-cases?project_id=<project_id>&limit=20"
```

### 4. 查看总览与批次

```bash
curl "http://127.0.0.1:8081/api/test-case-service/overview?project_id=<project_id>"
curl "http://127.0.0.1:8081/api/test-case-service/batches?project_id=<project_id>&limit=20"
```

## 文档导航

- `docs/test-case-service-api-design.md`
  - 当前 testcase 结果域接口设计与字段约束
- `docs/service-design.md`
  - `Local Design`：更泛化的结果域抽象思路，不等于当前实现
- `docs/usecase-workflow-design.md`
  - `Historical-in-place`：旧 `usecase-generation` 方案记录
- `../runtime-service/runtime_service/docs/10-test-case-service-persistence-design.md`
  - 当前 runtime 到结果域的 testcase 持久化设计
