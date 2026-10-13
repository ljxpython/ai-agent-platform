# 项目成员知识上传：平台侧接线

**状态：非前端与Final已完成；前端多格式/图片/v2与真实浏览器接续待同事完成。** 2026-10-12起，治理改动，标准模板。2026-10-13承接专项已完成真实Agent/成员共享、生命周期、两项目排队/去重与回退及Final；记录、当前方案与源码位置看[平台接线专项](../20261013-knowledge-documents-platform/README.md)。

当前 Worktree：`/Users/lijiaxin/.codex/worktrees/6394/ai-agent-platform`，沿既有 `feat/project-knowledge-mcp` 分支开发，不自行提交或推送。

本专项承接 [只读知识 MCP](../20261011-project-knowledge-mcp/README.md)。RAG 侧 G01/K01–K08 由同事负责；其原方案位于 `rag-anything-use/docs/projects/20261012-project-member-knowledge-upload/`。平台只负责权限、状态代理、精确授权、可信附件传输、MCP 与组合根接线，不保存索引、不创建第二队列。

- [方案与契约](plan.md)
- [任务和进度](tasks.md)
- [验证记录](verification.md)
- [前端交接](frontend-handoff.md)
- [RAG 实际协议与两项修复验收](provider-contract.md)
- [配置、启用和回退](deployment-runbook.md)
- [前端 fixture 来源](fixtures/README.md)
- [本地部署/真实旧查询证据](evidence/deployment-regression.json)
- [RAG 上轮失败与模型复验](evidence/rag-recheck.json)
- [RAG 5be564a 两项修复与 Runtime 实际联调](evidence/rag-5be564a-recheck.json)

已交付成员知识权限、四个项目 GET、read/upload/start/activate 专用授权、可信原件传输、两个 MCP 工具、两主图/HITL/Plan/deny 接线、同 key 失 ACK 回查及安全 DTO。没有新数据库迁移或平台第二队列；原只读 MCP 正常运行，新增上传默认关闭。实现细节见 [API](implementation/01-platform-api.md) / [Runtime](implementation/02-runtime-upload.md)。

2026-10-12历史修复复验时，RAG本地和远端main均为 `5be564ae5b28d010cf9beb26bc19ef11e7425cdd`，本轮 RAG78/API17/Runtime91项回归通过。实际 Platform API + RAG HTTP/MCP/supervisor + DeepSeek/百炼，七检查通过（178.512秒）：start/activate 200、失ACK GET返回原任务且不增加usage/attempt、Thread删除后继续ready、撤权拒绝且零模型调用、新旧来源和不可变快照。原 `febe70a` 403/405失败保留作历史，两项修复已验收。G01 冻结快照候选增量路线不变，平台不另建成果缓存。

Runtime 的可信附件、官方 MCP Adapter、真实平台授权到 RAG ready 另有七检查通过（141.466秒）；同key失ACK恢复、两并发同hash请求复用同一job且无新增usage、另一editor经实际平台GET读取资料/ready均通过。使用隔离SQL/IAM/Run和可信ToolRuntime fixture，未运行真实Agent Worker/浏览器，不能替代完整成员检索、Stop/重启/CAS/回退及大文件/负载验收。一次额外补测后台构建失败的证据保留，根因未采集，不宣称模型稳定性通过。

前端同事已交付F01–F03组件与自测记录；浏览器脚本含模拟知识响应，F02只断言助手消息可见并截图，不能算真实入库/回执闭环。本轮不改前端或RAG业务源码、不提交/推送、不发布生产；2026-10-13真实测试曾在所属隔离栈临时启用上传/v2，结束恢复默认。当前非前端V02已验，前端后续详见[新交接](../20261013-knowledge-documents-platform/frontend-handoff.md)，历史浏览器记录保持原边界。
