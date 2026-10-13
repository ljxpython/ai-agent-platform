# 平台侧验证计划和记录

当前状态：非前端实施与V02实际Agent/生命周期验收已完成，最新Final见[承接专项](../20261013-knowledge-documents-platform/verification.md)。本文各`2026-10-12`记录保留当时partial/失败，不作为当前阻塞；前端多格式/图片/v2及无mock浏览器由同事接续，正式新增上传默认关闭。

## 验证计划

- A01：角色权限、当前成员/服务账号、项目生命周期、四 HTTP DTO/分页、安全投影、超时/错误。
- A02：精确 HMAC/租约、过期/篡改/错操作/跨 scope、撤权、Thread ACL、后台不依赖聊天存活。
- R01：FileRef 六字段/可信消息、原字节/hash、私有 header、官方 Adapter、失 ACK/同 key/未知回执、取消与恶意响应。
- R02：两主图、Plan/schema/offload/子图/deny、HITL 与陌生 mutation。
- O01：默认关闭/旧查询、配置校验、所属启停、文档/fixture 无 secret。
- V01：真实平台 HTTP→Runtime→受控 MCP 全链与服务回归、静态检查；明确测试替身范围。
- V02：实际RAG入库/索引/查询、G01费用与恢复；2026-10-13在[承接专项](../20261013-knowledge-documents-platform/verification.md)完成真实平台Worker/成员及Ubuntu生命周期联验。

## Phase 验证记录

### A01 成员权限与项目状态代理 · 2026-10-12

通过。三项目角色read/upload、executor无runtime.write、当前非成员/撤权/disabled项目/scope拒绝；分页/严格query、DTO私密字段清除、10秒/1MiB边界、Session在网络await前关闭/返回前授权复核。`tests/test_knowledge_member_upload.py`与API回归集合45 passed/21 subtests；真实HTTP四GET受控链通过。

### A02 四用途授权 · 2026-10-12

通过。专用HMAC/30秒grant、签名/过期/错scope/用途/主体/Plan/deny拒绝，read写关闭仍可用且active项目/Thread/原Run复核；后台start/activate保留原Run绑定、Thread删除仍允许，排队后/activate前撤权和服务账号credential撤销拒绝。`tests/test_knowledge_authorization.py`含真实audit数据库安全ID断言，包含在API45/21中。此为平台入口证据，RAG实际后台请求仍需对齐。

### R01 可信原件、同key与安全回执 · 2026-10-12

通过。FileRef路径/size/MIME/hash/多余字段/跨Thread/修改/symlink、原名回执/旧附件/fork、私有headers、原bytes、MCP取消、I/O后撤权、失ACK同key只读回查且不submit；恢复时先刷新grant，null job迁移复用允许searchable=false；4KiB及恶意DTO/isError安全投影。新增非object回查两例先复现AttributeError，增加类型校验后最新Runtime集合112 passed。

### R02 两组合根、模式与审批 · 2026-10-12

通过。两根×query/submit/job×六模式装配边界；两根三access_policy的approve/reject覆盖原HITL；陌生mutation、错误schema和四annotations拒绝。schema/offload/Plan/unbound/deny/子图不提权，写工具未归入WORKSPACE_WRITE_TOOLS。组合根HITL使用fake工具，真实权限和HTTP边界由R01/A02另测，不据其声称RAG入库成功。

### O01 配置、部署与交接 · 2026-10-12

通过。`scripts/tests/test_local_stack_knowledge.py` 5 passed（含旧登记环境缺知识回调从本环境派生）；shell语法通过，doctor通过；本环境API/Runtime API/Worker串行重启且ready。现场GET capability200/not_configured/upload=false，legacy query在catalog、submit不在catalog。真实 `alpha-showcase_demo` Worker＋miaomiaoai deepseek-v4.1-flash＋既有MCP查询1 passed（21.00秒，Run20.139秒），单次query、文本/artifact相同、事实/来源/历史、跨project拒绝与私有binding注入拒绝通过。[安全证据](evidence/deployment-regression.json)已保存；7份fixture、前端话术/运维文档和活规范同步，文档链接/JSON/秘密/状态自检通过。

### V01 平台HTTP集成、安全与相关回归 · 2026-10-12

