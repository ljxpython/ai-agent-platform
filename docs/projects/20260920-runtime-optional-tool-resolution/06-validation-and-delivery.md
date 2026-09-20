# 06 — 验证矩阵、阶段交付与完成度

## 目标

证明 Runtime 真正拥有工具决策、Catalog 已退出执行链，并覆盖所有旧字段消费、数据转换和安全负向路径。

## 方案设计

### 阶段与交付

| 阶段 | 交付物 | 进入下一阶段条件 | 粗估人天 |
|---|---|---|---|
| G0 实施准备 | 批准记录、代码/数据库 head 核对 | 方案已批准，无旧业务迁移前置 | 0.5 |
| G1 Runtime 契约 | 声明/签名限制执行、auth/resolver/middleware、Agent 与 HTTP 路径 | 单元和执行安全集成通过 | 3–5 |
| G2 Platform 治理 | 新 restriction 管理/求值/签发、无目录执行依赖、旧策略退役与新表初始化 | API/IAM/schema 测试通过 | 2.5–4.5 |
| G3 Web 收口 | 只读 Catalog、管理员禁用例外面板、删除普通工具选择、错误交互 | 类型/组件与浏览器测试通过 | 2–3 |
| G4 联合演练 | 完整 E2E、新版恢复、schema 与切换证据 | 所有关键链路验收；部署窗口另行批准 | 2–3 |

合计初估 10–16 人天，不含生产切换；旧业务数据转换和兼容恢复已取消，不是已承诺工期。G1/G2 必须成套发布，阶段划分不意味着线上可以混用契约。

### 验证矩阵

| 编号 | 场景 | 关键预期/证据 |
|---|---|---|
| V01 | 默认无禁用 | 仅 Agent 已声明且环境可用工具进入模型，Catalog 空/旧/异常都不改变结果 |
| V02 | 单用户/项目工具 false | 不进模型 schema；伪造调用 handler 执行计数为零 |
| V03 | required 被禁用 | 初始化失败；optional 被禁用只移除；全 optional 空时普通对话成功 |
| V04 | true、0、null、字符串、未知工具/graph 规则 | 严格配置拒绝，不静默当允许；空规则明确合法 |
| V05 | 身份/作用域 | 多角色、跨 tenant/project/thread、Agent 名伪造、只读 scope 执行均按规则拒绝 |
| V06 | 子 Agent/MCP/internal | 子 Agent 不绕过主体禁用；禁用 MCP 不连接；内部名称不覆盖 false |
| V07 | 模型输出/直接执行 | 模型幻觉被禁工具调用、旧待执行工具调用都在副作用前拦截 |
| V08 | Skills/Memory/Workspace | delete_skill false 的工具与 HTTP 删除都拒绝；read/write/owner 校验保持 |
| V09 | Terminal | execute false 不能新建或写入终端；跨线程拒绝；发布清理旧进程有证据 |
| V10 | 人工审批/模式 | approve/full_access 不覆盖禁用；环境关闭不能被恢复为可用；新运行恢复/HITL 正常 |
| V11 | 新 token/Context/snapshot | 缺版本/旧字段/坏签名/过期/错误 hash 拒绝；新契约确定性、无秘密字段 |
| V12 | Gateway/Catalog 脱钩 | Mock 工具目录查询为失败陷阱，正常签发/Run 通过；模型禁用仍拒绝 |
| V13 | Catalog 刷新 | 坏响应保留旧快照；合法空只改变展示；新增工具无需刷新即可由 Runtime 使用 |
| V14 | 前端 | Agent CRUD/Chat 不传工具授权，工具页无策略 PUT；目录空不阻断聊天 |
| V15 | 直接退役 | 新 restriction 表为空；旧策略/工具选择不转换；无业务迁移脚本或兼容 Agent，schema 更新可执行 |
| V16 | 队列/Worker | 旧 pending 不执行，旧 token 拒绝，新旧 Worker 不混跑；不要求旧历史/审批可恢复 |
| V17 | 新版恢复/切换失败 | 新版会话与审批恢复正常；切换失败停止入口/Worker，修复重试，不恢复旧业务语义 |
| V18 | 执行替代路径 | 明确 execute/MCP 可达能力；业务级禁止由存储/沙箱把关，不把工具名禁用当资源安全 |
| V19 | 平台权限管理 | 非管理员不能写；项目与用户拒绝并集；跨项目删除拒绝；目录缺失不影响已有规则求值 |
| V20 | 求值失败/在线更新 | DB 异常不签空对象；新 Run/恢复使用新版本；活跃 Run 不冒充实时撤销，紧急取消有演练 |

