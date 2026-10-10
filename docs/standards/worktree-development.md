---
status: active
approved_on: 2026-10-10
last_verified: 2026-10-10
source_project: docs/projects/20261010-worktree-local-stack/
---

# Worktree 开发与本地资源隔离规范

用户已批准本规则，工具已通过三套真实本地栈隔离及浏览器/Worker 验收，证据见[专项验证](../projects/20261010-worktree-local-stack/verification.md)。适用于同一台可信开发机上的关联 Git Worktree，不作为生产部署规范。

## 必须先读

在 Worktree 开发、启停服务、迁移、联调或 E2E 测试前阅读本文。主工作区使用原有 app-local 配置及默认地址；关联 Worktree 必须初始化，缺少配置时禁止回退到主工作区。

Worktree 只隔离代码。每套联调环境包含 Web、Platform API、Runtime API、Runtime Worker、专属 Redis，两个独立 PostgreSQL 数据库和角色，以及独立 Workspace/PID/日志。PostgreSQL 服务器、工具程序和包缓存可以共享。

## 初始化与日常操作

先确认主工作区的 Runtime/API 私有 `.env` 和 Runtime 依赖已就绪，本机已有 Python 3.13、uv、pnpm、PostgreSQL、`redis-server` 和 `lsof`。新 Worktree 初始化工具可用主工作区 Python 读取配置和创建资源；实际应用必须在本目录执行 `deps` 后启动。

在目标 Worktree 根目录执行：

```bash
bash "scripts/local-stack.sh" init
bash "scripts/local-stack.sh" deps
bash "scripts/local-stack.sh" doctor
bash "scripts/local-stack.sh" start
bash "scripts/local-stack.sh" status
bash "scripts/local-stack.sh" logs runtime-worker
bash "scripts/local-stack.sh" restart-one platform-api
bash "scripts/local-stack.sh" stop
```

- `init` 继承主工作区 `apps/runtime-service/.env`、`apps/platform-api/.env`，以及存在时的 Web `.env` / `.env.local`（后者优先），生成独立资源地址和环境密钥；外部模型/搜索/观测配置直接复用。私有副本在 `.local-stack/runtime.env`、`platform.env`、`web.env`，不修改原文件、不整体 source；Web 只注入 `VITE_*` 公开参数。新 Worktree 管理员默认 `admin / admin123`，仅用于回环监听的可信本地开发环境；主目录账号不改变。重复执行保持本环境配置，不重新复制或重置密码。
- 需要本机 PostgreSQL 创建数据库和角色权限。默认使用 Unix socket 的 `dbname=postgres`，也可通过私有环境变量 `LOCAL_STACK_PG_ADMIN_DSN` 提供本机管理员连接。不创建或改动 PostgreSQL 服务器配置，不覆盖现有非本环境资源。
- `deps` 用当前分支 frozen 锁文件安装依赖。主工作区和 Worktree 各自拥有安装目录，共享 uv cache / pnpm store；不复制或链接主工作区 `.venv` / `node_modules`。
- `doctor` 检查配置和资源，不杀进程、不迁移。未启动的专属 Redis 只检查配置、程序和端口；运行中的 Redis 检查实际连接。
- `start` 先预检和迁移，为新的空环境复制一次主库基础数据，再启动所属进程；`seed` 可在迁移后单独执行。完成标记与数据在同一目标库事务中提交，后续启动不再复制、不覆盖本环境修改。旧环境已有数据且无完成标记时，自动启动保留原数据并跳过导入，显式 `seed` 拒绝导入。失败只回收本次启动的进程；迁移与写入只能访问本环境数据库，主库仅只读。
- `stop` 包含专属 Redis，保留数据库、Redis 持久数据、Workspace、环境身份和端口分配。主工作区 PostgreSQL/Redis 不由本脚本停止。
- `status` 输出环境 ID 和真实访问地址，不能假定 Worktree 使用 3000/2142/8123。

