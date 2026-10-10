# Worktree 本地联调资源隔离 - 验证

## 验证计划

- 单元：端口随机/排除占用/持久复用、登记写入并发、缺配置拒绝、生成地址及密钥隔离、销毁确认和资源名校验。
- 集成：真实独立 Redis、数据库角色/归属、进程归属及停止边界；现有启动脚本测试回归。
- 端到端：三个隔离环境并行运行，Web -> API -> Runtime 最短链路；停止一个环境后另外两个仍可用；同一配置重启后数据仍存在。
- 安全：登记不含秘密、不回退主环境、doctor 不杀进程、外部占用者保留、跨目录依赖拒绝、销毁显式确认且不强制断开连接。
- 配置与数据复用：继承各 app 配置并覆盖隔离字段、默认账号、只读白名单复制、模型凭据重加密、源历史排除、事务回滚与幂等重试。
- 回滚：停止新增环境后主工作区配置和数据保留。
- 性能：验证三环境并发登记与启动，无额外吞吐 SLO；真实模型额度共享不做调度。

## Phase 验证记录

### T01 - 2026-10-10

- `apps/runtime-service/.venv/bin/python -m unittest discover -s scripts -p test_local_stack_worktree.py -v`：7 项基础测试通过。
- `LOCAL_STACK_INTEGRATION=1 apps/runtime-service/.venv/bin/python -m unittest discover -s scripts -p test_local_stack_worktree.py -v`：8 项通过，包含三环境真实 PG/Redis，非 mock。
- 覆盖六进程同时登记（24 个唯一端口）、配置/资源归属拒绝、私有配置 600、特殊字符往返、独立安装目录要求和安全失败回收。
- 真实检查覆盖三套专属 Redis 的同名键/队列、六个专属数据库/角色、非超级用户权限、停止一套不影响其他两套、重新初始化保留身份和数据。测试临时 PG/Redis 资源已回收。
- `bash -n scripts/local-stack.sh` 通过；完整现有脚本回归 14 项通过（单独未启用的集成测试 1 项 skip 已在上面的显式集成执行中通过，skip 不计为 pass）。

### T02 - 2026-10-10

- 完整 `test_local_stack*.py` 回归此前 16 项通过，无 skip；覆盖真实多目录进程归属、手动启动/顽固子进程清理、doctor 不杀占用者及失败仅清理本次新进程。
- 三套临时目录通过正式 `init/deps/doctor/start/status/stop/destroy`，两个 Python 服务实际导入所属目录源码，uv/pnpm 使用 frozen 锁文件及共享缓存。
- 实际验证重复 start 幂等、停止第一套后另外两套可用、第一套重启保持身份/端口/凭据/项目；测试资源全部显式销毁。追加 Worker/浏览器验证记录在 T04。
- 新增父目录/状态目录越界与管理员连接不下发检查：首次 18 项回归中 17 项通过，1 项因验收命令引号失败；修正测试命令后该项复测通过。没有将失败或 skip 计作 pass。
- Shell 语法、项目 Ruff 配置下检查与格式验证通过。未安装全局工具；本机没有 shellcheck，以 `bash -n` 及真实执行覆盖脚本。
- 补充后的完整回归 18 项通过，无 skip；包含管理员 DSN/操作锁不传给子进程、安装目录父级和私有状态文件的跨目录软链接拒绝。

### T03 - 2026-10-10

- `vue-tsc --noEmit`、两个改动文件独立 `tsc --noEmit`、ESLint 与 Prettier 检查通过。
- `test_playwright_worktree_configuration_fails_closed` 真实加载 Playwright 配置：缺初始化、Web/API 地址跨环境、环境 ID 篡改、三种旧固定 `/tmp` fixture 模式均拒绝；正确登记可成功列出测试。该测试只加载配置，其安装目录链接是只读夹具，实际三栈依赖均独立安装。
- 主目录和三个临时环境的 Playwright `--list` 通过；主目录与既有 Codex Worktree 的 `git_paths()` 只读核对通过，未创建/操作用户分支或 Worktree。
- 本次 15 份 Markdown 的 `check_file()` 检查通过，规范/AGENTS/README/指南/部署契约导航与命令已核对。
- 全仓 `scripts/check_docs.py` 失败：8 份其他旧文档共 37 条 macOS 绝对路径。逐文件与 `git show HEAD:<path>` 比较，既有计数均相同，不属于本次修改；没有将全仓检查计为通过。
- 测试夹具初次因包元数据/模块模式缺失被 pnpm 误判，修正为当前真实 `package.json`，使用现有 Playwright Node CLI 只加载配置后通过；未删除或重装用户依赖。

