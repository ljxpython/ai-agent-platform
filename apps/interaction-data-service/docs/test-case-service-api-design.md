# test-case-service API 设计

状态：`Current API Design`

这篇文档描述当前 `interaction-data-service` 中 `test-case-service` 切片的接口设计。

当前代码真相源优先级：

1. `app/api/test_case_service/**`
2. `app/db/models.py`
3. 本文

如需理解更高层边界，请同时参考：

- `README.md`
- `docs/README.md`
- `../runtime-service/runtime_service/docs/10-test-case-service-persistence-design.md`

退役说明：旧的 `/api/usecase-generation/*` 只保留为历史记录，不再作为当前实现参考。

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
- `GET /api/test-case-service/documents/{document_id}/relations`
- `GET /api/test-case-service/documents/{document_id}/preview`
- `GET /api/test-case-service/documents/{document_id}/download`

### 原始资产

二期新增：

- `POST /api/test-case-service/documents/assets`

用途：

- 保存原始 PDF 文件资产
- 返回稳定的 `storage_path`
- 供后续 `documents/{document_id}/preview|download` 使用

设计约束：

1. 原始文件资产与 `documents` 元数据分离
2. 不把 PDF 二进制写入 `test_case_documents`
3. `documents` 仍只保存解析结果与来源元信息
4. 服务需安装 `python-multipart`，否则 `multipart/form-data` 路由无法启动

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
- `idempotency_key`
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

### 幂等语义

`test-cases` 的写入现在也支持可选幂等：

- 唯一范围：`project_id + batch_id + idempotency_key`
- 只有请求显式传入 `idempotency_key` 时才启用
- 命中已有记录时：
  - 复用原 `test_case_id`
  - 用最新请求覆盖 `title / description / status / module_name / priority / source_document_ids / content_json`
  - 不重复插入新行

当前用途：

- 仅用于 `runtime-service/test_case_service` 的自动正式保存
- 平台人工 CRUD 默认不传 `idempotency_key`，仍保持普通新增语义

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
- `GET /api/test-case-service/batches/{batch_id}`

返回批次级聚合：

- `batch_id`
- `documents_count`
- `test_cases_count`
- `latest_created_at`
- `parse_status_summary`

`batches/{batch_id}` 额外返回：

- 当前 batch 汇总
- 当前 batch 的 documents 分页结果
- 当前 batch 的 testcase 分页结果

## 表结构

### 1. `test_case_documents`

用途：保存附件解析结果，支持来源追踪和回看。

关键字段补充：

- `idempotency_key`：用于同批次附件重试幂等
- `storage_path`：指向原始文件资产相对路径
- `provenance.runtime.thread_id`
- `provenance.runtime.run_id`
- `provenance.runtime.agent_key`

### 2. `test_cases`

用途：保存正式测试用例，平台后续围绕这张表做列表、详情、修改、删除。

完整业务结构统一收敛到 `content_json`，运行时元信息放入 `content_json.meta`。

关键字段补充：

- `idempotency_key`：用于 `test_case_service` 自动保存时的正式 testcase 幂等覆盖

## 二期接口方案

### 1. documents/assets

#### 1.1 写入

- `POST /api/test-case-service/documents/assets`

建议请求形态：

- `multipart/form-data`

核心字段：

- `project_id`
- `batch_id`
- `document_id` 或 `idempotency_key`
- `filename`
- `content_type`
- `file`

返回建议：

```json
{
  "storage_path": "test-case-service/<project_id>/<batch_id>/<idempotency_key>.pdf",
  "content_type": "application/pdf",
  "filename": "接口文档.pdf",
  "size": 123456
}
```

实现原则：

1. 第一版使用本地文件系统
2. 路径按 `project_id / batch_id / idempotency_key` 组织
3. 同一 `project_id + batch_id + idempotency_key` 重复上传时允许覆盖或复用

### 2. documents/{document_id}/relations

用途：

- 返回当前 document 关联到的正式 testcase
- 支持平台页面展示“这份 PDF 影响了哪些测试用例”

返回建议：

```json
{
  "document": { "...": "..." },
  "runtime_meta": {
    "thread_id": "xxx",
    "run_id": "xxx",
    "agent_key": "test_case_service"
  },
  "related_cases": [
    {
      "id": "uuid",
      "case_id": "TC-001",
      "title": "登录成功",
      "status": "active",
      "batch_id": "test-case-service:thread"
    }
  ],
  "related_cases_count": 1
}
```

查询实现：

- 通过 `test_cases.source_document_ids` 包含当前 `document_id` 反查

### 3. documents/{document_id}/preview 与 download

用途：

- `preview`：浏览器内联预览 PDF
- `download`：附件下载

约束：

1. 仅当 `storage_path` 有效时可用
2. 若原始资产缺失，返回明确错误：
   - `404 document_asset_not_found`
3. `Content-Disposition` 必须输出 `filename*=UTF-8''...`，保证中文文件名预览/下载可用

### 4. documents/export

说明：

- `documents/export` 不在 `interaction-data-service` 直接生成 Excel
- 导出工作仍由 `platform-api-v2` 统一完成
- 当前服务只提供稳定分页查询接口和详情/关系接口

## 二期实现边界

1. `interaction-data-service` 负责：
   - document 元数据存储
   - 原始文件资产读写
   - 文档与 testcase 关系查询
2. 不负责：
   - Excel workbook 生成
   - 平台项目权限判断
   - runtime 业务流程控制

## 二期真实验证口径

禁止 mock。

至少验证：

1. 真实 PDF 上传后 `documents/assets` 可保存文件
2. `documents` 记录中的 `storage_path` 与真实文件路径一致
3. `preview / download` 返回真实 PDF 内容
4. `relations` 返回的 testcase 与 `source_document_ids` 实际关联一致
5. 同一批次相同 `idempotency_key` 重试时不产生脏数据

## 删除的旧接口

以下业务接口已退役：

- `/api/usecase-generation/workflows/*`
- `/api/usecase-generation/use-cases/*`

它们不再是当前服务真实接口，也不应继续作为新开发范式参考。
