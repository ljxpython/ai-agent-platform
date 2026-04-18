# AITestLab 项目级知识库平台化文档总览

> 状态说明
>
> - **Current reality（当前现实）**：截至 2026-04-17，AITestLab 与当前公开的 LightRAG HTTP API 仍以 `project -> workspace_key` 映射和单项目单 workspace 为正式已实现边界。
> - **Historical baseline（2026-04-12 历史基线）**：此前文档把 multi-workspace / request-scoped workspace data plane 当成主路径，相关验证与计划仍保留为历史事实。
> - **Preferred future default（首选未来默认）**：如果 LightRAG 可改，默认演进方向改为 **单 workspace + 通用 metadata/tag/filter 检索能力**；**multi-workspace 仅为 fallback**，不再作为默认主方案。

## 1. 当前已经确认的核心结论

### 1.1 能力定位

这次要做的仍然是 **平台级通用的 project-scoped knowledge capability**，但项目内知识域隔离的首选手段已经从“默认多 workspace”收敛为：

- `project`：治理边界
- `workspace`：默认物理隔离边界
- `metadata / tag / filter / boost`：项目内知识域隔离边界

### 1.2 当前现实

当前仓库与公开 HTTP 契约的事实仍然是：

- `platform-api-v2` 以 `project_id -> workspace_key` 维护项目知识空间
- `platform-web-vue` 只认 `projectId`，不直接感知 `workspace_key`
- `runtime-service` 保持 `project_id`-centric，不暴露 workspace 细节
- 当前公开 HTTP 契约 **还没有** 暴露 metadata/tag/filter retrieval 字段：
  - `apps/platform-api-v2/app/modules/project_knowledge/application/contracts.py`
  - `apps/platform-web-vue/src/services/knowledge/knowledge.service.ts`

### 1.3 首选未来默认

如果可以修改 LightRAG，推荐的默认架构是：

```text
one project = one workspace
+ generic metadata/tag/filter retrieval
+ soft boost / hard filter for intra-project domain isolation
```

这意味着：

- **不把项目内多 workspace 当成默认产品模型**
- **不让 frontend / runtime 引入 knowledge-space chooser 主语义**
- **不把 AITestLab 私有的 domain/layer/module 语义硬编码进上游协议**

### 1.4 fallback

只有当上游 LightRAG 的通用 metadata-aware retrieval 能力：

- 不可实现，或
- 可实现但不足以控制项目内串味

才退回到：

- 项目内多 workspace / 多物理知识空间

该路径在本目录中只应以 **historical baseline** 或 **fallback** 身份出现，**不再是默认推荐路径**。

## 2. 正式拓扑

### Human-facing path

```text
platform-web-vue -> platform-api-v2 -> LightRAG
```

### Future runtime path

```text
runtime-service / other services -> LightRAG MCP -> LightRAG
```

当前 runtime-side 仍保持：

- 输入主键：`project_id`
- 不暴露 workspace 细节
- 后续若支持 metadata/domain filter，也应通过通用协议能力传递，而不是让业务代码拼 workspace 规则

## 3. 文档目录

### Canonical docs（当前正式设计源）

1. [01-platform-design.md](./01-platform-design.md)
   - 当前现实 / 历史基线 / 首选未来默认 的总设计稿
2. [02-lightrag-data-plane-plan.md](./02-lightrag-data-plane-plan.md)
   - LightRAG 数据面与 metadata-aware retrieval 目标能力设计
3. [03-platform-api-v2-project-knowledge-design.md](./03-platform-api-v2-project-knowledge-design.md)
   - platform-api-v2 控制面契约与边界
4. [04-platform-web-vue-knowledge-workspace-plan.md](./04-platform-web-vue-knowledge-workspace-plan.md)
   - 前端知识工作台计划与检索范围 UX
5. [05-runtime-mcp-boundary.md](./05-runtime-mcp-boundary.md)
   - runtime-side MCP 边界
6. [06-delivery-roadmap.md](./06-delivery-roadmap.md)
   - 交付路线图（含 historical baseline 与 preferred future default）
7. [07-acceptance-checklist.md](./07-acceptance-checklist.md)
   - 验收与 contradiction sweep 清单
8. [08-execution-task-list.md](./08-execution-task-list.md)
   - docs refresh 与后续实现任务清单
9. [adr-001-single-workspace-default.md](./adr-001-single-workspace-default.md)
   - 关键 ADR

### Historical / specialized follow-on docs

以下文档仍保留，但在本轮未整体重写，应视为 **graph-focused historical follow-on docs**，不得覆盖本目录内新的默认决策：

- `09-platform-web-vue-knowledge-graph-redesign-plan.md`
- `10-platform-web-vue-knowledge-graph-single-milestone-plan.md`
- `11-platform-web-vue-knowledge-graph-acceptance-checklist.md`

## 4. `.omx` 计划工件

### Current planning artifacts
- `.omx/plans/prd-metadata-aware-project-knowledge-20260417.md`
- `.omx/plans/test-spec-metadata-aware-project-knowledge-20260417.md`

### Superseded historical baseline artifacts
- `.omx/plans/prd-project-scoped-knowledge-20260412.md`
- `.omx/plans/test-spec-project-scoped-knowledge-20260412.md`

## 5. 默认规则

- `project_id` 是 AITestLab 治理主键
- `workspace_key` 是默认项目级物理隔离主键
- `workspace_key` 不应成为 frontend/runtime 的主语义
- 项目内知识域隔离的首选目标能力是：
  - metadata write on ingest
  - metadata/tag filters on query
  - soft boost / hard filter
- **multi-workspace 只能作为 historical baseline 或 fallback 出现**
