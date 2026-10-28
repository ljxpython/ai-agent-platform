# 环境、日志与测试数据清理运维手册 (Environment Cleanup Runbook)

> **适用场景：** 本地或测试环境运行较长时间后，磁盘被服务日志、旧备份 dump、测试缓存撑满，或需要彻底清空历史对话快照、审计流水与 Redis 任务队列时使用。
> **核心工具：** `scripts/cleanup_env.sh`（一键自动化脚本）
> **核心原则：** 坚决保护模型配置、长期记忆、技能库与用户数据；测试数据与陈年日志一网打尽。

---

## 一、 快速使用指引 (人话速查表)

在执行任何涉及数据库的清理前，**务必确保写进程已停止**（避免锁冲突或写入不一致）：
```bash
./scripts/local-stack.sh stop
```

| 场景需求 | 推荐命令 | 影响范围 |
|---|---|---|
| **1. 日常快速清理**<br>仅清理代码构建缓存、pytest 缓存与临时报告 | `./scripts/cleanup_env.sh` | 零风险，仅清空 `.pytest_cache`、`.ruff_cache`、`test-results/` 等文件系统缓存 |
| **2. 测试环境一键重置**<br>重置用户会话、清空沙箱，准备新一轮测试 | `./scripts/cleanup_env.sh --clean-test-env -y` | 清空对话快照（`threads`, `runs`, `checkpoints`, `runtime_events` 等），软删除非保留测试项目（默认保留 `Test` 项目），清空沙箱工作区 |
| **3. 终极全量深度大扫除**<br>释放数 GB 磁盘空间，彻底清除所有历史垃圾 | `./scripts/cleanup_env.sh --deep -y` | 在模式 2 的基础上，额外清空控制面审计日志（`audit_logs`）、请求流水（`run_requests`）、Redis 测试残留、`.local-stack/logs` 本地日志以及陈年旧 dump 归档 |
| **4. 安全演练预览 (Dry-Run)**<br>只看会清哪些数据，不实际动手 | 追加 `--dry-run` 参数<br>例如 `./scripts/cleanup_env.sh --deep --dry-run` | 仅输出统计报告，不做任何修改 |

---

## 二、 数据分层与清理范围一览

### 1. 运行时数据库 (`graphharbor_acceptance`)
*   **清理对象：**
    *   `threads`：会话线程记录
    *   `runs`：会话执行回合记录
    *   `checkpoints` / `checkpoint_writes` / `checkpoint_blobs`：LangGraph 状态快照与消息二进制
    *   `runtime_events`：节点执行 SSE 事件与流式事件
    *   `run_checkpoint_baselines` / `retry_counters`：运行基线与计数器
    *   `runtime_message_inbox` / `dear_external_tasks`：外部临时任务与消息收件箱
*   **保护白名单（坚决不删）：**
    *   `dear_memory`：智能体长期记忆资产
    *   `dear_skills` / `dear_skill_versions`：技能定义与版本代码
    *   `assistants` / `assistant_versions`：智能体助手元数据
    *   `crons`：定时任务配置

### 2. 控制面数据库 (`platform_api`)
*   **清理对象：**
    *   `audit_logs`：平台审计与用户操作日志（高频请求下可能多达百万级）
    *   `run_requests`：运行请求流水
    *   `refresh_tokens`：已过期或已被撤销的 JWT 刷新令牌（`expires_at <= NOW() OR revoked_at IS NOT NULL`）
    *   `projects`：多余的历史废弃测试项目（软删除处理）
*   **保护白名单（坚决不删）：**
    *   `users` / `service_accounts`：平台用户与服务账号凭据
    *   `runtime_catalog_models` / `project_model_policies`：大模型配置、网关端点与模型密钥
    *   指定保留的项目（默认保留名为 `Test` 的项目）

### 3. Redis 缓存层
*   **默认清理库：**
    *   `DB 7`：当前本地环境默认库（存放 `run-stream` 与 `showcase` 任务状态）
    *   `DB 0` / `DB 2` / `DB 13` / `DB 14` / `DB 15`：自动化测试、压测与 CI 测试留下的残留 key

### 4. 本地文件系统
*   `.local-stack/logs/*.log`：Platform API 与 Runtime Service 的本地运行日志（长期运行可达数百 MB）
*   `apps/platform-api/.data/backups/`：过去执行清理时自动备份的旧 dump 归档（长期累积可达数 GB）
*   `apps/runtime-service/.runtime/workspaces/` & `showcase/`：Agent 沙箱运行时在磁盘上创建的代码与文件
*   构建分析缓存：`.pytest_cache/`、`.ruff_cache/`、`.mypy_cache/`、`.eslintcache`、全局 `__pycache__` 与 `.DS_Store`

---

## 三、 高级底层命令 (直接调用 Python 脚本)

如果需要更细粒度地控制底层清理逻辑，可以直接调用子模块 Python 脚本：

### 1. 仅清空控制面审计与请求流水
```bash
cd apps/platform-api
uv run --frozen python scripts/database.py clean-ledgers --execute --confirm-database platform_api
```

### 2. 软删除历史多余项目并保留指定项目
```bash
cd apps/platform-api
# 按项目名称保留
uv run --frozen python scripts/database.py clean-projects --keep-project-name Test --execute --confirm-database platform_api
# 或按 UUID 保留
uv run --frozen python scripts/database.py clean-projects --keep-project 5a5b7239-43e3-40e6-bba3-e64d96057607 --execute --confirm-database platform_api
```

### 3. 底层历史清理工具 (`cleanup_history.py`)
```bash
cd apps/platform-api
# 仅清理平台控制面历史 (自动做 dump 备份)
uv run --frozen python scripts/cleanup_history.py --platform --execute --writers-stopped --confirm-database platform_api

# 仅清理运行时对话历史 (自动取消未完成的 runs 并做 dump 备份)
uv run --frozen python scripts/cleanup_history.py --runtime --cancel-unfinished-runs --execute --writers-stopped --confirm-database graphharbor_acceptance
```

---

## 四、 常见问题与排障

### Q1: 运行清理时报错 `Unfinished runs exist; finish or cancel them first.`
*   **原因：** 数据库中存在处于 `running`、`queued` 等活跃状态的会话，为防止清理过程中数据写入导致脏状态，系统主动拒绝。
*   **解法：** 使用带 `--clean-test-env` 或 `--deep` 的 `cleanup_env.sh`，其底层已自动包含 `--cancel-unfinished-runs` 机制，会自动将挂死的 runs 复位为 `cancelled` 状态后再截断。

### Q2: 报错 `Database is locked / Lock timeout`
*   **原因：** 后端服务（`platform-api` 或 `runtime-service`）仍处于启动状态并持有长连接事务锁。
*   **解法：** 执行 `./scripts/local-stack.sh stop` 停止本地服务，再重新运行清理命令。
