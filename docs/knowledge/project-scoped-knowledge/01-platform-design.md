# 项目级知识库平台化总设计稿

## 1. 文档目的

本文定义 AITestLab 项目级知识库能力在 2026-04-17 之后的正式口径，并明确区分三类内容：

1. **Current reality**：今天已经成立的 repo 与公开契约事实
2. **Historical baseline（2026-04-12）**：此前已验证、但不再作为默认推荐路径的 multi-workspace 基线
3. **Preferred future default**：如果可修改 LightRAG，未来默认采用的单 workspace + metadata-aware retrieval 方案

## 2. Current reality

### 2.1 AITestLab 现有边界

当前仓库已经明确：

- `platform-web-vue` 是正式前端宿主
- `platform-api-v2` 是正式控制面，负责治理、权限、审计、operation 边界
- `runtime-service` 保持运行时项目上下文为 `project_id`
- 当前项目知识模型仍是 `project_id -> workspace_key`

这些事实意味着：

- `project` 已经是稳定的治理边界
- workspace 细节是 control-plane / data-plane 内部实现，不是前端或 runtime 的主语义

### 2.2 当前公开契约限制

截至本文更新时，AITestLab 与 LightRAG 公开 HTTP 契约里仍然**没有** metadata/tag/filter retrieval 字段：

- `apps/platform-api-v2/app/modules/project_knowledge/application/contracts.py`
- `apps/platform-web-vue/src/services/knowledge/knowledge.service.ts`

因此任何关于 metadata-aware retrieval 的描述，都必须标成 **preferred future default / target state**，不能写成已实现事实。

## 3. Historical baseline（2026-04-12）

2026-04-12 那轮文档和计划把以下方向当成主路径：

- request-scoped multi-workspace data plane
- dual-workspace isolation verification
- multi-workspace 作为主要的项目级隔离/演进抓手

这些内容仍然是**历史上真实存在并验证过的基线**，但现在的角色发生变化：

- 它们不再是默认推荐路径
- 它们只作为历史事实与 fallback 参考存在

## 4. Preferred future default

如果可以修改 LightRAG，AITestLab 的首选未来默认架构是：

```text
project = governance boundary
workspace = default physical isolation
metadata/tag/filter = intra-project retrieval isolation
```

### 4.1 为什么选这个默认

因为用户真正要解决的是：

- 同一项目内部，底层架构 / 应用层 / 组件 / 网络 / 存储 / 计算等知识域之间的串味

这不是租户隔离问题，而是**项目内检索边界**问题。

### 4.2 为什么不继续把 multi-workspace 当默认

把 multi-workspace 当默认会带来：

- 前端概念变重
- control-plane 资源模型变重
- runtime 更容易被 workspace 语义污染
- 项目内多轴知识切分会快速碎片化

因此 multi-workspace 仅保留为 fallback。

## 5. 角色边界

### 5.1 AITestLab 负责

- `project_id` 治理主键
- permission / audit / operations
- 人工工作台
- 对上游能力的消费与治理映射

### 5.2 LightRAG 负责

- ingest / chunk / graph / retrieval
- workspace 物理隔离
- 如果可改，上游提供**通用** metadata-aware retrieval 能力：
  - metadata write on ingest
  - query filter
  - soft boost / hard filter

### 5.3 明确拒绝的方向

**Rejected option**：
- 把 AITestLab 私有的 `domain/layer/module` 语义硬编码进 LightRAG 协议字段或过滤协议

上游应提供的是**通用能力**，AITestLab 只消费并在本地定义自身 taxonomy。

## 6. Alternatives

### Option A — Chosen
**Single workspace + generic metadata-aware retrieval**

Pros:
- 最符合现有 repo 的 project-centric 边界
- 前端/runtime 不必理解项目内多 workspace
- 通用上游能力可被其他消费者复用

Cons:
- 依赖上游 LightRAG 补齐通用能力
- 当前公开 HTTP 契约尚未提供这些字段

### Option B — Fallback
**Project-internal multi-workspace**

Pros:
- 在上游能力缺失时，能提供更强的硬隔离

Cons:
- 概念与治理成本明显更高
- 不应再当默认主方案

### Option C — Rejected
**AITestLab-private taxonomy in upstream protocol**

Rejected because:
- 污染上游通用协议
- 把本地业务语义耦合到通用 RAG 服务

## 7. 对各服务的含义

### platform-api-v2
- 继续 project-scoped facade
- workspace 继续作为内部治理映射
- future 传给上游的 query 语义优先是通用 filter/boost，不是业务私有 taxonomy 协议

### platform-web-vue
- 继续 project 路由组织
- 不引入 knowledge-space chooser 作为默认主交互
- 更适合引入 retrieval scope / filter UX，而不是多 workspace 选择器

### runtime-service
- 继续只信任 `project_id`
- 不要求 runtime 持有或拼接 `workspace_key`
- future 若支持 domain-aware retrieval，也通过通用 query filter 能力接入

## 8. 结论

从现在开始，本目录的默认推荐路径是：

- **single workspace per project**
- **generic metadata-aware retrieval as target state**
- **multi-workspace as fallback only**

任何继续把 multi-workspace 写成“默认主方案”的内容，都必须改写为：

- historical baseline，或
- fallback
