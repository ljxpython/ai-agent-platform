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

## 7. 本地验证

```bash
uv run python -m py_compile \
  app/api/management/testcase.py \
  app/services/interaction_data_service.py \
  app/services/local_json_http_client.py \
  app/api/management/schemas.py

curl "http://127.0.0.1:2024/_proxy/health"
```
