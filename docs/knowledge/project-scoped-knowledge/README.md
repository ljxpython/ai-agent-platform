# AITestLab 项目级知识库平台化文档总览

> 状态：当前目录是 **AITestLab 仓库内的正式知识库设计事实源**。LightRAG 仓库里的 `aitestlab-knowledge-*` 文档仍可作为外部参考，但 AITestLab 侧的边界、交付顺序与验收口径以后统一以这里为准。

## 1. 当前已经确认的核心结论

### 1.1 能力定位

这次要做的不是某个单独业务服务的私有知识能力，而是 **平台级通用的 project-scoped knowledge capability**。

当前仓库已经明确把平台治理层和 Runtime 执行层拆开，且 `apps/platform-web-vue` 是正式前端宿主、`apps/platform-api-v2` 是正式控制面后端（`README.md:20-21`, `README.md:42-67`, `docs/development-paradigm.md:36-50`）。

### 1.2 正式拓扑

当前确认的正式拓扑分成两条：

```text
人工工作台 / 管理操作
  -> platform-web-vue
  -> platform-api-v2
  -> LightRAG

后续运行时 / agent 程序化消费（后续阶段）
  -> runtime-service / other services
  -> LightRAG MCP
  -> LightRAG
```

也就是说：

- **平台人机工作台** 继续走 `platform-api-v2`
- **未来 runtime 程序化消费** 不扩成统一平台后端 API，而是通过 LightRAG MCP 完成

### 1.3 第一阶段边界

第一阶段默认先做：

- 一个 `project` 对应一个默认知识空间
- `documents`
- `retrieval`
- `graph`
- `settings`

第一阶段明确 **不做**：

- assistant 与知识库绑定
- 复杂审核流
- 细粒度文档权限

这些需求不等于永远不做，而是 **不在当前第一阶段落地**：

- 多知识库绑定
- 共享知识库 / 跨项目共享知识

## 2. 为什么这些决策符合当前仓库范式

当前仓库已经把控制面、运行时、调试前端和结果域明确拆层，不鼓励在平台层硬写智能体运行逻辑（`README.md:82-92`, `docs/development-paradigm.md:54-79`, `apps/platform-api-v2/docs/handbook/project-handbook.md:32-51`）。

同时：

- 所有可查询数据必须可按 `project_id` 过滤（`docs/development-guidelines.md:30-35`）
- `platform-api-v2` 已经有 project-scoped gateway 先例（`apps/platform-api-v2/app/modules/runtime_gateway/presentation/http.py:17-65`）
- `platform-web-vue` 已经有唯一正式项目上下文与 route/permission 模型（`apps/platform-web-vue/src/stores/workspace.ts:28-73`, `apps/platform-web-vue/src/router/routes.ts:28-48`, `apps/platform-web-vue/docs/control-plane-page-standard.md:11-90`）

所以知识库能力的正确接法不是“把 LightRAG UI 原样搬进来”，而是：

- 平台治理、项目边界、审计、权限入口继续放在 AITestLab
- 真实知识数据隔离与处理能力放在 LightRAG

## 3. 文档目录

1. [01-platform-design.md](./01-platform-design.md)
   - 总设计稿
   - 定义边界、角色、阶段口径与后续演进边界
2. [02-lightrag-data-plane-plan.md](./02-lightrag-data-plane-plan.md)
   - 只讲 LightRAG 数据面如何收口
   - 包含后续 MCP 化方向
3. [03-platform-api-v2-project-knowledge-design.md](./03-platform-api-v2-project-knowledge-design.md)
   - 只讲 AITestLab 控制面如何承接 project-scoped knowledge workspace
4. [04-platform-web-vue-knowledge-workspace-plan.md](./04-platform-web-vue-knowledge-workspace-plan.md)
   - 只讲前端页面与工作台怎么落
5. [05-runtime-mcp-boundary.md](./05-runtime-mcp-boundary.md)
   - 只讲 future runtime / agent programmatic consumption 为什么转向 LightRAG MCP
6. [06-delivery-roadmap.md](./06-delivery-roadmap.md)
   - 实施顺序总表 + 阶段清单
7. [07-acceptance-checklist.md](./07-acceptance-checklist.md)
   - 验收清单
8. [08-execution-task-list.md](./08-execution-task-list.md)
   - 细粒度执行任务单，后续开发按此逐项打勾

## 4. 当前文档和 `.omx` 产物的关系

- `.omx/specs/deep-interview-knowledge-platform-lightrag.md`：澄清后的需求输入工件
- `.omx/plans/prd-project-scoped-knowledge-20260412.md`：共识计划 PRD
- `.omx/plans/test-spec-project-scoped-knowledge-20260412.md`：测试与验收规格
- `docs/knowledge/project-scoped-knowledge/`：长期维护的正式设计与交付文档

## 5. 当前默认规则

- `project_id` 是 AITestLab 治理主键
- `workspace_key` 是 LightRAG 数据隔离主键
- Phase 1 的默认 `workspace_key` 规则建议固定为：

```text
kb_<project_uuid_without_dashes>
```

- 前端不直接感知 `workspace_key`
- 前端不直接调用 LightRAG
- future runtime-side consumer 也不应该在代码里散落硬编码 workspace 规则