### 测试落点

Runtime 现有：

- `apps/runtime-service/tests/runtime/test_auth.py`、`test_platform_auth.py`、`test_contracts_and_resolver.py`。
- `apps/runtime-service/tests/middlewares/test_runtime_middleware.py`。
- `apps/runtime-service/tests/test_terminal_http.py`、`tests/services/dearflow_agent/`、`tests/services/test_r4_capability_demos.py`。
- `apps/runtime-service/tests/integration/test_agent_server_auth.py` 与 `tests/durable/`（local_auth.py 及消费方一并升级）。
- 新增 `tests/runtime/test_tool_governance.py`，验证签名限制执行与非法 claim；已有 HTTP 测试中加入同动作拒绝用例。

Platform 现有：

- `apps/platform-api/tests/test_runtime_catalog_delegation.py`、`test_runtime_gateway_runtime_contract.py`、`test_runtime_gateway_http_matrix.py`。
- `apps/platform-api/tests/test_runtime_gateway_skills.py`、`test_runtime_gateway_workspace.py`、`test_agent_single_table.py`、IAM 测试。
- 在既有数据库测试中验证新表初始化与旧工具表退役；不新增旧 false/Agent tools 转换测试。
- 新增 `tests/test_tool_restrictions.py`：规则管理权限、主体校验、拒绝并集、查询失败、签名版本和同名 graph 隔离。

Web：

- `apps/platform-web/src/services/agents/context.spec.ts`、`agents.service.spec.ts`、`services/runtime/runtime-contract.spec.ts`。
- 修改页面的只读目录/无选择提交测试及两种 Chat 会话测试。
- 浏览器：普通聊天、Dear Agent、Skills/Terminal 禁用提示、审批、Agent 编辑与目录空态。

上述短文件名均相对同段给出的目录；后端和 Runtime 新增测试已落地，Web 测试由前端接入阶段执行。

### 全链路演练

在隔离项目使用两个用户：一个无例外，一个 delete_skill/execute 为 false。经 Web → Platform → Runtime 发起同一个 Agent 对话，捕获模型实际 schema 和工具 handler 调用；同时从直接 HTTP 尝试相同动作。将 Catalog 置为空，再重复，结果必须一致。再验证 required 禁用、模型禁用、错误 scope、审批恢复、MCP/子 Agent 绕过尝试。

工具授权使用确定性假模型/工具做自动化；真实模型只做连通与实际对话烟测，不能用“LLM 本次没调用”作为权限拦截证据。破坏性动作只对测试资源执行。

### 质量、性能、文档

- 使用各服务已有 pytest、lint、类型检查与 Web 现有测试命令；实施时核对 pyproject/package scripts，不新增测试框架。
- Runtime 集合求值无网络/数据库 I/O；Platform 签发读取禁用规则表，通过线程池避免阻塞异步入口，不读取工具 Catalog。未执行独立负载测试。
- 记录静态声明导入无副作用；故障日志含安全关联标识、规则/声明版本，不含 token、凭据、全量用户规则。
- 更新根 FEATURES、app runtime/gateway 标准、Runtime knowledge 14/19、前端契约及脚本使用说明。旧方案被取代才归档，当前设计不按阶段完成归档。
- 每阶段调用 implement-feature 留 implementation，最终 verify-change 按 done/partial/blocked/deferred 如实记录。

