# Phase 4 P1 - Operation Artifact 生命周期治理

这份文档记录 `operation export artifact` 从“只会本地落盘下载”升级到“带保留期、过期拒绝和清理入口”的当前收口。

## 当前目标

- 不让导出型 operation 的本地产物无限堆积
- 不让前端继续给已经过期的产物展示下载按钮
- 不把治理逻辑绑死在本地磁盘实现上，给后续 S3 / MinIO 一类对象存储预留清晰扩展边界

## 已完成内容

- 配置项：
  - `operations_artifact_storage_backend`
  - `operations_artifact_retention_hours`
  - `operations_artifact_cleanup_batch_size`
- 本地 artifact store 已增加：
  - `storage_backend`
  - `created_at`
  - `expires_at`
  - `retention_hours`
- 每个 artifact 保存时会写 sidecar 元数据文件：
  - `apps/platform-api-v2/app/modules/operations/application/artifacts.py`
  - 当前 sidecar 文件名：`.artifact.json`
- 下载链路已改成：
  - 到期后拒绝下载
  - 错误码：`operation_artifact_expired`
- 手动清理入口：
  - `POST /api/operations/artifacts/cleanup`
- 前端治理页已增加：
  - 过期 artifact 不再展示下载按钮
  - 显示 artifact 过期时间与 storage backend
  - 手动“清理过期产物”按钮
- `platform-config` 快照已补充 artifact 生命周期配置展示

## 当前实现边界

- 当前 `storage_backend` 只允许 `local`
- 当前清理入口是手动触发，不是定时任务
- 当前清理按 sidecar 元数据扫描本地目录，不依赖数据库 JSON 查询
- 当前不会回写 operation 结果载荷去删除 `_artifact` 字段
  - 前端通过 `artifact_expires_at` 判断是否继续展示下载入口

## 为什么这样设计

### 1. 不把清理逻辑绑定到数据库 JSON 查询

SQLite / PostgreSQL / 未来对象存储下，直接靠数据库里 `result_payload._artifact` 去做复杂查询会把实现绑死。

现在用 sidecar 元数据文件做清理口径，本地实现简单，后续切对象存储时也只需要替换 store，不用把 service / 前端治理页再推翻重写。

### 2. 先把治理边界定死，再扩 backend

当前平台还没正式切 Redis queue / S3 这类生产化后端，先把治理接口和前端交互收好，比盲目接一堆中间件更稳。

现在已经明确：

- store 必须提供 `save / resolve / cleanup`
- artifact payload 必须包含 `storage_backend / expires_at / retention_hours`
- 前端只能根据这些治理字段做展示，不直接猜本地路径

后面接对象存储时，只需要新增新的 store 实现。

## 后续扩展方向

### 对象存储

- 新增 `S3OperationArtifactStore` 或等价实现
- `storage_backend` 从 `local` 扩展为 `s3 / minio / oss`
- `relative_path` 可升级为对象 key
- 下载链路可扩成签名 URL 或平台代理下载

### 定时清理

- 接入 worker heartbeat / cron 后，把 `POST /api/operations/artifacts/cleanup` 对应逻辑变成周期任务
- 平台治理页保留手动触发入口作为兜底

### 审计与指标

- 记录每次 cleanup 的 `removed_count / bytes_reclaimed`
- 后续纳入 metrics / ops dashboard

## 验收建议

1. 触发一次 testcase export，确认 operation 详情出现：
   - `artifact_expires_at`
   - `artifact_storage_backend`
2. 手动把 artifact 过期时间调到过去，或等待过期
3. 确认前端不再展示下载按钮
4. 调用 `POST /api/operations/artifacts/cleanup`
5. 确认返回：
   - `removed_count`
   - `bytes_reclaimed`
6. 打开 `Platform Config`
7. 确认能看到 artifact retention / cleanup batch / backend 配置