通过。`test_real_http_grants_upload_receipt_reads_revocation_and_rollback` 启动本Worktree真实平台应用/认证/SQL/HMAC与官方MCP HTTP Adapter，OS分配并保留独立loopback socket，私有tmp库/workspace，受控provider。实际校验upload→queued、原keyreused、job/list/capability、模拟ready/document、当前成员撤权、写关后保留read；fixture原始私密字段被过滤。latest Runtime112 passed，API45 passed/21 subtests，脚本5 passed；Ruff format/check、src compileall、shell和git diff --check通过。未重跑全仓旧失败集合，旧专项已识别基线不得算本轮通过。

### F01–F03 前端交付记录与本轮边界 · 2026-10-12

同事已提交组件与自测记录：vue-tsc无报错、Vitest8项、Playwright3项和6张截图，见tasks的F01–F03条目；本轮只核对脚本，未复跑前端。`apps/platform-web/e2e/knowledge-member-upload.spec.ts`中F01模拟capabilities，F03模拟资料/任务；F02模拟capabilities，仅断言助手消息可见并截图，没有断言实际submit回执/ready。可作界面/会话证据，不能作为V02真实RAG入库闭环。前端源码由同事维护，本轮未修改。

### V02 历史联合验收尝试 · febe70a · 2026-10-12 · 当时 blocked

这是未完成 Task 的尝试记录，不新增已完成 Task，不进入 Final。[安全证据](evidence/rag-recheck.json)保存代码版本、测试结果、实际 HTTP 状态和模型调用摘要。

- **代码与环境：** 平台 Worktree `6394/ai-agent-platform` / `feat/project-knowledge-mcp`；RAG 源码 `/Users/lijiaxin/PyCharmMiscProject/research/rag-anything-use` / `febe70a`。使用各自独立 `.venv`、临时 SQL/知识库和 OS 分配的两个独立 loopback 端口；平台应用、SQL/IAM/Run、RAG HTTP/MCP/supervisor 均为实际源码。没有 Runtime Agent 或浏览器参与该协议 fixture，不作为完整用户链验收。
- **回归通过：** RAG `uv run --frozen --env-file ".env" pytest tests/ -q --tb=short`：67 passed in 32.62s，包含去重、候选/回退和本机持久恢复测试。平台 `uv run --frozen python -m pytest "tests/test_knowledge_member_upload.py" "tests/test_knowledge_authorization.py" -q --tb=short`：17 passed in 10.90s。直接执行 API `pytest` 曾因命名空间 `tests` 不在导入路径而收集失败，改用文档既定的 `python -m pytest` 后通过；临时 fixture 也先按应用入口初始化，避免直接导入授权模块触发既有循环导入。
- **后台授权失败已实测：** 同一平台成员、项目、原 Run 和知识库下，完整字段的 upload/start/activate 对照请求均 200；RAG `operation_identity()` 和 `authorize()` 生成的 start/activate 请求均 403 / `knowledge_upload_denied`，缺 issuer/audience/iat/exp/nonce/graph_id/sha256/size_bytes/file_name/mime_type。真实平台 upload grant → RAG PUT 200 → MCP queued → 实际 supervisor 的 start 被拒 → failed / `knowledge_authorization_denied`，约 0.205 秒；没有任何模型 usage。修复属于 RAG 协议，平台不放宽安全 DTO。
- **失 ACK 回查失败已实测：** 对已持久受理请求，使用有效同项目 Bearer 和平台 upload grant 发起 `GET /internal/knowledge/uploads/{request_id}`，实际 405，`Allow: PUT`；预期为 200 和原请求安全回执。已有 legacy 服务上的无效探测为 404，仅说明 legacy 不注册逻辑库路由；正式判据以上述 online 逻辑库 405 为准。
- **RAG 自身真实模型链通过，但授权为桩：** 运行同事 `scripts/verify_online_knowledge.py`，首轮失败；同一配置仅再跑一次，288.883 秒，六项 checks 全 true：HTTP/MCP 受理、真实 Worker ready、重复 A 无新增入库 usage、新旧来源、回退 searchable、发布文件 checksum 不变。DeepSeek `deepseek-v4.1-flash` + 百炼 `text-embedding-v4` / 1024 维，合成 MD 两份；A 解析 1 / 图抽取 HTTP 3 / Embedding 11，B 解析 1 / 图抽取 HTTP 3 / Embedding 12（含已有图更新 1）。旧文档累积和重复原件零新增入库调用成立；查询模型费另计，不据此承诺整段会话零费用。
- **保留模型失败事实：** 首轮 A failed / `knowledge_processing_failed`，实际图抽取 HTTP 4、Embedding 1，LLM total_tokens=42616；后三次各 reasoning_tokens=8192，等于 max_tokens。配置 `thinking.type=disabled` 仍出现大量 provider 推理 Token。第二轮虽通过，A/B 各有一次 8192 推理 Token 响应并触发重试，说明当前提供方抽取耗时/费用仍有波动；不根据这些统计猜定上游根因。provider cost 缺已核实币种/费率，amount/currency 保持 null。
- **证据归属：** 协议 runner、完整在线结果、首轮失败、第二轮临时语料与日志保留于本 Worktree `.local-stack/evidence/member-knowledge-upload/rag-recheck/`；入 Git 文档仅安全摘要。首轮原脚本会写同事仓库的固定失败证据路径，已先保存本轮失败再恢复该文件原内容；第二轮只重定向测试证据/临时目录，不修改 RAG 源码。RAG 工作区状态与开始一致，仅原有未跟踪百炼文档。临时 HTTP 服务及所属 Worker 已结束，登记栈保持运行，两端上传开关默认关闭。

