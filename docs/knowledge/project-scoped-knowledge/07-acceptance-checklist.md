# 验收与一致性清单

## 1. 文档状态声明

本清单同时验证：

- **current reality** 是否说清楚
- **historical baseline（2026-04-12）** 是否被正确标记
- **preferred future default** 是否被正确表达

## 2. Current reality checks

- [ ] 文档明确说明：当前 `project_id -> workspace_key` 映射仍是正式已存在能力
- [ ] 文档明确说明：frontend 默认仍然只认 `projectId`
- [ ] 文档明确说明：runtime 仍然是 `project_id`-centric
- [ ] 文档明确说明：当前 AITestLab / LightRAG HTTP 契约 **没有** 暴露 metadata/tag/filter retrieval 字段

## 3. Historical baseline checks

- [ ] 文档明确说明：2026-04-12 的 multi-workspace 路线是历史已验证基线
- [ ] 文档没有把 historical baseline 误写成 current default
- [ ] 旧 `.omx/plans/prd-project-scoped-knowledge-20260412.md` 已标记为 superseded historical baseline
- [ ] 旧 `.omx/plans/test-spec-project-scoped-knowledge-20260412.md` 已标记为 superseded historical baseline

## 4. Preferred future default checks

- [ ] 文档明确说明：未来默认方案是 single workspace + generic metadata-aware retrieval
- [ ] 文档明确区分：workspace 是物理隔离，metadata/tag/filter 是项目内检索隔离
- [ ] 文档明确说明：metadata-aware retrieval 仍是 target state，不是 current reality

## 5. Alternatives checks

- [ ] 文档存在明确 alternatives：
  - [ ] chosen：single workspace + generic metadata-aware retrieval
  - [ ] fallback：multi-workspace only if upstream support is unavailable/insufficient
  - [ ] rejected：AITestLab-private taxonomy in upstream protocol

## 6. Boundary checks

- [ ] frontend 不被要求理解 workspace internals
- [ ] runtime 不被要求理解 workspace internals
- [ ] 平台 docs 不把 AITestLab 私有 taxonomy 描述成上游协议固定字段

## 7. Contradiction sweep

对以下文件执行一致性检查：

- `docs/knowledge/project-scoped-knowledge/README.md`
- `01-platform-design.md`
- `02-lightrag-data-plane-plan.md`
- `03-platform-api-project-knowledge-design.md`
- `04-platform-web-knowledge-workspace-plan.md`
- `05-runtime-mcp-boundary.md`
- `06-delivery-roadmap.md`
- `07-acceptance-checklist.md`
- `08-execution-task-list.md`
- `.omx/plans/prd-metadata-aware-project-knowledge-20260417.md`
- `.omx/plans/test-spec-metadata-aware-project-knowledge-20260417.md`

通过标准：

- [ ] 任何 `multi-workspace` / `multiple workspaces` / `多 workspace` 相关表述，只能被标记为：
  - historical baseline，或
  - fallback
- [ ] 没有任何未标记的文案把 multi-workspace 写成 preferred default

## 8. Completion gate

- [ ] 新 PRD 存在
- [ ] 新 test-spec 存在
- [ ] README + `01`-`08` 已更新
- [ ] contradiction sweep 通过