### T04 - 2026-10-10

- `apps/runtime-service/.venv/bin/python scripts/verify_worktree_local_stack.py --output docs/projects/20261010-worktree-local-stack/evidence/native-three-stacks.json` 完整执行通过，证据 [native-three-stacks.json](evidence/native-three-stacks.json)。三个临时目录名称含空格，走正式脚本入口。
- 三套各自安装当前源码依赖、迁移两个专属数据库、启动独立 Redis/API/Worker/Web。Web 代理登录、创建项目、精确委托访问 Runtime catalog 成功，临时 catalog 包含四个业务 graph 和一个确定性探针。
- 三个真实 Worker 并发执行写入/读取，返回各自环境 ID；同名 `isolation.txt` 仅在各自 Workspace，内容符合所属 ID。三个独立 Chromium 上下文真实登录成功，检查 Web/API 登记地址及浏览器 API 请求 origin。
- 重复 `start` 幂等；第一套 `stop` 后其余两套仍完成真实 Worker 读取；第一套重启保持身份、端口、凭据、项目、Thread 和 Workspace 文件，继续执行任务成功。
- 全部临时进程由正式 `stop` 关闭、专属资源通过精确环境 ID `destroy` 清理；未启动/停止用户主工作区或既有 Codex Worktree。
- Git 位置查询为 fixture，其余安装、数据库、Redis、HTTP、Worker 和浏览器均为真实运行；实际 Git 主目录及既有 Worktree 检测另有只读证据，不将 fixture 宣称为真实 Git Worktree 生命周期。
- 追加验收的前两轮分别因未对齐项目 Agent、`workspace_demo` 缺少专用资源绑定失败，资源均已回收。改用临时最小 LangGraph 探针、复用现有 Agent 对齐入口后，上述完整链路通过；业务 graph/鉴权未改动。

### T05 - 2026-10-10

- `test_local_stack_worktree.py`：11 项通过，另 1 项 PG/Redis 集成因未启用开关跳过，不计通过，待 T07 全量开启执行。
- 覆盖主 Runtime/API 配置继承、默认 admin/admin123、Web .env/.env.local 优先与地址重写、特殊字符/重复 init/配置文件 600，以及原源码/软链接/端口边界。
- 配置继承单测补验通过：新环境清空主配置的历史 JWT verification keys，并保持 access/refresh 密钥独立。
- Ruff check/format 和 Shell 语法通过。Runtime venv 没有 Ruff 命令，使用隔离 `uvx ruff`，没有全局安装或改变项目依赖。

### T06 - 2026-10-10

- `LOCAL_STACK_INTEGRATION=1 apps/runtime-service/.venv/bin/python -m unittest discover -s scripts -p test_local_stack_seed.py -v`：最初 4 项真实 PostgreSQL 测试全部通过；追加第 5 项后的完整回归与收尾重跑 5 项均通过，无 skip。
- 验证复制 ID/外键/自定义 Skill、模型密文重新加密且可解密、目录地址重映射、目标默认密码与源密码/密文保持原状；历史/cron 不复制。
- 重复导入保持 Worktree 自己的模型名称/管理员密码；非空旧环境自动启动保留、显式导入拒绝；错误解密密钥或列结构差异回滚全部目标数据，修复后可重试。
- 追加第 5 项真实 PG 测试覆盖两库部分失败后的安全重试、已完成库不再依赖主配置、源库没有 admin 时仅补建目标本地管理员；5 项均在 T07 完整回归中通过。补验非空/归属检查时同时验证 URI query 的远端 host/hostaddr/service 覆盖被拒绝。
- 前两轮测试分别因夹具遗漏租户 slug/策略列名，以及连接关闭后 PG 活动状态短暂延迟导致失败；已修正夹具并等待测试连接退出后清理，精确回收一次失败留下的临时库/角色。没有操作主环境数据。

### T07 - 2026-10-10

