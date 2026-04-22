# 项目级知识库交付路线图

## 1. 文档目的

本文明确新默认方向下的交付顺序，并保留 2026-04-12 historical baseline 作为参考。

## 2. Current reality vs historical baseline vs preferred future default

### Current reality

今天 repo 内已成立的是：

- project-scoped knowledge facade
- 项目默认 workspace 映射
- 前端 knowledge 工作台
- runtime `project_id`-centric 边界

### Historical baseline（2026-04-12）

历史上优先级最高的是：

- request-scoped multi-workspace data plane
- dual-workspace isolation
- 以 workspace 为主隔离抓手

这些内容仍保留为：

- historical baseline
- fallback 能力基础

### Preferred future default

今后若可改上游，主顺序变为：

1. 冻结 docs 口径与 ADR
2. 补齐上游 generic metadata-aware retrieval 目标设计
3. 定义 platform-api 通用 retrieval contract
4. 定义 platform-web retrieval scope/filter UX
5. 保持 runtime `project_id`-centric MCP 边界
6. 仅在必要时启用 multi-workspace fallback

## 3. 当前推荐顺序

### Phase 0 — 文档与口径冻结
- [x] deep-interview 收敛
- [x] ralplan 共识
- [x] README + `01`-`08` 改写为三态口径
- [x] 新 PRD/test-spec 落盘

### Phase 1 — 上游目标能力设计
- [ ] 明确 ingest metadata contract（target state）
- [ ] 明确 query filter / boost contract（target state）
- [ ] 明确 hard filter / soft boost 语义
- [ ] 明确不把 AITestLab 私有 taxonomy 写进上游协议

### Phase 2 — platform-api 未来契约设计
- [ ] project-scoped facade 保持不变
- [ ] future retrieval contract 预留通用 filters/boosts
- [ ] 不泄露 workspace 语义

### Phase 3 — platform-web 未来交互设计
- [ ] retrieval scope/filter UX
- [ ] documents metadata/tag 展示策略
- [ ] settings 中的 current reality / future default / fallback 说明

### Phase 4 — runtime MCP 路线固化
- [ ] MCP 仍保持 project-centric
- [ ] fallback 时不让 runtime 直接持有 workspace 规则

### Phase F — Fallback multi-workspace
只有在上游 metadata-aware retrieval 不可实现或不足时才进入：
- [ ] fallback 策略
- [ ] fallback 对 platform/runtime 的最小侵入设计

## 4. Historical baseline 处理规则

以下旧路径不删除，但不再写成默认推荐：

- multi-workspace-first
- dual-workspace-first acceptance
- workspace-first execution ordering

这些内容只允许在文档中作为：

- historical baseline，或
- fallback

## 5. 现在不建议做的事

- 不要把 metadata-aware retrieval 写成已实现现实
- 不要把 multi-workspace 保留为 co-equal default
- 不要让 frontend/runtime 主交互切成多个 knowledge spaces
- 不要把 AITestLab 私有 taxonomy 嵌入上游协议

## 6. 本轮 docs hardening（file-level adaptation pass）

这轮新增的 docs hardening 只做一件事：

> 把已经讨论清楚的 file-level 适配面，分别写入现有 canonical 边界文档，而不是再创建一个并行 canonical doc。

### 本轮落点

- `03-platform-api-project-knowledge-design.md`
  - 主锚点：`apps/platform-api/app/modules/project_knowledge/application/contracts.py`
- `04-platform-web-knowledge-workspace-plan.md`
  - 主锚点：`apps/platform-web/src/services/knowledge/knowledge.service.ts`
- `05-runtime-mcp-boundary.md`
  - 服务落点：`apps/runtime-service/runtime_service/services/test_case_service_v2`
  - 具体锚点：`apps/runtime-service/runtime_service/services/test_case_service_v2/knowledge_mcp.py`

### 为什么不新建 canonical doc

因为这轮内容本质上不是新的架构边界，而是：

- 对既有 03/04/05 文档的 file-level 落地补强
- 对 06 路线图的追踪补记

如果再单独新建一个 canonical 设计稿，会引入第二份“实现适配总表”，增加冲突风险。

### 本轮完成标准

- [x] `03` 已写入 platform-api file-level adaptation anchor
- [x] `04` 已写入 platform-web file-level adaptation anchor
- [x] `05` 已写入 test_case_service_v2 landing zone 与 `knowledge_mcp.py` 锚点
- [x] `06` 已记录这轮 docs hardening pass
- [x] 未新增新的 canonical file-level doc

## 7. 分阶段实施顺序（field-level rollout order）

在 file-level 适配已经讨论清楚之后，推荐实施顺序进一步收敛为：

### Stage 1 — 先改 LightRAG（能力提供方）

目标：先让上游具备最小可消费能力，否则下游只能继续停留在文档设计。

最小必做：
- ingest metadata/tag 写入能力
- `/query` / `/query/stream` 支持 `metadata_filters`
- `strict_scope` 语义成立

建议后做：
- `metadata_boost`
- documents list 按 metadata 辅助筛选
- 图谱检索的 domain-aware 行为增强

### Stage 2 — 再改 `platform-api`（contract + pass-through）

目标：把上游能力收进 AITestLab 的 project-scoped facade。

最小必做：
- `ProjectKnowledgeQueryRequest` 扩 `metadata_filters`
- `query` / `stream_query` 透传 `metadata_filters`
- upload facade 支持 metadata 承载位

建议后做：
- `metadata_boost`
- `strict_scope`
- DocumentsPageQuery 的 metadata filter

### Stage 3 — 再改 `platform-web`（最小用户价值闭环）

目标：先验证“串味是否下降”，而不是一次性把所有管理面做满。

最小必做：
- Retrieval 页支持 tags / layer 过滤
- 结果页回显当前 scope/filter
- query local state / localStorage 持久化包含 scope

建议后做：
- Documents 上传 metadata 输入
- Documents 列表 metadata 展示
- Settings 里的 taxonomy / preset 配置

### Stage 4 — 最后改 `test_case_service_v2`（最小侵入适配）

目标：服务继续只认 `project_id`，只补“在合适时带 filter 查”的能力。

最小必做：
- `query_project_knowledge` 工具参数扩 `metadata_filters`
- prompt 增“有明确知识域时优先带 filter”规则

建议后做：
- `metadata_boost`
- `strict_scope`
- guard middleware 的 domain-aware 查询约束

## 8. 最小 MVP 闭环

如果只做一个最小验证闭环，推荐按下面 4 步落地：

1. **LightRAG**：`/query` 支持 `metadata_filters`
2. **platform-api**：query contract 透传 `metadata_filters`
3. **platform-web**：Retrieval 页支持 tags / layer 过滤输入
4. **test_case_service_v2**：在“底层架构类问题”场景自动带 filter 查询

### MVP 成功判据

- 当用户查询“底层架构”类问题时，应用层知识串味显著下降
- `platform-web` 不引入 knowledge-space chooser
- `runtime-service` 仍不学习 `workspace_key`
- 上游协议仍是通用 metadata filter，而不是 AITestLab 私有 taxonomy

## 9. 本轮推荐优先级

### P0
- LightRAG query filter
- platform-api pass-through
- platform-web retrieval filter UI

### P1
- ingest metadata write
- documents metadata 展示
- `test_case_service_v2` prompt + tool 参数适配

### P2
- metadata boost
- settings presets
- documents metadata filter
- guard middleware 升级
