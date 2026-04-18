# ADR-001 — Single workspace per project as default; metadata-aware retrieval for intra-project isolation

- Status: Accepted
- Date: 2026-04-17
- Source spec: `.omx/specs/deep-interview-multi-kb-design.md`

## Context

AITestLab 当前项目知识能力已经围绕：

- `project` 作为治理边界
- `workspace_key` 作为项目级物理隔离实现
- frontend / runtime 不暴露 workspace internals

用户新的设计目标不是重新做项目内多知识库对象，而是减少同一项目内不同知识域的检索串味。

## Decision

采用如下默认架构：

- **one project = one workspace**
- **generic metadata-aware retrieval** 作为项目内知识域隔离的首选未来默认方案
- **multi-workspace** 仅作为 fallback

## Drivers

1. 项目内知识域串味是核心问题
2. 现有 repo 边界天然更适配 project-centric 模型
3. 不希望 workspace 语义扩散到 frontend/runtime
4. 不希望把 AITestLab 私有 taxonomy 写进上游协议

## Alternatives considered

### Chosen
single workspace + generic metadata-aware retrieval

### Fallback
multi-workspace only if upstream support is unavailable or insufficient

### Rejected
AITestLab-private taxonomy in upstream protocol semantics

## Consequences

- 现有 docs 需要重写为三态口径
- 当前 reality 仍必须明确：metadata-aware retrieval 尚未公开实现
- multi-workspace 文案只能作为 historical baseline 或 fallback 出现

## Follow-ups

1. 更新 README + `01`-`08`
2. 新建 PRD/test-spec 计划工件
3. 执行 contradiction sweep