- `LOCAL_STACK_INTEGRATION=1 apps/runtime-service/.venv/bin/python -m unittest discover -s scripts -p "test_local_stack*.py" -v`：24 项全部通过，无 skip，包含 5 项基础数据真实 PG 测试及原 PG/Redis/启停回归。后续连接覆盖与 JWT verification keys 调整的直接相关测试补验通过。
- `apps/runtime-service/.venv/bin/python scripts/verify_worktree_local_stack.py --output docs/projects/20261010-worktree-local-stack/evidence/native-three-stacks-baseline.json` 完整执行退出 0，证据 [native-three-stacks-baseline.json](evidence/native-three-stacks-baseline.json) 为 `passed`。
- 三套环境各从实际主库复制 1,208 条 Platform 基础数据和 10 条 Runtime 配置（本次源快照计数），默认管理员登录、模型新密钥解密、源历史排除、Web/API/Runtime catalog 和三个 Chromium 登录通过。真实 Worker/Workspace、重复 start、停一套不影响另外两套、重启数据保留继续通过。
- 第一轮追加三栈验收因要求目标 audit_logs 绝对为空失败：服务启动会生成新的审计。已修正为核对目标审计 ID 不来自主库，其余历史表仍检查首次链路前为空；资源回收后完整重跑通过，未将失败记为通过。
- 全部临时环境经正式 stop/destroy 精确回收；独立核对 12 个端口释放、6 个专属库/角色不存在、验收进程与临时目录不存在，当前仓库公共登记为空。没有启停用户现有环境。
- 16 份本次 Markdown 的 `check_file()`、新增导航/相对链接、YAML 契约和七任务/七 Phase 状态一致性检查通过；FEATURES 另有 4 条既有失效链接与 HEAD 一致，未修改。全仓文档检查仍为 8 份旧文档的 37 条 macOS 绝对路径，按用户要求后置。
- 收尾按仓库根配置清理新增 PG 测试的未使用变量和冗余 noqa，5 项真实 PG 重跑通过；6 个新增/相关测试脚本的 Ruff check、5 个新增脚本的 format check、Shell 语法及 `git diff --check` 通过。扩展检查另发现两个既有脚本共 6 条 Ruff 诊断，逐项与 HEAD 比较一致，未修改。没有新前端源码改动，沿用 T03 的类型/lint 证据与本次真实浏览器回归。

## Final 验证记录

### 2026-10-10 Final（原 T01-T04 范围）

- **执行人：** 本次 Codex 会话，按用户已批准范围执行。
- **完成度：** `done`。T01-T04 全部完成，四条 Phase 记录齐全，README/plan/tasks/CONTEXT/FEATURES 与规范状态一致。
- **完整脚本回归：** `LOCAL_STACK_INTEGRATION=1 apps/runtime-service/.venv/bin/python -m unittest discover -s scripts -p "test_local_stack*.py" -v`，19 项全部通过，无 skip；包含真实 PG/Redis 和真实进程停止边界。
- **端到端：** 本轮三栈真实验收完整通过，使用上述最新 [JSON 证据](evidence/native-three-stacks.json)，不重复启动已经验证的三栈。真实 Worker/Workspace、三个 Chromium 登录、Web/API/Runtime、重复启动、停止及重启持久化齐全。
- **静态与契约：** Shell 语法、Ruff check/format、TS/vue-tsc、ESLint/Prettier、YAML v3 解析与端口策略核对、`git diff --check` 均通过。15 份本次 Markdown 通过文档检查及导航/四任务状态一致性校验。
- **安全与资源回收：** 登记不存秘密，配置权限 600，跨目录/软链接/地址漂移拒绝，管理员 DSN 和操作锁标记不下发后台应用；销毁确认、活跃连接及归属拒绝有实际测试。验收 12 个端口全部释放，无验收服务遗留，本机不存在 `wt_<12hex>_{platform,runtime}` 库/角色，当前仓库公共登记为空。
- **回滚：** 停止保留分配/凭据/项目/Thread/Redis/Workspace，真实重启恢复成功；主工作区原私有配置及数据未覆盖，未启停用户既有环境。没有 Git 提交/推送、分支创建或生产部署。
- **性能范围：** 六进程同时分配 24 个不同端口和三栈并发执行通过；本次无吞吐 SLO，不对 CPU/内存/模型配额作容量保证。
- **已知范围外问题：** 全仓文档检查仍失败，8 份旧文档中的 37 条绝对路径与 HEAD 一致；本机无 shellcheck。旧共享 `/tmp` E2E 专项在 Worktree 中明确拒绝，后续需迁移 runner；不宣称这些旧专项已支持并发。
- **未验边界：** 未调用真实外部模型，未验证生产部署或机器容量调度。三栈使用 Git 位置 fixture，真实 Git 检测仅只读核对主目录和既有 Worktree；未创建/删除用户 Worktree。

