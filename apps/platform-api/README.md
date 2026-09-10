# Platform API

Platform 是 Runtime 的治理与受控网关：管理身份、项目、Agent、模型、策略和审计；GraphHarbor 持有 Thread/Run/Checkpoint/Interrupt 执行事实；Runtime 持有图、工具和模型构造。

## 当前进度

2026-09-10，[重构工程](../../docs/projects/20260910-platform-api-refactor/README.md)进行中（partial）：

- 已删除知识库、测试用例平台业务及前端接入。
- 正式代码已迁入可安装的 `src/platform_api`，旧 `app` 包、根目录启动包装与 Assistant 导入兼容包已移除。
- API 初始化使用线程池短事务，启动失败和正常关闭都会释放数据库资源。
- Graph 目录改为远端只读发现，参数 schema 改为远端获取；已删除本机源码扫描和 AST 兜底。部署端需包含本轮 GraphHarbor 的默认 Assistant 注册与 schema 修复，旧 post21 服务不满足该契约。
- 新数据库、单表 Agent与简约网关尚未完成。Operations 及旧业务层级仍在逐步退役，不作为新增功能模板。

不兼容旧产品逻辑，不迁移旧数据；新平台自身的数据完整性、安全和恢复仍须验证。历史 Freeze 文档不代表本工程已完成。

## 代码各部分的用途

```text
src/platform_api/
  main.py          create_app：应用创建、路由与中间件装配
  config.py        环境配置与启动校验
  bootstrap/       lifespan：当前 API 资源初始化和释放
  core/            共享身份上下文、错误、数据库、凭据与观测
  modules/         平台业务用例；现有四层目录待按实际职责简化
  adapters/        官方 SDK 及必要的 HTTP/SSE 适配
  entrypoints/     系统路由、HTTP 依赖/中间件和暂存 Worker 入口
migrations/        Alembic 文件；当前仍是旧修订链，新空库基线待实现
scripts/           开发数据库工具
tests/            自动化测试（不属于已删除的 testcase 产品）
```

业务归属：

| 模块 | 职责 |
| --- | --- |
| identity / iam / users | 登录、身份、用户与平台/项目权限 |
| projects / service_accounts | 项目、成员和服务身份授权 |
| agents | 项目 Agent 配置与治理；不执行图 |
| runtime_catalog / runtime_policies | 部署能力视图、模型配置与执行策略 |
| runtime_gateway | 授权、运行参数决议、协议适配和转发 |
| announcements / audit / platform_config | 公告、可追溯操作记录与真实生效的设置 |
| operations | 暂存旧 Run 协调与目录/Agent 同步；禁止添加新任务 |

新增功能先确定所有者，再写对应模块的路由、Pydantic 输入输出和用例；只有需要持久化或复用查询时才添加模型与查询文件。不要机械复制四层目录、空 Protocol、通用 CRUD 基类或平台执行状态机。具体目标见[服务结构专题](../../docs/projects/20260910-platform-api-refactor/04-service-structure-and-migration.md)。

## 安装与启动

在 `apps/platform-api` 下使用 Python 3.13：

```bash
uv sync --frozen
cp ".env.example" ".env"
uv run --frozen uvicorn platform_api.main:create_app --factory --host 127.0.0.1 --port 2142 --reload
```

根据环境设置数据库与 Runtime 地址。配置来自 `PLATFORM_API_*` 环境变量或工作目录的 `.env`；修改已有配置文件时保留自己的凭据。

Operations 尚未全面退役期间，当前执行链仍需要：

```bash
uv run --frozen python -m platform_api.entrypoints.worker.main
```

开发数据库工具为 `uv run --frozen python scripts/init_db.py`。它使用当前模型创建开发表，不代表已完成新数据库方案。Alembic 可通过绝对配置路径定位修订目录，不依赖执行时的工作目录；新基线交付以前不要把旧修订链作为新平台空库部署方案。

## 镜像

```bash
docker build -t platform-api:local .
```

镜像按 `uv.lock` 安装正式包，包含 `migrations/` 和 `alembic.ini`，默认启动应用工厂；不需要根目录 Python 包路径注入。按当前开发顺序，先完成本地链路，整体功能完成后统一验收 Docker/Compose。

Graph 目录显式刷新通过官方 `POST /assistants/search` 分页查询系统默认 Assistant，普通列表只读快照。参数展示在项目授权后调用 `GET /assistants/{graph_id}/schemas`；不会创建上游 Assistant，也不会返回宿主机路径。远端不可用时明确报错，不生成假 schema。公开可编辑参数是远端 Context 与平台允许字段的交集，身份、Tool 授权及内部模型引用不可编辑。

## 验证与文档

```bash
uv run --frozen python -m compileall -q src tests
PLATFORM_RUNTIME_INTEGRATION=0 uv run --frozen python -m unittest discover -s tests -p 'test*.py' -q
```

测试使用临时数据；外部集成关闭时的 skip 不计通过。真实 Runtime 联调和部署恢复另按工程验收。

协作先读[根 AGENTS](../../AGENTS.md)，再读[工程状态](../../docs/projects/20260910-platform-api-refactor/README.md)和[文档导航](docs/README.md)。当前仍在改造的 handbook 以工程已确认决策为准。
