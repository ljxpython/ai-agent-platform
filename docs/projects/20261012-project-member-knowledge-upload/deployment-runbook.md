# 成员知识上传：配置、启用与回退

2026-10-13更新。非前端实施与V02实际Agent/生命周期门禁已完成；最新RAG基线main `c30e2149`、真实Ubuntu多格式/图片/v2验收与Final见[承接专项](../20261013-knowledge-documents-platform/verification.md)。新增上传默认关闭，前端与正式部署仍需接续；本文保留旧文本库配置，最新联调恢复/正式合入按[新交接](../20261013-knowledge-documents-platform/deployment-handoff.md)。

## 当前资源和配置位置

Worktree `/Users/lijiaxin/.codex/worktrees/6394/ai-agent-platform`，登记环境 `wt_39abb85e02a2`；Web/API/Runtime 地址分别为 `http://127.0.0.1:25457`、`http://127.0.0.1:24748`、`http://127.0.0.1:23512`，知识 MCP `http://127.0.0.1:63311/mcp`。以 `bash "scripts/local-stack.sh" status` 的实时登记为准。原生 PG、专属 Redis、Runtime local；三仓分别使用自己的 `.venv`。

Platform/Runtime 私有配置在本环境 `.local-stack/platform.env` / `runtime.env`，RAG 在 `.local-stack/knowledge/knowledge.env`。不打印、提交或复制秘密到其他 Worktree；不使用主环境库/Workspace。新 Worktree 先按 [资源隔离规范](../../standards/worktree-development.md) init/deps/doctor。

## API 与 Runtime

| 变量 | 用途 | 默认/要求 |
| --- | --- | --- |
| PLATFORM_KNOWLEDGE_MCP_BINDINGS_JSON | 可信 tenant:project → resource | `{}`；沿旧知识 MCP，新 Thread/fork 才获得绑定 |
| PLATFORM_API_KNOWLEDGE_CONNECTIONS_JSON | 同 resource → 受管 HTTP origin、token、scope、knowledge_base_id | `{}`；scope 必须与 binding 一致，origin 不带路径/用户密码/query |
| PLATFORM_API_KNOWLEDGE_UPLOAD_ENABLED | 平台新写门禁 | `false`；关闭不禁用资料/任务 GET 或旧查询 |
| PLATFORM_API_KNOWLEDGE_KEY_ID / SECRET | 知识专用 HMAC | `knowledge-v1` / 空；secret 至少 32 字节且不同于 JWT/委托/completion secret |
| RUNTIME_MCP_CONNECTIONS_JSON | 受管 MCP URL/Bearer/scope/allowed_tools | 沿旧配置；仅新增两工具名字，不能开放全部 mutation |
| RUNTIME_KNOWLEDGE_UPLOAD_ENABLED | Runtime submit 装配门禁 | `0`；只能 `0/1`，关闭时 submit 不进入 defaults/catalog |
| RUNTIME_KNOWLEDGE_KEY_ID / SECRET | 与 API/RAG 相同知识专用 key | `knowledge-v1` / 空；勿复用其他用途 secret |
| PLATFORM_KNOWLEDGE_AUTHORIZATION_URL | 精确授权回调 | 本所属 API `/api/runtime/internal/knowledge/authorize` |

API connections 结构示例，仅作为 schema，不包含可用秘密：

```json
{
  "knowledge_project_a": {
    "base_url": "http://127.0.0.1:63311",
    "token": "<private-project-token-at-least-32-characters>",
    "scope": {"tenant_id":"__default","project_id":"11111111-1111-4111-8111-111111111111"},
    "knowledge_base_id":"kb_11111111111111111111111111111111"
  }
}
```

同 resource 的 Runtime connection 沿 [MCP 规范](../../../apps/runtime-service/docs/standards/project-knowledge-mcp.md) 填 `streamable_http`、`url=<origin>/mcp`、同 Bearer/scope；allowed_tools 只列 query/submit/job 三个工具。开启写入必须配置真实 kb ID，不能由模型/FileRef 参数补出。

已初始化的旧 Worktree 缺少或空新增回调时，从本登记 API 地址派生；显式配置成其他环境仍预检失败。该兼容不写回私有配置、不回退主工作区。新增 GET 在 connections 缺失时 capability 安全降级为 not_configured，即使 legacy query 仍工作；不能据此声称查询回归。