## 身份、登记与端口

- 环境 ID 为 `wt_<随机ID>`，绑定 Worktree 的真实路径，切换分支不变。不要复制 `.local-stack/` 到另一个目录。
- `<git-common-dir>/local-stacks/registry.json` 是关联 Worktree 共用的资源登记表，不存秘密。`list` 可以查看登记；禁止直接编辑来抢占分配。
- 首次初始化从 23000-29999 随机分配 Web/API/Runtime/Redis 四个端口，排除已登记及当前被占用的端口。分配写入加跨进程锁，登记原子替换。
- 重启复用原端口；端口被外部程序抢占时明确失败，不强杀、不让某个服务单独漂移。随机与“少见”端口不等于保证空闲。
- 同一环境操作加锁；不同环境可并发。进程停止须核对命令及真实目录归属，不凭 PID 文件或端口单独决定。
- API upstream、Runtime self URL、模型/Thread/message/memory 授权回调和前端代理统一生成，指向同一环境。不能手工指向其他 Worktree 或主工作区。
- 额外预览/测试服务同样不能硬编码公共端口或抢占登记端口；先使用 OS 分配空闲端口并保留所属进程句柄，结束时仅停止自己启动的进程。长期联调服务应先扩展统一登记再接入。

## 数据与文件

- 每套环境有 `<环境ID>_platform`、`<环境ID>_runtime` 两个数据库，使用同名非超级用户角色。数据库和角色带环境归属标记；不采用公共 schema 代替数据库隔离。
- 专属 Redis 监听回环地址、有独立密码和持久目录。不能只用共享 Redis 的不同逻辑 DB 冒充完整隔离，Pub/Sub 不受 DB 分隔。默认上限 512 MiB、noeviction，Worker 并发为 1。
- `.local-stack/` 不入 Git，保存 `environment.json`、`runtime.env`、`platform.env`、`web.env`、`redis.conf`、`pids/`、`logs/`、`redis/`、`workspaces/`。私有配置权限为 600。
- 私有配置、状态目录和安装目录不能通过软链接指向其他环境，包含父目录的间接链接；PG 管理员连接信息不传给后台应用进程。
- 主工作区 PID/日志也在自己的 `.local-stack/`；旧临时 PID 文件不自动接管。发现旧手动进程先核对归属，再显式执行 `stop`。
- 构建产物、Vite 缓存、覆盖率、截图和测试报告保留在所属 Worktree。不要复用其他 Worktree 的可写缓存。
- 默认复用主库的模型连接，密文用新环境 master key 重新加密，不共享主密钥；JWT、委托、数据库/Redis 密码仍独立。外部模型、搜索及观测账号的额度/资源与 CPU、内存和磁盘仍共享，避免同时启动大量 Worker 或真实模型测试。

### 基础数据白名单

首次 `start` 使用主工作区两套 `.env` 的本机 PostgreSQL 连接，在源库只读 repeatable-read 事务中读取；每个目标库验证专属角色/归属、空数据及列类型后复制。保留原业务 ID 和外键，不生成包含凭据的 dump，不在日志打印模型 Key。两库分别取配置快照，不作为完整备份，也不停止主环境。

| 数据 | 初始化行为 |
|---|---|
| 租户、用户、项目/成员、Agent、服务账号定义/项目授权 | 复制定义与关系；只在目标库设置管理员初始密码，其他用户保留原密码哈希 |
| 模型/Graph/工具目录、项目模型/Graph 策略、工具限制、公告、平台配置 | 复制；重加密模型凭据，将主 Runtime 目录地址映射到本环境 |
| Runtime assistants/assistant_versions、用户自定义 dear_skills | 复制配置，保留与平台配置对应的 ID |
| 对话/Run/checkpoint、审批/消息/取消记录、Usage、审计、登录/服务账号令牌、公告已读 | 不复制 |
| 定时任务、长期记忆、store、旧技能版本、Redis 队列、Workspace 文件 | 不复制，避免历史内容污染新测试以及定时任务重复自动执行 |

