# 执行任务清单

> 本文件只保留对 **preferred future default** 有效的任务，同时把 2026-04-12 multi-workspace-first 执行思路视为 historical baseline。

## A. Docs refresh（本轮必须完成）

### A1 三态口径改写
- [ ] README 增加 current reality / historical baseline / preferred future default 三态说明
- [ ] `01`-`08` 统一改写为三态口径

### A2 新计划工件
- [ ] 新建 `.omx/plans/prd-metadata-aware-project-knowledge-20260417.md`
- [ ] 新建 `.omx/plans/test-spec-metadata-aware-project-knowledge-20260417.md`
- [ ] 将 2026-04-12 PRD/test-spec 标记为 superseded historical baseline

### A3 Contradiction sweep
- [ ] 检查 README + `01`-`08` + 新 PRD/test-spec
- [ ] 确认所有 multi-workspace wording 仅作为 historical baseline 或 fallback

## B. Preferred future default planning

### B1 上游通用能力目标
- [ ] ingest metadata/tag write contract
- [ ] query metadata/tag filter contract
- [ ] soft boost / hard filter 语义
- [ ] 上游协议保持通用，不绑定 AITestLab taxonomy

### B2 platform-api 未来契约
- [ ] 保持 project-scoped facade
- [ ] future query contract 预留通用 filters/boosts
- [ ] workspace 继续内聚在控制面

### B3 platform-web 未来交互
- [ ] retrieval scope/filter UX 草案
- [ ] documents metadata visibility 草案
- [ ] settings 说明 future default / fallback

### B4 runtime MCP 边界
- [ ] runtime 继续只认 `project_id`
- [ ] future metadata-aware retrieval 不改变 runtime project-centric 边界

## F. Fallback（仅当必要时启用）

### F1 fallback trigger
- [ ] 明确上游能力不足的判定条件

### F2 fallback multi-workspace
- [ ] 若进入 fallback，再单独规划多 workspace 对 control-plane/frontend/runtime 的影响

## Historical baseline note

此前围绕 workspace manager / request-scoped multi-workspace / dual-workspace acceptance 的详细任务，属于 **2026-04-12 historical baseline**，不再作为当前默认执行清单。

## C. 分阶段执行清单（implementation order）

### C1 LightRAG（先做）
- [ ] `/query` 支持 `metadata_filters`
- [ ] `/query/stream` 支持 `metadata_filters`
- [ ] ingest 支持 metadata/tag 写入
- [ ] `strict_scope` 语义落地

### C2 platform-api（第二层）
- [ ] `ProjectKnowledgeQueryRequest` 扩 `metadata_filters`
- [ ] `presentation/http.py` 接收并透传 `metadata_filters`
- [ ] `application/service.py` 透传 `metadata_filters`
- [ ] `adapters/knowledge/client.py` 原样转发
- [ ] upload facade 增 metadata 承载位

### C3 platform-web（第三层）
- [ ] `knowledge.service.ts` query payload 扩 `metadata_filters`
- [ ] `KnowledgeQuerySettingsPanel.vue` 增 filter UI
- [ ] `KnowledgeRetrievalPage.vue` 持有 scope/filter state
- [ ] Retrieval 结果回显当前 scope/filter
- [ ] recent query 持久化包含 scope/filter

### C4 runtime-service / test_case_service_v2（最后）
- [ ] `knowledge_mcp.py` 扩 `query_project_knowledge` 可选参数
- [ ] `prompts.py` 增“明确知识域时优先带 filter 查询”规则
- [ ] `README.md` 记录 metadata-aware retrieval 适配边界
- [ ] 如有必要再升级 `knowledge_query_guard_middleware.py`

## D. 最小 MVP（优先做这 4 件事）

- [ ] LightRAG `/query` 支持 `metadata_filters`
- [ ] platform-api query pass-through `metadata_filters`
- [ ] platform-web Retrieval 页支持 tags / layer filter
- [ ] test_case_service_v2 在“底层架构类问题”场景自动带 filter 查询

## E. MVP 验证口径

- [ ] “底层架构”类查询的应用层串味显著下降
- [ ] 前端未引入 knowledge-space chooser
- [ ] runtime 未学习 `workspace_key`
- [ ] 上游协议未绑定 AITestLab 私有 taxonomy