## 任务拆分

- [x] G0：用户批准方案，取消旧项目维护和兼容迁移；已核对 schema revision。
- [x] G1：Runtime 契约、工具执行及 HTTP 拦截实现与定向验证。
- [x] G2：Platform 禁用管理、求值、签发、审计与 schema 测试。
- [ ] G3：前端由用户接手，deferred；见 [前端交接](frontend-handoff.md)。
- [x] G4 本轮证据整理：后端链路、安全契约、本地新版恢复及剩余范围。
- [ ] G4 联合发布：浏览器完整 E2E、旧 Worker 清退、切换失败停止/重试、紧急撤销演练，deferred 至联合发布阶段。

## 验证要求与记录

2026-09-20，执行人：Codex。本地开发环境及隔离测试资源；未部署生产、未迁移已有业务数据库。以下计数存在重复覆盖，不累加为独立用例总数。

### Platform API

工作目录 `apps/platform-api`；命令前缀 `.venv/bin/python -m unittest discover -s tests`。

| 参数 | 实际结果 | 证据 |
|---|---|---|
| `-q` | 204 ran，OK，7 skipped；阶段性全量，后续改动定向复验 | `/tmp/tool-platform-tests.log` |
| `-p 'test_runtime_gateway*.py' -q` | 51 ran，OK，1 skipped；含两个真实 HTTP 服务 Workspace 联调 | `/tmp/tool-gateway-final.log` |
| `-p test_tool_restrictions.py -q` | 4 passed | `/tmp/tool-restrictions-final.log` |
| `-p test_runtime_catalog_delegation.py -q` | 13 passed | `/tmp/tool-catalog-final.log` |
| `-p test_runtime_delegation.py -q` | 13 passed | 测试执行输出 |
| `-p test_runtime_gateway_runtime_contract.py -q` | 17 passed | `/tmp/tool-gateway-contract-final.log` |
| `-p test_audit_http_resolution.py -q` | 8 passed | 测试执行输出 |

规则 CRUD/IAM、项目与用户拒绝并集、服务账号项目规则、异常不回退空权限、旧接口退出、客户端伪造字段、Catalog 坏快照/合法空、审计 target/metadata 均有测试。迁移与 ORM 一致性使用临时 SQLite，未对已有业务库执行 migration。

### Runtime

工作目录 `apps/runtime-service`；命令前缀 `.venv/bin/python -m pytest`，参数 `-q --tb=short`。

| 测试范围 | 实际结果 | 证据 |
|---|---|---|
| `tests/services tests/runtime tests/middlewares/test_runtime_middleware.py tests/test_terminal_http.py tests/test_image_http.py tests/test_workspace_zip.py tests/test_thread_workspace_isolation.py` | PostgreSQL 连接等待处主动中断；已执行 192 passed、27 skipped，不能视作全量通过 | `/tmp/tool-runtime-tests2.log` |
| 下列续跑集合 | 103 passed、1 skipped | `/tmp/tool-runtime-remaining.log` |
| `tests/services/test_schema_introspection.py tests/services/test_workspace_policy.py tests/services/workflow_demo/test_agent.py` | 22 passed，补齐中断后模块 | `/tmp/tool-runtime-extra.log` |
| `tests/runtime tests/middlewares/test_runtime_middleware.py tests/test_terminal_http.py` | 当时 78 passed、2 failed；修复情况见下 | `/tmp/tool-contract-final.log` |
| `tests/runtime/test_auth.py` 最终复验 | 14 passed | `/tmp/tool-auth-final.log` |
| `tests/runtime/test_tool_governance.py` | 12 passed；随后两项加强断言/配置校验分别复验通过 | `/tmp/tool-security-final.log` |
| `tests/runtime/test_tool_governance.py::test_signed_denials_block_direct_http_before_side_effects` | 1 passed；明确验证 runtime.tool.not_allowed，排除 scope 拒绝假阳性 | 测试执行输出 |
| `tests/runtime/test_tool_governance.py::test_mcp_declarations_reject_malformed_names_and_shapes` | 1 passed | `/tmp/tool-mcp-final.log` |
| `tests/services/dearflow_agent/test_agent.py::test_new_signed_denial_blocks_pending_approval_after_rebuild` | 1 passed；真实 Graph 重建后审批仍拒绝，无文件副作用 | 测试执行输出 |