导入有完成标记后不追随主库变更，Worktree 内修改互不影响。源库停机、模型密文无法解密或白名单表结构不同会明确失败，目标事务回滚；另一个已经完成的库可在重试时复用。工具不清空已有环境来重新导入，也不自动复制未知新表。初始 Workspace 为空，依赖旧会话文件的配置需在新环境准备对应测试文件。

## 依赖复用与源码归属

- 可共享 Python/Node/uv/pnpm 程序、uv 下载缓存、pnpm 内容 store、Playwright 浏览器二进制。
- Python `.venv` 必须由本服务、本 Worktree 建立。两个 Python app 都是 editable 安装，共享 `.venv` 会导入其他目录代码。
- `node_modules` 独立建立，pnpm 自行从 store 链接/克隆包内容；禁止将整目录软链接到主工作区。锁文件、workspace 配置和补丁以当前 Worktree 为准。
- 工具清除继承的 `VIRTUAL_ENV`、`UV_PROJECT_ENVIRONMENT`、`PYTHONPATH`，避免带入主环境。不要手动设置跨目录安装目标。
- `deps` 检查应用模块实际解析路径，确保源码来自当前 Worktree。源码变更正常 editable 生效；依赖/锁文件/补丁变更后重新执行 `deps`。

## 测试与浏览器

- 单元测试不需要启动全栈。数据库集成测试必须使用本环境配置；禁止默认接入主工作区库或 Redis。
- `pnpm --dir "apps/platform-web" test:e2e` 自动读取本 Worktree 的登记地址。配置不存在时拒绝启动；显式 `PLAYWRIGHT_BASE_URL` 必须等于登记地址。
- 浏览器测试使用独立上下文，不共享 storageState。手动联调按 `status` 给出的 URL 访问；不同 Web 端口隔离 localStorage，但 cookie 不按端口隔离，涉及 cookie 的测试必须使用独立浏览器上下文。
- `reuseExistingServer` 仅用于本环境已启动的前端；不得复用主工作区 3000 端口。
- 旧专项 `RUN_ERROR_CONTRACT_E2E`、`RUN_SSE_CONTRACT_E2E`、`RUN_LOCAL_GOVERNANCE_E2E` 仍使用固定 `/tmp` fixture，Worktree 中明确拒绝这些模式。先将专项 runner 的 fixture、地址和截图路径改为所属环境，才能恢复并发执行；禁止复制其他会话的 `/tmp` 配置绕过检查。
- 验收至少验证三套环境同时联调、停止一套不影响另外两套、Worker 不串任务、数据库/Workspace 不串数据、依赖导入属于当前源码。

## 销毁与异常恢复

```bash
bash "scripts/local-stack.sh" list
bash "scripts/local-stack.sh" stop
bash "scripts/local-stack.sh" destroy --confirm "wt_具体环境ID"
```

`destroy` 会删除该环境数据库、角色、Redis 数据、Workspace 和本地状态并释放登记。AI 执行前必须取得用户对具体环境销毁的明确确认；方案批准不等于允许删除用户已有数据。命令本身也要求精确 ID，并拒绝仍运行的环境、不属于该环境的 PG 资源或活跃数据库连接。不强制断开连接，不用 CASCADE。

初始化失败保留已登记身份和配置，补齐管理员权限/依赖后重试 `init`，不创建另一套身份绕过失败。端口冲突先查看所属进程，不用 pkill 或 lsof 找到 PID 后直接 kill。删除/移动 Worktree 前先停止；需要保留数据则保留目录和登记，不自动回收“看起来过期”的环境。

共享部署、发布版本、生产数据库和系统配置不属于本地隔离资源。此规范不授权 Git 提交/推送、变更生产服务或修改上游共享依赖版本。