**当时的后续交付：** 请求RAG同事补两协议并提供commit；已由下述`5be564a`复验关闭，不再作为当前阻塞。推理Token/重试和完整Agent生命周期仍单独验收。

上轮收尾自检：当时7份Markdown、27个专项链接、安全摘要JSON、6完成Task/1 blocked Task与6 Phase/1阻塞尝试对应检查通过，`git diff --check`通过。RAG与`febe70a`一致，原有百炼未跟踪文档保留；临时进程无残留，登记栈ready，未提交/push/生产变更。当时专项blocked；当前状态以本文开头和下述`5be564a`记录为准。

### V02 两项修复复验与 Runtime 实际 Adapter 联调 · 2026-10-12 · partial

**本轮用户请求的修复验证：通过。** V02仍是未完成Task，本节为Phase补充证据，不进入Final。安全摘要见[rag-5be564a-recheck.json](evidence/rag-5be564a-recheck.json)。

- **版本：** RAG本地main和远端main均为`5be564ae5b28d010cf9beb26bc19ef11e7425cdd`，未拉取/切换分支或改同事源码。平台Worktree仍为`6394/ai-agent-platform` / `feat/project-knowledge-mcp`。独立`.venv`、OS分配loopback端口、临时SQL/知识库；登记栈没有重启或配置写入。
- **源码核对：** `operation_auth.py:operation_identity/authorize`保留graph_id/hash/size/name/MIME，每次以RAG issuer和新iat/exp/nonce签请求；旧identity缺字段拒绝。`http_routes.py`注册GET，`upload_service.py:lookup_request`校验有效upload grant，`jobs.py:request_receipt`绑定原主体/来源/文件/scope；新写暂停不阻止回查，不enqueue。
- **回归：** RAG全量78 passed in39.35s；Platform API权限/授权17 passed in11.13s；Runtime上传、实际HTTP协议和两组合根91 passed in43.98s/5既有SWIG warnings。没有重复运行无关全仓回归。
- **实际平台＋RAG＋模型协议：** 同事新`verify_provider_contract.py`直接运行，七检查全true，178.512秒。实际后台start/activate200、两文档ready与MCP新旧来源；篡改/过期/错原主体拒绝；B受理后删除Thread仍ready；RAG项目新写暂停后同keyGET200/原job/reused且usage与attempt不变，错主体/hash/name拒绝。C排队后撤普通executor成员，start拒绝/安全failed且模型调用零；撤权start/activate拒绝；A发布快照checksum不变。使用DeepSeek `deepseek-v4.1-flash`与百炼`text-embedding-v4`1024维，没有授权桩。
- **Runtime实际Adapter链：** 复用现有`config()/thread_resource_metadata/DocumentWorkspace/AttachmentReceipts/load_mcp_tools`，同一实际平台和RAG的独立服务；可信ToolRuntime fixture代表原executor，SQL保存实际原Run。官方Adapter原字节上传→queued→真实后台ready；Runtime job工具读取ready；模拟实际MCP已受理后本地传输失ACK，Runtime真正GET回查同job/reused。ready后两个不同tool_call_id并发同hash请求都复用原job，全库jobs仍1、usage仍21（是计数，不等于Token或金额）；另一editor使用实际平台认证GET读发布资料/ready任务。安全回执无Bearer/HMAC/upload_id/签名，七检查全true，141.466秒。
- **补测失败事实：** 自写probe第一轮误断言attempt=0，实际首次受理为1；仅修改忽略目录内probe断言，此轮无模型调用。第二轮已queued/GET恢复，但实际后台构建failed；当时runner未采集job error_code/构建日志，临时环境自动回收，故根因无法确认，失败JSON保留。增加安全诊断后第三轮141.466秒通过；过程中只读usage观察到一个unknown图抽取事件，不能据成功归因或宣称provider稳定。上述失败不是新发现的403/405协议回归。
- **边界：** 两协议通过、Runtime Adapter可信附件链通过；仍没有真正Agent Worker/浏览器、另一成员通过Agent检索、跨Run且处理中的并发去重、目标online Stop/重启/候选失败/CAS/回退、大文件/负载验收。外部费用无exactly-once保证，币种/费率未核实，不估算金额。新旧查询本轮在RAG MCP直接完成，另一editor本轮验证的是平台资料/任务GET。
- **资源与留痕：** 两组fixture自行回收HTTP/Worker/SQL/临时corpus；完整报告、两份probe及失败摘要留在`.local-stack/evidence/member-knowledge-upload/rag-5be564a/`，入Git仅安全摘要。本轮只更新平台验收文档/证据；RAG仍仅原有未跟踪`docs/projects/20261012-bailian-embedding/`。登记七服务running、API/Runtime ready，上传默认关闭，未提交/push/生产部署。专项状态改为partial，旧两项外部阻塞解除，不触发标准毕业。
- **收尾自检：** 六份本轮Markdown的34个链接有效，专项全部JSON可解析；7个完成Task（含前端合并交付）/1个未完成V02与Phase/状态一致；登记上传开关关闭，命名probe进程及临时corpus无残留，RAG工作区保持，`git diff --check`通过。经验提案：验收失败先保存安全job错误/构建日志摘要再清理fixture，避免无法归因；未经用户确认不写入`docs/lessons/`。

