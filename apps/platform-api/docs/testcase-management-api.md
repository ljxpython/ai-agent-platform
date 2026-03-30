# Testcase 管理接口

这份文档描述 `apps/platform-api` 当前新增的 testcase 管理面接口。

## 1. 路由前缀

统一前缀：

- `/_management/projects/{project_id}/testcase`

## 2. 当前接口

### 2.1 聚合读取

- `GET /overview`
- `GET /batches`

用途：

- 给 `platform-web` 的 Testcase 工作区提供总览与批次筛选信息

### 2.2 用例管理

- `GET /cases`
- `GET /cases/export`
- `GET /cases/{case_id}`
- `POST /cases`
- `PATCH /cases/{case_id}`
- `DELETE /cases/{case_id}`

### 2.3 文档解析结果

- `GET /documents`
- `GET /documents/{document_id}`

## 3. 权限约束

当前实现：

- 读接口：`admin / editor / executor`
- 写接口：`admin / editor`

所有接口都先经过：

- `require_project_role(...)`

## 4. 当前请求链路

```text
platform-web
  -> /_management/projects/{project_id}/testcase/*
    -> platform-api testcase router
      -> InteractionDataService
        -> interaction-data-service /api/test-case-service/*
```

## 5. 当前实现分层

路由：

- `app/api/management/testcase.py`

请求 schema：

- `app/api/management/schemas.py`

本地 HTTP client：

- `app/services/local_json_http_client.py`

interaction-data-service 业务封装：

- `app/services/interaction_data_service.py`

## 6. 设计约束

- `platform-api` 不直接持有 testcase 业务数据
- `platform-api` 负责项目权限校验与协议整形
- `interaction-data-service` 负责 testcase 记录的真实存储与聚合查询
- 本地 JSON HTTP client 只负责通用的 base_url / timeout / header / JSON 处理，不理解 testcase 字段

## 7. Excel 导出实施方案

### 7.1 接口

- `GET /_management/projects/{project_id}/testcase/cases/export`

查询参数复用列表页筛选：

- `batch_id`
- `status`
- `query`

权限：

- `admin / editor / executor`

返回：

- `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- `Content-Disposition: attachment; filename=...`

请求示例：

```http
GET /_management/projects/{project_id}/testcase/cases/export?batch_id=test-case-service:xxx&status=active&query=登录
Authorization: Bearer <token>
x-project-id: <project_id>
```

实现入口：

- 路由：`app/api/management/testcase.py`
- 业务：`app/services/interaction_data_service.py`
- Excel 生成：`app/services/testcase_case_export.py`

导出上限：

- 单次最多 `2000` 条 testcase
- 超限返回 `400 testcase_export_limit_exceeded:{total}>{limit}`

### 7.2 导出内容

一期固定导出一个 workbook，包含两张 sheet：

1. `测试用例`
   - 导出当前筛选命中的正式 testcase
   - 一行一条 testcase
2. `导出信息`
   - `project_id`
   - 当前筛选条件
   - 导出时间
   - 导出总条数

`测试用例` sheet 当前固定列：

- `Case ID`
- `标题`
- `模块`
- `优先级`
- `状态`
- `描述`
- `前置条件`
- `步骤`
- `预期结果`
- `测试类型`
- `设计技术`
- `测试数据`
- `备注`
- `质量门禁`
- `质量分数`
- `批次 ID`
- `来源文档 IDs`
- `创建时间`
- `更新时间`

数组字段使用单元格多行文本，不额外拆子表：

- `preconditions`
- `steps`
- `expected_results`
- `source_document_ids`

对象字段处理：

- `test_data` 以 JSON 字符串写入单元格
- `quality_gate / quality_score` 从 `content_json.meta.quality_review` 提取
- 缺省值统一导出为空字符串，避免前端和 Excel 模板出现不一致空值口径

### 7.3 实现边界

1. 只导出 testcase，不混入 PDF 解析记录
2. 由 `platform-api` 生成 Excel，前端只负责发起下载
3. 导出接口会按筛选条件拉取 testcase 全量数据
4. 为了稳定性，单次导出设置最大条数上限；超限时返回明确错误，要求先缩小筛选范围
5. Excel 结构保持稳定，避免前端自己拼字段导致口径漂移

### 7.4 页面联动约束

- 导出筛选条件必须和 `/cases` 列表页完全一致
- 当前页看到什么筛选结果，导出就按同一条件出什么结果
- 不能新增“仅导出当前分页”语义，避免用户误判导出范围
- 文件名统一由后端生成，前端不自行命名

### 7.5 当前真实验证口径

本地已按真实服务链路验证：

1. 启动 `interaction-data-service`
2. 启动 `platform-api` 并指向本地 `interaction-data-service`
3. 使用真实 `admin` 登录获取 token
4. 调用真实导出接口下载 `.xlsx`
5. 使用 `openpyxl` 反读文件，校验：
   - 存在 `测试用例 / 导出信息` 两张 sheet
   - 真实 batch 导出条数正确
   - `batch_id / source_document_ids / steps` 等字段已落入工作簿

## 8. 本地验证

```bash
uv run python -m py_compile \
  app/api/management/testcase.py \
  app/services/interaction_data_service.py \
  app/services/local_json_http_client.py \
  app/services/testcase_case_export.py \
  app/api/management/schemas.py

curl "http://127.0.0.1:2024/_proxy/health"
```