续跑使用 `PGCONNECT_TIMEOUT=3` 和 `-o faulthandler_timeout=45`，集合：

```text
tests/services/test_message_inbox_postgres.py
tests/services/test_r4_capability_demos.py
tests/services/test_resource_reconnect.py
tests/services/test_workspace_demo.py
tests/runtime/test_auth.py
tests/test_terminal_http.py
tests/test_image_http.py
tests/test_workspace_zip.py
tests/test_thread_workspace_isolation.py
```

PostgreSQL 临时 schema 上消息恢复/崩溃测试实际执行；两次 45 秒栈转储来自 Worker 冷启动等待，最终通过。待审批撤销使用 InMemorySaver 重建 Graph，不能替代集群发布验证。

曾失败的两项分别是测试负例误用合法 read operation、expected_scope 比对遗漏 operation。已修正负例并补齐 operation 校验，最终 auth 14 项通过。其他安全证据覆盖 Platform 实际签名 → Runtime 验签 → schema/模型幻觉输出/handler/HTTP 拒绝、required/optional、配置 hash 与 MCP 禁用不连接。

### 质量与边界

最终 86 个修改/新增 Python 文件 AST 解析及 Ruff `F,E9` 检查通过；`git diff --check` 通过，专项非 archive 文档的 20 个相对链接有效，前端代码 diff 为空。Ruff 通过 `uv tool run ruff check --select F,E9` 执行（服务虚拟环境无 Ruff 可执行文件）。该检查不等于完整静态类型检查。未执行独立负载测试；未把真实模型/环境开关导致的 skip 算作通过。日志路径是本机临时证据，复验以仓库测试与上述命令为准。

### 完成度判定

| 范围 | 状态 | 说明 |
|---|---|---|
| 后端与 Runtime 本轮开发；V01–V13、V18–V20 的契约/执行部分 | done | 单元、签名跨服务契约、真实 HTTP 联调及安全负向证据齐备 |
| V15 schema 和旧接口退出 | done | 隔离库验证；业务库执行属于发布步骤 |
| V10/V17 本地新版 Graph 审批恢复 | done | 重建后使用新禁用规则，审批不绕过 |
| 环境特有/真实模型全量覆盖 | partial | 有 skipped，不宣称真实模型及所有部署链路通过 |
| V14 前端与浏览器全链路 | deferred | 用户明确接手前端开发，接入后验收 |
| V09/V16/V17/V20 发布部分 | deferred | 旧进程/Worker 清退、单版本切换、发布失败停止重试、紧急撤销演练留到联合发布 |
| 集群持久化/重启/重放的新契约验证 | blocked | 未提供本次联合部署版本及运行环境；本地恢复不能代替集群证据 |
| 旧项目迁移、兼容与旧业务恢复 | 不适用 | 用户明确取消，不实施 |

终端关闭保留 scope/owner 校验，但允许作为清理操作；禁用 execute 不自动终止已活跃进程。紧急撤销需要显式取消运行/关闭终端，不能宣称实时撤销。

## 状态

本轮后端与 Runtime 开发及约定的本地验证 done。整个专项 partial：前端由用户接入，联合发布与集群验证待后续阶段。方案已由用户批准实施，不自行宣称生产验收完成。