## 可复验命令与证据

下面命令以所属app或Worktree根执行，真实模型只跑一条旧查询回归，不自动启动共享服务或在线写。

Runtime app：

```bash
uv run --frozen pytest "tests/tools/test_knowledge_upload.py" "tests/tools/test_knowledge_upload_http.py" "tests/tools/test_knowledge_http_contract.py" "tests/tools/test_knowledge_result.py" "tests/services/test_knowledge_composition.py" "tests/services/test_mcp_probe.py" "tests/test_thread_workspace_isolation.py" "tests/workspace/test_office_http.py" "tests/test_workspace_http.py" "tests/services/showcase_demo/test_documents.py" -q --tb=short
KNOWLEDGE_PLATFORM_LIVE=1 uv run --frozen pytest "tests/e2e/test_knowledge_platform.py::test_project_knowledge_real_worker[alpha-showcase_demo]" -q -s --tb=short
```

最新结果112 passed/5既有SWIG弃用warnings（73.10秒）；真实模型1 passed（21.00秒）。fixture重生成命令见[fixtures说明](fixtures/README.md)。

`5be564a`本轮最小回归，Runtime app执行（91 passed in43.98s）：

```bash
uv run --frozen pytest "tests/tools/test_knowledge_upload.py" "tests/tools/test_knowledge_upload_http.py" "tests/services/test_knowledge_composition.py" -q --tb=short
```

API app：

```bash
uv run --frozen python -m pytest "tests/test_knowledge_member_upload.py" "tests/test_knowledge_authorization.py" "tests/test_knowledge_mcp_bindings.py" "tests/test_audit_http_resolution.py" "tests/test_iam_policy_engine.py" "tests/test_runtime_gateway_workspace.py" -q --tb=short
```

45 passed/21 subtests passed/2既有websocket弃用warnings（53.19秒）。

`5be564a`本轮API最小回归17 passed in11.13s：

