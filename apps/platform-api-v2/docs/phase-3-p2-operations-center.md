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

## 验收建议

1. 先在 `Runtime / Models` 触发一次刷新
2. 再在 `Assistants` 里触发一次重同步
3. 再在 `Testcase / 文档管理` 和 `Testcase / 用例管理` 各触发一次导出
4. 打开 `Operations Center`
5. 确认能看到以上操作的状态流转、详情内容、审计跳转和导出结果下载

## 当前边界

- 仍是 `db_polling` worker，不是 Redis queue
- 仍以 polling 为主，没有 SSE / WebSocket 推送
- 未做 artifact TTL、对象存储外接和批量归档
