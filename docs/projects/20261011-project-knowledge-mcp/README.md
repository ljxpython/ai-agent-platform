# 项目知识检索 MCP 接入

**状态：blocked（非前端文本/MCP开发与本地部署已完成；PDF/Office、业务语料质量门禁缺环境/资料。前端由同事接续）。**

启动日：2026-10-11；治理改动。用户已明确“方案评审通过”“同意，基于源码在本地开发、启动和联调”“把除了前端的开发项都开发完成”，并授权提交与推送源码。本地部署已授权；未部署生产。

源码交付：知识工程已推送到 [`main`，提交 `568b8b7`](https://github.com/ljxpython/rag-anything-use/commit/568b8b73f8cfd86e111928c2ff12971a3d487fc0)；平台采用独立分支 [`feat/project-knowledge-mcp`](https://github.com/ljxpython/ai-agent-platform/tree/feat/project-knowledge-mcp)。平台分支基于本次开发/验证的 `116cc26f`，尚未合并主干；提交与推送不代表PDF/业务质量或前端验收完成。

## 交付

平台按可信项目给新Thread/fork签发只读知识资源，两主图共用官方MCP loader；外部 `rag-anything-use` 按Bearer固定项目范围检索已发布资料。来源与模型片段来自同一次检索，安全投影后随现有SSE/历史回放。未增加知识管理页面、知识业务表或自建Agent循环。

| 位置 | 本轮实际改动 |
| --- | --- |
| 平台 Worktree：`/Users/lijiaxin/.codex/worktrees/6394/ai-agent-platform` | Platform API可信绑定/私有输入拒绝、Runtime公共装配/来源预算、两主图/权限/测试、本地资源管理与文档 |
| 知识工程原工作目录：`/Users/lijiaxin/PyCharmMiscProject/research/rag-anything-use` | 认证/scope、路径与发布锁、单次检索/来源、文本离线入库、异步生命周期、重型依赖可选、CLI/测试/运行文档；不是新worktree |
| DeerFlow参考目录 | 只读借鉴外部RAG边界，未改参考项目 |
| `apps/platform-web` | 未改业务源码；真实fixture与交接文档在本专项 |

## 已验证与剩余工作

真实两项目HTTP隔离、两主图Worker→DeepSeek→MCP→回答/历史、用户/服务账号撤权、Stop无迟到结果、Worker重启、fork重签、新索引版本发布与保留旧索引、MCP/Embedding重启均有证据。3份合成Markdown、30道检索问题中20题有答案，Recall@8=100%、跨项目来源0，不能外推业务PDF质量。

知识工程24项测试、API59项相关回归、Runtime74项相关回归及11项真实模型关键链通过；平台全量检查存在旧失败，已在HEAD源码快照复现并列于[验证记录](verification.md)，不标“全仓全绿”。

- **B01：** Intel macOS x86_64/Python3.13无锁定Torch2.11 wheel。已尝试documents frozen安装，文本基础环境可用；未降核心锁/Python或引入Docker。需要兼容ARM Mac/Linux环境完成PDF/Office解析。
- **B02：** 未提供10–20份代表性业务资料/标注问题。需要资料路径及允许的模型环境，才能完成业务召回/引用/无答案门槛。
- **F1B：** 前端同事完成来源卡联验、必要的小适配与浏览器F01–F10。本轮交接已完成，不冒充浏览器验收。

## 本地联调

隔离环境 `wt_39abb85e02a2`。Web `http://127.0.0.1:25457`、API `http://127.0.0.1:24748`、Runtime `http://127.0.0.1:23512`，知识MCP `http://127.0.0.1:63311/mcp`、独立Ollama `127.0.0.1:65417`。凭据保留在本环境私有配置。

```bash
bash "scripts/local-stack.sh" status
bash "scripts/local-stack.sh" knowledge-restart
```

服务保留运行供同事接续。最新登记与启停见[部署手册](deployment-runbook.md)，不要把这些端口套用到其他worktree。

## 导航

- [tasks.md](tasks.md)：唯一进度来源、完成卡和Block请求。
- [plan.md](plan.md)：已批准设计、三层职责与契约。
- [provider-assessment.md](provider-assessment.md)：实施前源码评估，未实测判断由本次证据补充。
- [implementation/01-knowledge-mcp.md](implementation/01-knowledge-mcp.md)：文件/函数改动和发现。
- [verification.md](verification.md)：Phase证据、基线失败、未执行项。
- [frontend-handoff.md](frontend-handoff.md)：同事技术交接。
- [frontend-message.md](frontend-message.md)：可直接转发的话术。
- [fixtures/README.md](fixtures/README.md)：真实与受控协议样本来源。
- [deployment-runbook.md](deployment-runbook.md)：配置、入库、更新与回退。

接续原[知识检索评估](../20261010-agent-knowledge-retrieval-assessment/README.md)。关闭知识沿现有tool restriction，历史快照保留Thread ACL。
