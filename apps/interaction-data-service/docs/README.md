# interaction-data-service 当前说明

## 当前定位

`apps/interaction-data-service` 现在采用“每个 runtime 服务一个专属接口前缀”的范式。

当前已经落地的业务前缀：

- `/api/test-case-service`

这意味着：

- HTTP API 不再走通用 `record_type` 大入口
- 也不再保留旧的 `/api/usecase-generation/*` 业务接口
- 每个服务使用自己的资源命名、自己的表、自己的 payload 约束

## 当前真实接口

### 1. 附件解析结果

- `POST /api/test-case-service/documents`
- `GET /api/test-case-service/documents`
- `GET /api/test-case-service/documents/{document_id}`

### 2. 正式测试用例

- `POST /api/test-case-service/test-cases`
- `GET /api/test-case-service/test-cases`
- `GET /api/test-case-service/test-cases/{test_case_id}`
- `PATCH /api/test-case-service/test-cases/{test_case_id}`
- `DELETE /api/test-case-service/test-cases/{test_case_id}`

### 3. 聚合读取

- `GET /api/test-case-service/overview`
- `GET /api/test-case-service/batches`

## 当前真实表

定义文件：`app/db/models.py`

- `test_case_documents`
  - 存 PDF / 图片 / 文本附件解析结果
- `test_cases`
  - 存最终正式测试用例

## 与 runtime-service 的约定

当前 `test_case_service` 的持久化链路是：

```text
runtime-service/test_case_service
  -> persist_test_case_results
  -> interaction-data-service HTTP API
  -> test_case_documents / test_cases
```

受信上下文约定：

- `project_id` 优先从 `runtime.context / runtime.config / runtime.state` 读取
- 当前如果尚未正式透传，可使用 `test_case_default_project_id` 兜底

## 运行与排查

### 1. 查看服务元信息

```bash
curl "http://127.0.0.1:8081/api/meta"
```

### 2. 查看文档解析结果

```bash
curl "http://127.0.0.1:8081/api/test-case-service/documents?project_id=<project_id>&limit=20"
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

## 相关文档

- `docs/service-design.md`
- `docs/test-case-service-api-design.md`
- `../runtime-service/runtime_service/docs/10-test-case-service-persistence-design.md`
