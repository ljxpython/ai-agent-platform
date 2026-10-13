# 知识文档与图片平台接线

- 时间：2026-10-13 起
- 目标：完成 RAG 在线文档接入、来源 v2、图片可信上传的非前端实现及验证，交给前端同事接续。
- 模板类型：标准模板
- 改动级别：治理改动（跨服务契约及上传信任边界）
- 状态：已完成（全部非前端、前端 F01–F06、真实端到端测试闭环及 MCP 目录防死循环优化均 `done`，用户已通过最终验收）
- 工作区：`<worktree-root>`，分支 `feat/project-knowledge-mcp`。

入口：[方案](plan.md) · [任务](tasks.md) · [验证](verification.md) · [评审](review.md) · [前端交接](frontend-handoff.md) · [真实fixture](fixtures/README.md) · [联调恢复/正式合入](deployment-handoff.md)。承接 [成员上传](../20261012-project-member-knowledge-upload/README.md)。

RAG 基线：`research/rag-anything-use`，main `c30e2149ab975a3fc7e1539cc26216c0b9a0242e`；与 `2bd5818` 功能源码一致。Ubuntu 路径 `<ubuntu-home>/rag-anything-use`。

本阶段包含 Platform API、Runtime、真实 Worker 联调与前端交接。前端业务实现、正式合并/发布和业务语料生产容量评估由后续阶段负责。

Final：API223项＋182子断言、Runtime379项、Ubuntu RAG119项及local-stack5项通过；Runtime5项既有Docker专项跳过，不计通过。七类真实验收场景及默认v1旧查询smoke通过；50个后端变更Python文件lint/format及编译、shell/diff通过，详见[最终摘要](evidence/final-results.json)。没有新数据库迁移，保留Token/后台两分支及回执。

验收后已恢复Runtime/API私有配置，新上传关闭、来源1；旧768库显式固定ollama，避免源码新OpenAI配置覆盖缺省项。Ubuntu临时RAG/SSH通道及本worktree七个服务已停止，PG/Workspace/corpus/冻结版本保留，见[清理证据](evidence/cleanup.json)。本轮没有Git提交、合并或生产部署，RAG源码与前端业务源码未改。
