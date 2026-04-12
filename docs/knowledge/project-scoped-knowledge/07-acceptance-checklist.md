# 项目级知识库验收清单

> 勾选口径：`[x]` 表示当前仓内实现 + 本次静态/自动化验证已覆盖；`[ ]` 表示仍需要 live integration / 联调环境继续验收。

## 1. 验收目标

本清单用于验收以下三部分是否真正打通：

1. LightRAG request-scoped multi-workspace data plane
2. `platform-api-v2` human-facing project knowledge control plane
3. `platform-web-vue` project knowledge workspace

## 1.1 当前自动化证据快照（2026-04-12）

- [x] `uv run --directory apps/platform-api-v2 --with pytest python -m pytest -q tests/test_knowledge_client.py tests/test_project_knowledge_contract.py tests/test_project_knowledge_service_integration.py tests/test_operations_artifact_flow.py tests/test_operations_bulk_archive.py tests/test_operations_streaming_and_retry.py tests/test_operations_queue_backend.py`
  - 结果：`22 passed`
- [x] `pnpm vitest run src/services/knowledge/knowledge.service.spec.ts src/router/routes.spec.ts src/modules/knowledge/pages/KnowledgeSettingsPage.spec.ts`
  - 结果：`7 passed`
- [x] `pnpm build`
  - 结果：`vue-tsc --noEmit && vite build` 通过
- [x] `pnpm lint`
  - 结果：`0 errors`，仅保留现有 Vue 样式 warning
- [x] `./.venv/bin/python -m pytest -q tests/test_workspace_manager.py tests/test_workspace_migration_isolation.py tests/test_multimodal_config.py tests/test_workspace_isolation.py`（LightRAG 仓）
  - 结果：`23 passed`

说明：上面证据已经覆盖 repo 内实现、adapter 契约、knowledge 路由/页面 smoke，以及 LightRAG workspace/multimodal 的离线自动化验证；仍保留 `[ ]` 的条目，表示需要真实联调环境继续完成 live integration 验收。

## 1.2 当前 live integration 证据快照（2026-04-12）

- [x] 本地 bring-up：
  - `bash ./scripts/platform-web-vue-demo-up.sh`
  - `bash ./scripts/platform-web-vue-demo-health.sh`
  - 结果：`runtime-service` / `interaction-data-service` / `platform-api-v2` / `platform-web-vue` / worker 全部健康
- [x] LightRAG live service：
  - 在 `/Users/bytedance/PycharmProjects/test4/LightRAG` 启动 `./.venv/bin/lightrag-server`
  - `curl http://127.0.0.1:9621/health`
  - 结果：`200 OK`
- [x] A/B 项目 live 验收：
  - 新建 `Knowledge Live A 20260412-093956`
  - 新建 `Knowledge Live B 20260412-093956`
  - 结果：两项目都能解析独立 `workspace_key`
- [x] API + UI 联调证据已落盘：
  - `.omx/logs/knowledge-live-integration-20260412.json`
  - 结果：记录了 A/B 项目 `workspace_key`、文档列表、query 命中结果、graph labels / graph counts 以及泄漏检查
- [x] live 联调中额外发现并修复设置页真实问题：
  - 现象：Settings 页通过 `/api/projects/{project_id}/knowledge/` 命中 Vite proxy 的 `307 -> localhost:2142` 重定向链路，浏览器侧丢失鉴权头，触发 `session_expired`
  - 修复：`apps/platform-web-vue/src/services/knowledge/knowledge.service.ts`
  - 回归：`pnpm vitest run src/services/knowledge/knowledge.service.spec.ts` -> `5 passed`
- [x] multimodal live smoke：
  - LightRAG 启动口径：`PYTHONPATH=/Users/bytedance/PycharmProjects/test4/LightRAG ENABLE_MULTIMODAL_PROCESSING=true ./.venv/bin/python -m lightrag.api.lightrag_server`
  - multimodal 证据：`.omx/logs/knowledge-live-multimodal-20260412.json`
  - 结果：`pdf / jpg / png / docx / pptx / xlsx` 全部进入 query references，文档状态为 `processed`

## 2. 文档与边界基线

- [x] 当前目录文档已成为正式事实源
- [x] 第一阶段不再把 assistant 绑定写成必须范围
- [x] runtime-side future path 已明确为 LightRAG MCP
- [x] 多知识库 / 共享知识被明确定义为后续阶段，而非第一阶段阻塞项

## 3. LightRAG 数据面验收

### workspace 隔离

- [x] 同一服务实例支持多个 workspace
- [x] project A 上传的文档不会出现在 project B 文档列表中
- [x] project A 的 query 不会查到 project B 数据
- [x] project A 的 graph 不会读到 project B 图数据
- [x] project A 的删除不会影响 project B 数据

### 状态一致性

- [x] `track_status` 按 workspace 返回
- [x] `pipeline_status` 按 workspace 返回
- [x] 文档状态不会串 workspace

### 多模态稳定性

- [x] pdf 可上传
- [x] jpeg/png 可上传
- [x] docx 可上传
- [x] pptx 可上传
- [x] xlsx 可上传

## 4. platform-api-v2 验收

### 模块与模型

- [x] 存在 `project_knowledge` 模块
- [x] 存在 `adapters/knowledge`
- [x] `project_knowledge_spaces` 可读写
- [x] project 可解析到默认 `workspace_key`

### API 与边界

- [x] 前端 documents 请求走 `platform-api-v2`
- [x] 前端 retrieval 请求走 `platform-api-v2`
- [x] 前端 graph 请求走 `platform-api-v2`
- [x] gateway/facade 会注入 `LIGHTRAG-WORKSPACE`
- [x] 无 `project_id` 或无权限会被拒绝
- [x] human-facing errors 已按平台错误口径返回

### operations / audit

- [x] 长耗时动作可进入 operation
- [x] 前端可看到操作状态
- [x] 关键写操作可对接 audit

## 5. platform-web-vue 验收

### 路由

- [x] 存在 `/workspace/projects/:projectId/knowledge/*` 路由组
- [x] project 切换后知识页上下文正确变化
- [x] 无权限时页面或按钮按正式权限语义处理

### Documents

- [x] 可上传文档
- [x] 可看分页列表
- [x] 可看 `track_status`
- [x] 可看 `pipeline_status`
- [x] 可删除 / 清空

### Retrieval

- [x] 可发起查询
- [x] 可查看结果
- [x] 可查看引用 / 上下文

### Graph

- [x] 可搜索 label
- [x] 可查看图谱
- [x] 可展开属性面板

### Settings

- [x] 可看到默认知识空间摘要
- [x] 可看到 workspace 映射摘要
- [x] 可看到服务状态 / 运行说明

### UI 一致性

- [x] 页面壳层符合 control-plane 标准
- [x] 所有请求统一通过正式 service 层发起
- [x] loading / empty / error 完整
- [x] 危险动作有确认弹窗
- [x] 没有 LightRAG 原产品壳残留

## 6. 端到端场景

### 场景 A：Project A 文档入库并查询

- [x] 在 project A 上传文档
- [x] 文档出现在 project A 列表
- [x] query 命中 project A 内容
- [x] graph 只返回 project A 图数据

### 场景 B：Project B 不受影响

- [x] 切到 project B 后，看不到 project A 文档
- [x] 在 project B 下查不到 project A 数据

## 7. 当前非阻塞但需记录的后续项

- [ ] 多知识库绑定
- [ ] 共享知识库
- [ ] LightRAG MCP 正式化
