# Phase 3 P1 - Runtime Policies 正式治理页

这份文档记录 `runtime policy overlay` 从“文档结论”落到“正式可配置页面”的收口结果。

## 已完成内容

- 项目级 overlay 已有正式存储模型，不再让页面自己拼散装 JSON
- 已补齐三类目录的读取与更新接口：
  - `GET /api/projects/{project_id}/runtime-policies/models`
  - `PUT /api/projects/{project_id}/runtime-policies/models/{catalog_id}`
  - `GET /api/projects/{project_id}/runtime-policies/tools`
  - `PUT /api/projects/{project_id}/runtime-policies/tools/{catalog_id}`
  - `GET /api/projects/{project_id}/runtime-policies/graphs`
  - `PUT /api/projects/{project_id}/runtime-policies/graphs/{catalog_id}`
- 权限统一走项目级 runtime write/read 权限，不允许页面绕过控制面直接写目录状态
- 前端正式治理页已接入：
  - `apps/platform-web-vue/src/modules/runtime/pages/RuntimePoliciesPage.vue`
  - 路由：`/workspace/runtime/policies`

## 当前页面能力

- 按 `Models / Tools / Graphs` 三个视图查看 overlay
- 页头“刷新目录”会按当前 tab 触发底层 runtime catalog refresh operation，不再只是前端本地重拉 overlay 列表
- 支持启用/禁用、排序、备注等核心字段编辑
- 修改后直接回写控制面，不再由页面层自定义缓存协议
- 保持当前 `platform-web-vue` 的统一视觉与交互规范
- 接口与页面均按 `platform-api-v2` 作为唯一正式控制面处理，不再尝试走 legacy 治理链路

## 当前边界

- 当前是项目级 overlay，不做租户级/环境级多层覆盖合并
- 当前不接 quota / safety / routing 等未来高级策略
- 当前不做批量导入导出，避免提前把治理页做成配置垃圾场

## 验收建议

1. 登录 `platform-web-vue`
2. 进入任一项目
3. 打开 `Runtime / Policies`
4. 在 `Models / Tools / Graphs` 三个 tab 下分别点击页头“刷新目录”，确认会生成真实刷新任务并回灌最新目录
5. 分别修改 model/tool/graph 的策略字段
6. 刷新页面确认配置仍能正确回显