## RAG 团队交付条件

同事提供隔离 online 服务代码版本、可访问地址、resource/scope/真实 kb、私下注入的 Bearer 和专用 HMAC。其当前源码配置名为 `KNOWLEDGE_ONLINE_ENABLED`、`KNOWLEDGE_AUTHORIZE_URL`、`KNOWLEDGE_AUTHORIZATION_KEY_ID`、`KNOWLEDGE_AUTHORIZATION_SECRET`；MCP token scope、模型、原件/任务/generation 目录与 worker 参数由 RAG 运维维护。authorize URL 指向本环境 API；三进程 key ID/secret 完全一致。

G01已有小语料证据，路线是完整冻结快照恢复到候选workspace、原生增量处理新资料。平台不另建成果缓存、索引或任务队列。[两项协议缺口](provider-contract.md)已由`5be564a`修复并实测验收；无需继续请求补字段/GET。对齐目标部署环境与剩余联合场景，平台严格校验保持。

## 启用顺序与验证

1. 使用已验`c30e2149`或兼容后续版本，对齐目标隔离online配置；先保留API=false、Runtime=0、来源1。capability现支持TXT/MD/PDF/DOCX/PPTX/PNG/JPEG，按网关交集选择，不混写旧768库与新1024库。
2. 当前平台V02已实测完成，目标部署仍需重做普通executor附件→MCP queued→start/activate→ready、另一成员查新旧资料及权限/生命周期门禁。前端按[最新交接](../20261013-knowledge-documents-platform/frontend-handoff.md)补多格式、图片、完整JSON与来源v2并做无mock浏览器验收；可仅在验收环境开启新写，失败即关闭。
3. 只在目标环境设置 API=true、Runtime=1；部署/重启由维护者操作。RAG 先就绪，再串行加载 API/Runtime API/Worker，刷新目录，创建新绑定 Thread。不要复用当前 legacy 数据目录做试验性原地增量写。
4. capabilities 明确 upload_enabled=true 且格式/上限符合；目录出现精确 submit/job；普通成员及当前 Thread ACL 实查。端口健康不是入库通过证据。

所属平台进程更新命令，从 Worktree 根逐条执行：

```bash
bash "scripts/local-stack.sh" doctor
bash "scripts/local-stack.sh" restart-one platform-api
bash "scripts/local-stack.sh" restart-one runtime-api
bash "scripts/local-stack.sh" restart-one runtime-worker
bash "scripts/local-stack.sh" status
```

串行完成启停再跑测试；本次发现同目录 pytest/HTTP fixture 会被既有 restart-one 的归属扫描回收，因此不要同时重启和执行测试。RAG 更新若已按本环境登记，沿 `knowledge-restart`；本轮未重启/覆盖同事 online 服务。目录刷新使用认证的 `POST /api/runtime/graphs/refresh`、`POST /api/runtime/tools/refresh`，不记录 token。

## 最小回退

关闭API上传与Runtime submit开关，串行重启对应三个平台进程并刷新目录。保留job工具和四只读GET的连接/专用授权配置。平台开关仅拒绝新submit/upload；已受理start/activate仍按原Run、当前IAM/凭据、签名与deny校验继续，不取消既有入库。撤权/凭据失效/submit deny仍可阻断排队执行与发布；授权最长30秒租约边界不变。禁止删除原件、索引、job、Thread/checkpoint或降低数据库版本。RAG项目uploads=off用于管理侧暂停/冻结回退，与平台关闭新增上传语义不同。

若只需禁用某项目的新提交，使用既有 tool-restrictions deny 精确 submit，再由 RAG 执行原主体/项目治理。全部知识停用另按旧专项流程 deny 查询/状态工具、撤 token；仅删除绑定不能撤已有 Thread。索引 active 版本回退由 RAG generation CAS/不可变版本完成，不要求重写历史 ToolMessage。

2026-10-13已在Ubuntu隔离RAG完成实际Agent/成员共享、处理中去重零新增用量、两项目排队与旧读、20MiB异步回执/Stop、API/Worker/RAG重启/Fork及冻结回退/恢复。当前样本规模不保证业务召回或生产吞吐；前端浏览器/正式部署未验。本轮无提交/push/生产发布；[新验证](../20261013-knowledge-documents-platform/verification.md)及[原验证](verification.md)保留证据与失败事实。