```bash
uv run --frozen python -m pytest "tests/test_knowledge_member_upload.py" "tests/test_knowledge_authorization.py" -q --tb=short
```

RAG仓库本轮命令：

```bash
uv run --frozen --env-file ".env" pytest "tests/" -q --tb=short
uv run --frozen --env-file ".env" python "scripts/verify_provider_contract.py" --platform-root "/Users/lijiaxin/.codex/worktrees/6394/ai-agent-platform" --output "/Users/lijiaxin/.codex/worktrees/6394/ai-agent-platform/.local-stack/evidence/member-knowledge-upload/rag-5be564a/provider-real.json"
```

Runtime补测probe留在上述忽略证据目录，命令/输入路径及边界写在脚本中；平台/RAG各自独立Python运行，不复制密钥到文档。它们只用于本次验收，不作为新业务服务或平台第二队列。

Worktree根：

```bash
"./apps/platform-api/.venv/bin/python" -m unittest "scripts/tests/test_local_stack_knowledge.py"
"./apps/platform-api/.venv/bin/ruff" check <本轮变更Python文件>
"./apps/platform-api/.venv/bin/ruff" format --check <本轮变更Python文件>
"./apps/platform-api/.venv/bin/python" -m compileall -q "apps/platform-api/src/platform_api"
"./apps/runtime-service/.venv/bin/python" -m compileall -q "apps/runtime-service/src/runtime_service"
bash -n "scripts/local-stack.sh"
git diff --check
```

Ruff来自同一Worktree API独立安装，Runtime不借其他Worktree依赖；本轮实际format --check/check全部33个变更Python文件通过。未新增/升级依赖，无本轮数据库迁移。文档自检检查334个链接、8个JSON及7份fixture的实际Pydantic DTO，六completed Task/六Phase/一blocked Task一致，当前私有配置secret扫描通过。FEATURES中4个断链在HEAD原文已存在，本轮新链接无断链，未扩大范围修旧路径：

- `apps/platform-web/docs/changes/20260923-fix-zombie-clarification-on-thread-switch.md`
- `quickstart/deployment-guide.md`
- `quickstart/operator-handoff.md`
- `apps/platform-web/docs/changes/20261007-prompt-queue-unconfirmed-deadlock-and-switch-healing.md`

现场原始安全日志/Run证据位于本环境 `.local-stack/evidence/knowledge/alpha-showcase_demo/` 与 `.local-stack/evidence/member-knowledge-upload/deployment-disabled.json`；入Git仅[安全摘要](evidence/deployment-regression.json)，不含Bearer/HMAC/private配置或模型凭据。

## 问题与外部阻塞

已修复：失ACK旧grant可能已过期，恢复前重新授权；非object恢复正文原会抛AttributeError，增加object边界检查；迁移null job的searchable不强制true，保留回退事实。既有local-stack restart-one会回收同目录pytest/HTTPfixture，本轮API测试曾exit143，改成启停/测试串行后完整重跑通过，未把它当业务测试失败，也未扩大范围改进程管理。

2026-10-12历史V02 partial：原两项协议缺口由`5be564a`关闭，[当时证据](evidence/rag-5be564a-recheck.json)实测后台ready和同keyGET恢复。完整冻结快照候选增量不变，不另建平台缓存/队列。一次Runtime补测实际构建失败根因未采集，成功轮仍观察到unknown图抽取事件；历史高推理Token/重试保留，模型稳定性不能据78项单测或单次成功判定。

2026-10-12当时未验实际Agent、处理中去重及生命周期，不能用该轮Adapter结果冒充。2026-10-13已由[承接专项](../20261013-knowledge-documents-platform/verification.md)完成实际Worker普通成员上传、另一成员累积检索、跨Run处理中/ready同hash零新增用量、20MiB异步Stop、两项目排队/旧读、Fork/API/Worker/RAG重启与冻结回退/恢复；RAG119项含候选失败/CAS/受控恢复。仍未验前端无mock浏览器、生产容量和业务题集，最长30秒跨库授权租约不变。

## Final 验证记录

本专项2026-10-12未执行Final，保留上方Phase及历史失败。2026-10-13承接专项完成非前端统一回归与真实联合验收，最终结果以[新Final](../20261013-knowledge-documents-platform/verification.md#final-验证记录)为准，不重复计数或覆盖原历史。前端与正式部署独立接续。