结论：用户已批准的本地 Worktree 资源隔离范围完成，`worktree-development.md` 已毕业为 `active`，`last_verified` 为 2026-10-10。

### 2026-10-10 Final（追加配置与基础数据复用，T01-T07）

- **执行人及范围：** 本次 Codex 会话；用户已批准的本地隔离和追加默认账号、app 配置继承、主库基础数据复用。
- **前置状态检查：** README/plan 为 done，tasks 七项全部完成，七条 Phase 与 CONTEXT/FEATURES 一致，规范保持 active、last_verified 2026-10-10。
- **完成度：** `done`。24 项完整 local-stack 回归无 skip；连接 URI 覆盖/JWT 历史验证密钥定向补验通过，收尾测试代码整理后 5 项真实 PG 再次通过。
- **配置与数据：** 三套真实环境各复制 1,208 条 Platform 和 10 条 Runtime 基础配置，模型 Key 使用目标新密钥解密成功，admin/admin123 实际登录通过。关系/主密码和密文不变、源历史排除、非空拒绝、失败回滚、幂等及部分失败重试均有实际证据；不把本次快照计数视为固定产品数据量。
- **端到端及回滚：** 最新 [native-three-stacks-baseline.json](evidence/native-three-stacks-baseline.json) 为 passed。真实 Web/API/Runtime、三个 Worker/Workspace 和独立 Chromium 登录、重复 start、停一套不影响其余两套、重启保持本环境数据均通过。Git 查询仍为 fixture，实际主目录/已有 Worktree 检测沿用 T03 只读证据。
- **安全及资源回收：** 源只读事务、专属角色/归属、目标空库/事务锁、密文重加密、私有文件 600 和 JWT 密钥隔离有测试。正式 stop/destroy 回收所有验收环境，12 个端口释放、6 个验收库/角色及验收进程/目录不存在，公共登记为空；收尾 PG 夹具也全部回收。
- **静态与文档：** 本次新增脚本及相关回归的 Ruff check/format、Shell 语法、差异检查，16 份 Markdown 的文档规则、新导航链接和 YAML 契约通过。范围外 37 条绝对路径、FEATURES 4 条既有失效链接及旧脚本 6 条既有 Ruff 诊断未修复，不宣称全仓检查通过。
- **未验边界：** 未调用真实外部模型，外部账号额度仍共享；不作 CPU/内存容量保证，未做生产部署或 Git 提交，未创建/删除用户 Worktree。

结论：追加需求全部完成，首次 start 自动初始化可复用基础数据，后续保留本环境修改；主工作区配置与数据未覆盖。

## 后置文档问题

用户明确要求本次不修复。`scripts/check_docs.py` 当前报告的 37 条均为个人 macOS 绝对路径，影响文档在其他机器或 Worktree 中的可移植性，不是本次启动脚本报错。逐文件计数与 HEAD 相同，清单如下：

| 文件 | 数量 | 报告行号（2026-10-10） |
|---|---|---|
| [open-swe-vs-runtime-gap.md](../../knowledge/open-swe-vs-runtime-gap.md) | 30 | 42, 57, 61, 118, 171, 219, 267, 271, 311, 372, 376, 437, 535, 580, 608, 636, 672, 708, 751, 786, 818, 911, 958, 1002, 1052, 1092, 1138, 1188, 1217, 1245 |
| [agent-followup-suggestions/README.md](../20261005-agent-followup-suggestions/README.md) | 1 | 51 |
| [scheduled-agent-tasks/frontend-handoff.md](../20261005-scheduled-agent-tasks/frontend-handoff.md) | 1 | 4 |
| [scheduled-agent-tasks/plan.md](../20261005-scheduled-agent-tasks/plan.md) | 1 | 11 |
| [scheduled-agent-tasks/verification.md](../20261005-scheduled-agent-tasks/verification.md) | 1 | 101 |
| [agent-context-window-governance/frontend-handoff.md](../20261006-agent-context-window-governance/frontend-handoff.md) | 1 | 202 |
| [agent-execution-budget/implementation/02-frontend-budget-implementation.md](../20261007-agent-execution-budget/implementation/02-frontend-budget-implementation.md) | 1 | 7 |
| [agent-run-cancellation/frontend-handoff.md](../20261007-agent-run-cancellation/frontend-handoff.md) | 1 | 332 |

收尾额外核对出 FEATURES 的 4 条既有失效链接及旧脚本 6 条既有 Ruff 诊断，均与 HEAD 一致；它们不属于上述 37 条，不混入本次文档检查计数，也未修改。
