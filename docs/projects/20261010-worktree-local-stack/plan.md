# Worktree 本地联调资源隔离 - 方案

- **状态：** 已完成（`done`）；T01-T07 配置、基础数据复用及资源隔离全部验收。

## 背景与批准

Worktree 隔离代码，但当前启动脚本共用临时 PID/日志目录，默认服务端口、数据库、Redis 和 Workspace 也可能重叠。端到端测试固定启动 3000 端口，Python editable 安装不能跨 Worktree 共享。

2026-10-10 用户批准上轮完整方案：首次随机分配并持久复用端口；Git 公共目录集中登记并加锁；统一生成环境内地址；各环境独立数据资源和进程归属；共享 uv/pnpm 包缓存但独立安装目录；规范集中到 docs/standards 并由 AGENTS 引导查阅。

## 设计

- `scripts/local_stack_worktree.py`：识别关联 Worktree，在 Git common dir 的 `local-stacks/registry.json` 登记环境 ID、真实路径、端口和资源名。使用 Python 标准库文件锁、原子替换和 socket 绑定检查。端口池为 23000-29999，注册分配后重启复用。
- 每个目录的 `.local-stack/` 保存私有配置、PID、日志、Redis 持久文件和 Workspace，不入 Git。登记表不存密钥。主工作区继续使用原有 app-local 配置及端口，但 PID/日志也改为本目录独立。
- `init` 从主工作区已有私有配置读取基线，覆盖所有本地链路地址、数据库、Workspace 和环境凭据；为关联 Worktree 创建两个专属数据库及非超级用户角色。管理员连接仅由 `LOCAL_STACK_PG_ADMIN_DSN` 或本机 PostgreSQL Unix socket 提供，不打印或写入登记表。
- Redis 使用本机已有 `redis-server` 创建专属回环监听进程，持久数据保留在本环境。API、Worker 只能使用本环境 Redis。Worker 默认并发 1，主工作区保持原值。
- `deps` 用当前 Worktree 的 frozen 锁文件同步独立 `.venv` / `node_modules`，利用 uv cache 和 pnpm store。拒绝链接到其他 Worktree 的安装目录，检查 Python 包实际解析路径。
- `doctor/status/logs` 不杀进程、不执行迁移。`start` 检查、迁移、启动；失败只清理本次新启动进程。`stop` 保留数据及分配。`destroy --confirm <环境ID>` 只允许停止后的本环境，并显式确认删除专属数据和释放登记。
- Playwright 从登记配置读取地址，全部联调使用本环境；缺少配置拒绝回退到主工作区。

## 风险控制

- 注册文件锁只覆盖分配写入，实际启动仍需绑定检查；外部程序抢占端口时失败，不强杀、不单服务漂移。
- 同一环境启停加锁，防止重复启动/同时销毁。检查 PID 的命令和真实目录归属。
- 全部 PG 操作验证专属数据库/角色名及归属，拒绝覆盖既有非本环境资源；清理不使用强制断开外部会话或 CASCADE。
- 配置缺失、登记不一致、跨目录依赖、资源指向主工作区时拒绝启动。
- CPU、内存、磁盘和模型配额仍共享；不实现容量调度服务。

## 2026-10-10 追加需求与实施范围

用户要求管理员默认 `admin / admin123`、直接复用当前项目各 app 的 `.env`，并复制主数据库中有用的配置数据以减少手工创建。37 条存量文档路径问题后置。

- `init` 继续继承主工作区 Runtime/API `.env`，补充可选 Web `.env` 的私有副本；数据库、Redis、Workspace、链路地址、JWT/委托密钥保持环境独立。Worktree 管理员默认值设为 `admin / admin123`，只用于本地回环环境，不修改主目录账号或生产默认值。
- `start` 在迁移后、启动服务前自动执行一次基础数据初始化，也提供 `seed` 命令供已迁移空环境使用。重复启动读取数据库内完成标记，不覆盖 Worktree 自己的改动；已有非空旧环境自动启动跳过导入，显式 `seed` 拒绝覆盖，不清空、不合并。
- Platform 白名单：租户、用户、项目/成员、服务账号定义/项目授权、Agent、模型/Graph/工具目录、项目策略、工具限制、公告和平台配置。保留业务 ID 和外键；只在目标库将管理员设为默认账号，模型凭据用本环境新 master key 重新加密，目录 runtime 地址改为本环境。
- Runtime 白名单：`assistants`、`assistant_versions`、`dear_skills`。会话、Run、checkpoint、消息、取消/回执、Usage、审计、登录/服务账号令牌、定时任务、记忆、store 和旧技能版本不导入，Redis/Workspace 保持空环境。定时任务不复制，避免启动后重复自动执行外部动作。
- 源连接仅允许本机 PostgreSQL，使用只读 repeatable-read 事务；每个目标库在单一事务中检查归属、空库及列类型兼容后复制和记录完成状态。两库快照分别取，保留原 ID；不宣称为主项目完整备份，也不停止主环境写入。
- 不生成包含明文凭据的数据文件，不打印 DSN/密码/模型 API Key。失败事务回滚，已完成的另一个库保持完成标记以支持安全重试。
- 外部模型/工具凭据按用户要求复用，调用额度与外部服务资源仍共享。未知新表不会自动复制，需明确加入白名单。

## 回滚

停止新增 Worktree 环境，保留 `.local-stack/` 数据及登记，不销毁数据库。主工作区原 app-local 配置、端口和数据未覆盖，可使用原启动方式。撤销本次工具代码前先停止新增 Redis/服务；不执行自动数据删除。
