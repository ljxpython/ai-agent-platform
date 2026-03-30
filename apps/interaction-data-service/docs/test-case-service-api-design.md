# test-case-service API 设计

## 目标

为 `runtime_service/services/test_case_service` 提供一组最小且稳定的结果域接口：

1. 保存附件解析结果
2. 保存最终正式测试用例
3. 支持平台后续查询与 CRUD

## 设计原则

1. 一个服务一个专属前缀
2. 一个资源一组明确接口
3. 不承载 workflow / snapshot / review 编排状态
4. 允许业务结果字段直接表达测试用例语义

## 路由前缀

- `/api/test-case-service`

## 资源 1：documents

### 写入

- `POST /api/test-case-service/documents`

请求体核心字段：

- `project_id`
- `batch_id`
- `idempotency_key`
- `filename`
- `content_type`
- `source_kind`
- `parse_status`
- `summary_for_model`
- `parsed_text`
- `structured_data`
- `provenance`
- `confidence`
- `error`

### 查询

- `GET /api/test-case-service/documents`
- `GET /api/test-case-service/documents/{document_id}`

查询条件：

- `project_id`
- `batch_id`
- `parse_status`
- `query`

### 幂等语义

`documents` 的写入支持幂等：

- 唯一范围：`project_id + batch_id + idempotency_key`
- 命中已有记录时：
  - 复用原 `document_id`
  - 按最新请求做有限字段更新
  - 不重复插入新行

这个约定用于支持 `test_case_service` 的“上传即落库 + 同批次重试不重复写入”。

## 资源 2：test-cases

### 写入

- `POST /api/test-case-service/test-cases`

请求体核心字段：

- `project_id`
- `batch_id`
- `case_id`
- `title`
- `description`
- `status`
- `module_name`
- `priority`
- `source_document_ids`
- `content_json`

### 查询和管理

- `GET /api/test-case-service/test-cases`
- `GET /api/test-case-service/test-cases/{test_case_id}`
- `PATCH /api/test-case-service/test-cases/{test_case_id}`
- `DELETE /api/test-case-service/test-cases/{test_case_id}`

查询条件：

- `project_id`
- `status`
- `batch_id`
- `query`

## 聚合资源：overview / batches

### 总览

- `GET /api/test-case-service/overview`

返回当前项目下的聚合统计：

- `documents_total`
- `parsed_documents_total`
- `failed_documents_total`
- `test_cases_total`
- `latest_batch_id`
- `latest_activity_at`

### 批次聚合

- `GET /api/test-case-service/batches`

返回批次级聚合：

- `batch_id`
- `documents_count`
- `test_cases_count`
- `latest_created_at`
- `parse_status_summary`

## 表结构

### 1. `test_case_documents`

用途：保存附件解析结果，支持来源追踪和回看。

关键字段补充：

- `idempotency_key`：用于同批次附件重试幂等

### 2. `test_cases`

用途：保存正式测试用例，平台后续围绕这张表做列表、详情、修改、删除。

完整业务结构统一收敛到 `content_json`，运行时元信息放入 `content_json.meta`。

## 删除的旧接口

以下业务接口已退役：

- `/api/usecase-generation/workflows/*`
- `/api/usecase-generation/use-cases/*`

它们不再是当前服务真实接口，也不应继续作为新开发范式参考。
