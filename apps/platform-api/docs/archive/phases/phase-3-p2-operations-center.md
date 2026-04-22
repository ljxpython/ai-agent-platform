# Phase 3 P2 - Operations Center 正式治理页

这份文档记录 `operations` 从后端能力升级为前端正式治理入口后的收口结果。

## 已完成内容

- `platform-web-vue` 已增加正式治理页：
  - `apps/platform-web-vue/src/modules/operations/pages/OperationsPage.vue`
  - 路由：`/workspace/operations`
- 页面支持：
  - 列表
  - 详情
  - 取消
  - 批量取消
  - 批量归档 / 恢复归档
  - 归档范围切换
  - 过期 artifact 不再继续展示下载按钮
  - 手动清理过期产物
  - 状态徽标
  - 输入 / 结果 / 错误 / 元数据查看
  - 审计跳转
  - 资源详情跳转
  - 导出型 operation 结果下载
- 后端已补产物下载出口：
  - `GET /api/operations/{operation_id}/artifact`

## 当前已纳入统一 operation 流的动作

- `runtime.models.refresh`
- `runtime.tools.refresh`
- `runtime.graphs.refresh`
- `assistant.resync`
- `testcase.documents.export`
- `testcase.cases.export`

## 前端接线结论

- `Assistants` 页面和详情页的 `重同步` 现在优先走 operation 流
- `Testcase Documents / Cases` 的导出在 v2 路径下优先走 operation + artifact 下载
- legacy 口径仍保留原同步接口，避免演示环境没切到 v2 时直接瘫掉
- `Operations Center` 本身属于 `platform-api-v2` 独占治理页，前端不再允许它错误回退到 legacy client

## 验收建议

1. 先在 `Runtime / Models` 触发一次刷新
2. 再在 `Assistants` 里触发一次重同步
3. 再在 `Testcase / 文档管理` 和 `Testcase / 用例管理` 各触发一次导出
4. 打开 `Operations Center`
5. 确认能看到以上操作的状态流转、详情内容、审计跳转和导出结果下载

## 当前边界

- 仍是 `db_polling` worker，不是 Redis queue
- 已增加 SSE 实时推送，前端保留 polling 兜底
- 未做 artifact TTL、对象存储外接

## 本轮补充收口

- 后端已增加：
  - `GET /api/operations/stream`
  - `POST /api/operations/bulk/cancel`
  - `POST /api/operations/bulk/archive`
  - `POST /api/operations/bulk/restore`
  - `POST /api/operations/artifacts/cleanup`
  - SSE 事件类型：`page`、`heartbeat`
- 前端 `Operations Center` 已接入实时同步状态提示：
  - `连接中`
  - `实时同步`
  - `轮询兜底`
- 前端 `Operations Center` 已增加：
  - 多选批量栏
  - 批量取消 / 批量归档 / 恢复归档
  - `仅未归档 / 包含已归档 / 仅已归档` 视图切换
  - artifact 过期时间 / storage backend 展示
  - 过期 artifact 清理动作
- 审计中间件已修正为：
  - 对 `StreamingResponse / text/event-stream` 不再捕获完整响应体
  - 仅记录基础审计，避免吞流导致 SSE 卡死
- artifact 生命周期已修正为：
  - 本地 artifact sidecar 元数据落盘
  - `expires_at` 到期后拒绝下载
  - 清理入口按过期时间清扫本地文件并回收空间
- 已补验证：
  - `tests.test_operations_streaming_and_retry`
  - `tests.test_operations_artifact_flow`
  - `tests.test_operations_bulk_archive`
  - `tests.test_operations_artifact_lifecycle`
