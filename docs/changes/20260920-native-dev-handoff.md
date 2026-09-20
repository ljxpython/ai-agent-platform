# 原生开发环境文档与服务器交接

日期：2026-09-20。范围：仓库级文档修订与私有文件交接，不修改业务契约、运行代码或数据库。

## 背景与授权

用户确认非 Docker 开发环境方案，要求沿用本地数据库名和账号作为推荐，修正部署文档，
并将当前代码和配置交付到腾讯服务器。后续明确选择空库初始化管理员，不迁移旧项目、用户或聊天，
另明确要求将服务器原仓库切到本地当前分支。
服务器上的安装、建库、迁移和启动由用户按文档执行。

## 当前标准

后续状态：用户另批准[本机 PostgreSQL 密码认证](../projects/20260920-local-postgres-password/README.md)，
本地已启用 SCRAM，Runtime 密码与本交接的服务器配置副本一致。原始 env 备份保留交接当时的内容，
不将原始无密码备份当成当前推荐配置。

- Runtime：数据库 `graphharbor_acceptance`，角色 `lijiaxin`；服务器角色使用密码认证且非超级用户。
- 平台：数据库/角色 `platform_api`；管理员 `admin`，密码只在私有配置。
- Redis：回环地址、逻辑库 7，认证服从目标环境。
- 默认进程：Runtime API、Runtime Worker、Platform API、Platform Web；结果域按需单独启动。
- 代码、配置与数据分开交接；不复制依赖目录、数据库、队列、会话或工作区。

## 修订范围

- `docs/quickstart/deployment-guide.md`：原生依赖、空库、账号、配置、SSH、模型和验收完整步骤。
- `docs/quickstart/local-dev.md`、`docs/quickstart/env-matrix.md`、`docs/local-deployment-contract.yaml`：统一当前默认链路。
- `docs/guides/ai-deployment-assistant-instruction.md`：修正 SQLite、旧模型配置和服务名单，区分上传与部署。
- `README.md`、`README.en.md`、`docs/README.md`、`docs/FEATURES.md`：导航与现状同步。
- `docs/guides/database-operations.md`、`docs/guides/development-guidelines.md`：本地推荐名称、可选结果域边界。
- `apps/platform-api/docs/handbook/configuration.md`：正式开发 PG，SQLite 仅测试/迁移源。
- `apps/runtime-service/README.md`、`apps/runtime-service/deploy/README.md`：原生配置路径、真实四进程和应用表迁移入口。

历史阶段方案、归档、数据库迁移历史不改写成新机部署说明；当前部署入口已与脚本核对。
容器专有规范保留独立入口，本次不宣称容器或生产验收完成。

## 目标机只读检查

Debian 13 x86_64；Python 3.13.5、uv 0.12.17、Node 22.22.2、pnpm 10.5.1、PostgreSQL 17.11。
PG/Redis 已运行且只监听回环，PG 由面板目录安装；系统 Python 缺少 dotenv。
内存约 3.6 GiB，无 swap；仅作为容量事实，不代表已跑通完整栈。
服务器已有项目目录，交接使用独立受保护目录，不覆盖已有项目。

## 验证与边界

- `python3 scripts/check_docs.py` 通过；本次文档 `git diff --check` 通过。
- 15 个相关文件的相对链接、56 段 shell 示例语法及私密值检查通过；部署契约 YAML 解析及默认进程与脚本对照通过。
- 已上传源码快照、6 份原始 env 和服务器配置副本；整体包及逐文件 SHA-256 校验通过。
- 交接目录及私有目录权限 700，私有文件 600；未上传 `~/.my_best/.env` 或 SSH 密码。
- 服务器原仓库从 main 切到 `feat/dear-agent-p0-p1`，HEAD `6df0e17` 与本地一致，远端工作区干净。
- 原仓库分支仅代表已提交版本；本机未提交内容在独立源码快照中，不假称已 push。
- 未安装软件、未建库、未执行迁移、未启动应用；真实登录与模型 E2E 留给后续部署验收。
- 未提交 Git，不把其他进行中的业务改动当成此次文档实现。
