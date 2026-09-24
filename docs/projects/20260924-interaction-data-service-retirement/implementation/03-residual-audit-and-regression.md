# 残留审计与主链路回归

## 时间与任务

2026-09-24；Task 2.1、2.2、3.2 补充核查。

## 残留审计

- 对 `apps/platform-web/src/`、`apps/platform-api/src/`、`apps/runtime-service/src/runtime_service/`、两套迁移目录及部署脚本检索旧服务名、Testcase 业务名、旧表和 8081；现行业务源码及迁移没有旧结果域实现或调用。前端/Platform API 的退役路由断言保留，用于防止旧入口复活。
- 发现两份 Compose、两个环境示例和现行部署说明仍传播 `TEST_CASE_V2_KNOWLEDGE_*`。Runtime 源码没有读取这些变量；删除这组无效配置和说明。`PLATFORM_API_KNOWLEDGE_UPSTREAM_*` 只出现在旧部署说明中，其没有实际配置入口，相关误导性说明一并去除。
- `apps/platform-web/e2e/support/platform.ts` 仍调用已不存在的 `PUT /runtime-policies/tools/{id}`。当前工具策略默认允许、通过 `tool-restrictions` 显式禁用，故删去夹具中的旧工具刷新与逐项启用步骤。未改三个主应用的业务代码。

## 验证

- 两份 Compose `config --quiet`、前端 typecheck 通过；现行配置/指南中不再有 `TEST_CASE_V2_KNOWLEDGE_*`。
- Playwright `chat-refactor.spec.ts` 的 1280 桌面用例通过，覆盖真实模型回复、刷新后历史、审批恢复与分支编辑。`control-plane-refactor.spec.ts` 的主路由用例通过，浏览器没有请求旧业务路由。
- 前端成果页及路由 8 个单测通过；Platform API `test_dear_artifacts_two_service_http` 通过，真实连接 Runtime 验证成果列表、预览/下载及 Runtime 重启后读取。
- `agent-refactor.spec.ts` 已越过旧夹具 404，但仍因测试使用旧标签“名称”而超时；当前 UI 标签为“智能体名称”。此为既有 E2E 用例与现行页面不一致，不作为退役链路通过证据。
- 新增 `apps/platform-web/e2e/retired-result-service.spec.ts` 并真实运行通过：临时项目中 Dear Agent 经审批写入并发布 Markdown；成果页经平台网关列出 SHA 命名文件、预览“退役验收成功”、下载同名文件。前两次失败来自测试沿用旧审批控件/源文件名及抽屉遮挡下载按钮，已修正；最终 1 通过（48.1 秒）。
- 使用全新临时 Docker 卷运行 `deploy/postgres/init/01-init-shared-databases.sh`，空库只生成 `postgres`、`platform_api`、`runtime_service` 和后两者角色；未生成旧库/角色。临时容器和卷已清除。
- 提交前修正 Dear Agent Memory 两份现行文档中的 3 处本机绝对路径，`scripts/check_docs.py` 复验通过。

## 未覆盖边界

用户确认本次仅覆盖本机，未来 Docker 部署自行管理。两份 Compose 未完整构建/启动；本机已验证配置解析和全新数据库初始化。项目本机范围标记 `done`。
