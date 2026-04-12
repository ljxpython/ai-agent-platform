# 项目级知识库平台化总设计稿

## 1. 文档目的

这份文档定义 AITestLab 项目级知识库能力的正式边界。它回答的是：

1. 为什么现在适合把知识库做成平台能力
2. AITestLab 和 LightRAG 各自负责什么
3. 第一阶段应该做到哪里，哪些先不做
4. 为什么 future runtime-side consumption 要走 LightRAG MCP，而不是继续扩 platform API

## 2. 当前代码事实

### 2.1 AITestLab 已经具备 project-scoped control plane 基础

当前仓库已经明确：

- `platform-web-vue` 是正式前端宿主（`README.md:42-59`）
- `platform-api-v2` 是正式控制面，负责治理与边界，而不是 Runtime 真执行（`docs/development-paradigm.md:58-79`, `apps/platform-api-v2/docs/handbook/project-handbook.md:32-51`）
- 所有可查询数据必须可按 `project_id` 过滤（`docs/development-guidelines.md:30-35`）
- `platform-api-v2` 已有 project-scoped gateway 组织范式（`apps/platform-api-v2/app/modules/runtime_gateway/presentation/http.py:17-65`）
- `platform-web-vue` 已有唯一正式 workspace store 和 project route 模型（`apps/platform-web-vue/src/stores/workspace.ts:28-73`, `apps/platform-web-vue/src/router/routes.ts:28-48`）

### 2.2 LightRAG 已经具备 workspace 隔离基础，但还没完全平台化

当前外部参考仓库 LightRAG 已有：

- `LIGHTRAG-WORKSPACE` header 解析入口（外部参考：`lightrag/api/lightrag_server.py:458-486`）
- 但服务仍以单个 `rag = LightRAG(...)` 初始化为中心（外部参考：`lightrag/api/lightrag_server.py:1254-1289`）
- 其自身任务拆分稿也明确承认：workspace 还没有在所有关键 API 路径里统一生效，且实例复用/多 workspace 机制还没完全成型（外部参考：`docs/aitestlab-knowledge-lightrag-task-breakdown.md:52-97`）

这意味着 LightRAG 已经有“对的隔离原语”，但还没有被收口成“可被 AITestLab 稳定接入的 project knowledge data plane”。

### 2.3 当前仓库已存在 runtime-side knowledge MCP 先例

`test_case_service` 现在已经通过私有知识库 MCP 工具接知识能力，而不是把知识检索当成平台公开业务 API 直接塞进 runtime-service 内部（`apps/runtime-service/runtime_service/services/test_case_service/DESIGN.md:66-127`）。

这为 future runtime-side integration 提供了一个重要方向：

> future runtime-side consumption 可以优先走 MCP，而不是把平台控制面 API 和 runtime 程序化消费强行揉成一个入口。

## 3. 总体目标

目标不是把 LightRAG 当成一个独立产品嵌进 AITestLab，而是把它变成：

> **AITestLab 项目级知识空间的数据面服务**

最终要形成两条明确链路：

```text
Human-facing path
platform-web-vue -> platform-api-v2 -> LightRAG

Future runtime path
runtime-service / other services -> LightRAG MCP -> LightRAG
```

## 4. 角色边界

### 4.1 AITestLab 负责

- 项目上下文与 `project_id`
- project-level permission / audit / operations
- human-facing knowledge workspace UI
- 控制面 API、错误映射、操作中心接入
- `project_id -> workspace_key` 的治理侧绑定与维护

### 4.2 LightRAG 负责

- 文档上传 / 解析 / chunk / 图谱 / 检索
- workspace 级真实数据隔离
- track / pipeline / status 等知识处理状态
- future MCP 能力

### 4.3 明确不放在 LightRAG 的内容

- 平台用户体系
- project membership / permission
- 审计中心
- 平台操作中心
- control-plane navigation / page shell

## 5. 核心设计决策

### 决策 A：知识库能力是 project-scoped，不是 assistant-scoped

当前第一阶段不做 assistant 与 knowledge base 的显式绑定关系。原因很简单：

1. 现在先要解决的是 **项目级知识空间能不能稳定存在**
2. assistant 绑定是第二层能力，会显著放大资源模型、权限和 UX 复杂度
3. 用户已经明确第一阶段不把 assistant 作为知识库关系中心

### 决策 B：第一阶段做“一项目一默认知识空间”

第一阶段默认只落：

- 一个 project 对应一个默认 knowledge workspace
- 一个正式 human-facing knowledge workspace

但这不等于永远不支持：

- 多知识库绑定
- 共享知识库 / 跨项目共享

它们被明确定义为 **后续阶段**。

### 决策 C：Phase 1 先不把资源模型做重

当前第一阶段不建议直接上 `knowledge_bases + project_knowledge_bindings` 双表作为最小实现，而建议先用更轻的 `project_knowledge_spaces` 模型承接项目默认知识空间。

原因：

- 第一阶段尚无 assistant 绑定
- 第一阶段尚无一项目多知识库
- 第一阶段尚无共享知识库
- 过早把资源模型做成多对多，会让平台 API、页面、权限和验收全面变重

**演进策略**：

- Phase 1：`project_knowledge_spaces`
- Phase 2（多知识库 / 共享知识进入正式范围时）：再拆为 `knowledge_bases` + `project_knowledge_bindings`

### 决策 D：future runtime-side consumption 走 LightRAG MCP

未来 `runtime-service` 或其他 agent service 需要程序化消费知识能力时，不继续扩大 `platform-api-v2` 的职责去做一套统一 runtime consumption API。

原因：

1. `platform-api-v2` 的职责是 control plane，而不是所有运行期工具都从它出发（`apps/platform-api-v2/docs/handbook/project-handbook.md:32-51`, `apps/platform-api-v2/docs/handbook/project-handbook.md:101-119`）
2. 当前仓库已有 runtime 通过 MCP 使用知识能力的成功样式（`apps/runtime-service/runtime_service/services/test_case_service/DESIGN.md:66-127`）
3. 把 human-facing control-plane API 与 runtime 工具 API 强行统一，会把平台和 runtime 再次耦起来

## 6. 第一阶段范围

### In scope

- LightRAG request-scoped workspace 数据面收口
- AITestLab human-facing project knowledge control-plane module
- `platform-web-vue` 正式知识工作台页面
- `documents -> retrieval -> graph -> settings` 的实施顺序
- project-scoped permission / operation / audit 接入

### Out of scope

- assistant 绑定知识库
- 复杂审核流
- 文档级细粒度权限
- shared knowledge 正式上线
- multi-knowledge binding 正式上线
- runtime-service 通过 platform-api-v2 直接做通用程序化消费

## 7. 后续阶段范围

### Phase 2 候选

- 多知识库绑定
- 共享知识库
- knowledge resource/binding 模型升级
- LightRAG MCP 标准化
- runtime-service 通过 MCP 复用项目知识空间

## 8. 文档治理规则

当前目录是 AITestLab 侧正式事实源。后续如果 LightRAG 仓库内的设计文档与这里冲突，以当前目录为准，并回写更新外部参考设计稿，避免双边文档长期漂移。
