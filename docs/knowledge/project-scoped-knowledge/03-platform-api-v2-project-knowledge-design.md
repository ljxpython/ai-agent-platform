# platform-api-v2 项目知识工作台设计稿

## 1. 文档目的

本文只讨论 AITestLab `apps/platform-api-v2` 应该如何承接 **human-facing project knowledge workspace**。

重点说明：

- 它是 **control-plane facade**
- 它服务的是 `platform-web-vue` 的人工工作台和项目治理入口
- 它 **不是** future runtime programmatic consumption 的统一入口

## 2. 为什么仍然需要 platform-api-v2

当前仓库已经明确：

- `platform-api-v2` 管治理与边界（`apps/platform-api-v2/docs/handbook/project-handbook.md:32-51`）
- 前端正式页面统一只走 `platform-api-v2`（`apps/platform-api-v2/docs/handbook/project-handbook.md:112-119`, `apps/platform-web-vue/docs/control-plane-page-standard.md:54-66`）
- 当前平台已有 project-scoped gateway 先例（`apps/platform-api-v2/app/modules/runtime_gateway/presentation/http.py:17-65`）

因此只要是 **人工工作台**、**项目内治理操作**、**需要 permission / audit / operation 的知识页面**，就仍然应该走 `platform-api-v2`。

## 3. 模块命名建议

第一阶段建议新增：

```text
apps/platform-api-v2/app/modules/project_knowledge/
apps/platform-api-v2/app/adapters/knowledge/
```

选择 `project_knowledge` 而不是单纯叫 `knowledge_gateway` 的原因：

- 第一阶段不只是“代理 LightRAG”，还承担 project resource / permission / operation / audit 语义
- 该模块的正式语义是“项目知识工作台”而不是“某个透明 proxy”

## 4. 路由前缀建议

第一阶段建议统一走：

```text
/api/projects/{project_id}/knowledge/*
```

这更符合当前仓库的 project-scoped control-plane 语义，也与 `project_id` 作为治理主键的事实一致（`docs/development-guidelines.md:30-35`）。

## 5. 第一阶段资源模型建议

### 5.1 不建议第一阶段直接落双表

当前第一阶段不建议直接使用：

- `knowledge_bases`
- `project_knowledge_bindings`

作为最小实现。

原因：

- 当前没有 assistant binding
- 当前没有 multi-knowledge binding
- 当前没有 shared knowledge 正式需求
- 当前只需要承接“一项目一默认知识空间”

### 5.2 Phase 1 轻量模型

建议第一阶段先用：

```text
project_knowledge_spaces
```

字段建议：

- `id`
- `project_id`
- `provider`（Phase 1 固定 `lightrag`）
- `workspace_key`
- `display_name`
- `status`
- `service_base_url`
- `runtime_profile_json`
- `created_at`
- `updated_at`

这足以支撑：

- project 默认知识空间
- 项目知识设置页
- project -> workspace_key 治理映射
- 后续 phase 2 迁移到更重模型

### 5.3 演进路径

当以下任一需求真正进入实施范围时，再升级为：

- 多知识库绑定
- 共享知识库
- assistant 级覆盖（如果未来重新进入范围）

升级目标再转为：

- `knowledge_bases`
- `project_knowledge_bindings`

## 6. 第一阶段 API 面

### 6.1 工作台与设置

- `GET /api/projects/{project_id}/knowledge`
- `PUT /api/projects/{project_id}/knowledge`
- `POST /api/projects/{project_id}/knowledge/refresh`

### 6.2 Documents

- `POST /api/projects/{project_id}/knowledge/documents/upload`
- `POST /api/projects/{project_id}/knowledge/documents/scan`
- `POST /api/projects/{project_id}/knowledge/documents/paginated`
- `GET /api/projects/{project_id}/knowledge/documents/track-status/{track_id}`
- `GET /api/projects/{project_id}/knowledge/documents/pipeline-status`
- `DELETE /api/projects/{project_id}/knowledge/documents`

说明：AITestLab 控制面 upload 入口当前采用 **binary body + `x-knowledge-filename` header** 契约，避免平台层为单一工作台上传能力额外引入 multipart 依赖；真正对 LightRAG 的 upstream 调用仍由 adapter 侧转成 `multipart/form-data`。

### 6.3 Retrieval / Graph

- `POST /api/projects/{project_id}/knowledge/query`
- `GET /api/projects/{project_id}/knowledge/graph/label/list`
- `GET /api/projects/{project_id}/knowledge/graph/label/search`
- `GET /api/projects/{project_id}/knowledge/graphs`

说明：第一阶段图谱 mutation 是否开放，应该作为单独风险位处理；如果没有明确业务必要性，建议先只读。

## 7. 请求处理链

每个 knowledge 请求都走同一条链：

1. 解析 `project_id`
2. 校验 actor 对该项目的权限
3. 查询 `project_knowledge_spaces`
4. 取出 `workspace_key`
5. 注入 `LIGHTRAG-WORKSPACE`
6. 用 service auth 调 LightRAG
7. 做错误映射
8. 需要时接入 operation / audit

## 8. 权限建议

建议新增或复用：

- `project.knowledge.read`
- `project.knowledge.write`
- `project.knowledge.admin`

最小语义：

- read：看列表、检索、图谱、状态
- write：上传、扫描、删除
- admin：修改项目知识空间配置、清空文档、重建类动作

补充约束：

- `knowledge.documents.scan` 即使通过通用 operation 提交入口，也必须额外满足 `project.knowledge.write`
- `knowledge.documents.clear` 即使通过通用 operation 提交入口，也必须额外满足 `project.knowledge.admin`
- worker 真正执行 `clear` 时仍应再次按 `project.knowledge.admin` 校验，避免出现“提交时和执行时权限语义不一致”

## 9. operations / audit 建议

下列动作应优先 operation 化：

- 扫描目录
- 清空文档
- 批量导入
- 未来重建索引

因为当前平台已经明确：超过 3 秒、需要取消/重试/保留历史的动作应纳入 operation（`apps/platform-api-v2/docs/handbook/project-handbook.md:78-93`）。

## 10. 明确边界

这个模块不负责：

- future runtime-side MCP tool 暴露
- 把 knowledge 做成公共 runtime API 产品面
- assistant 绑定知识库
