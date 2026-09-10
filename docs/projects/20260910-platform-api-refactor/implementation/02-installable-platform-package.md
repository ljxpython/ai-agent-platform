# 可安装平台包与启动资源生命周期

## 时间与任务

2026-09-10；对应 04 的 S1/S3/S4 中正式包、启动入口、镜像交付和资源初始化部分。业务模块内部压平、新数据库基线、全服务 DB/HTTP 生命周期仍未完成。

## 实现

- 正式 Python 包由 `apps/platform-api/app` 移至 `src/platform_api`；`factory.py` 合入命名明确的 `main.py`，`core/config.py` 移至包根 `config.py`。同步更新源码、测试 mock/importlib 路径、Alembic 和开发脚本导入。
- 删除根目录 `main.py`/`worker.py` 包装、测试 sys.path 注入、13 个 Assistant 兼容重导出文件、空 tenants 模块、无消费 NullUnitOfWork。其余业务代码保留当前行为，已有未提交改动随文件迁入，没有覆盖。
- pyproject 使用现有 Runtime 同样的 setuptools src 包布局；uv.lock 将本服务记录为可安装 editable 项目。开发使用 `uv sync --frozen`；API 使用 `uvicorn platform_api.main:create_app --factory`，暂存 Worker 使用 `python -m platform_api.entrypoints.worker.main`。
- 更新两份正式 Compose、应用 Compose 示例、CI、local-stack 与演示启停/健康脚本。独立 interaction-data-service 的 `main:app` 不改名。
- Docker 镜像固定 uv 0.9.9，使用锁文件安装正式包，复制 migrations/alembic.ini；去除不需要的编译工具和 curl，平台 Compose 健康探测使用 Python 标准库。镜像没有源码挂载要求。
- Alembic 使用 `%(here)s/migrations` 定位修订目录，不再依赖当前目录/sys.path 注入。当前修订内容仍是旧表链路；本次不新增旧数据迁移，也不把它标成新空库基线。

### 资源清理

`bootstrap/lifespan.py` 将建表与管理员初始化纳入 try/finally，初始化失败也释放 engine，并清空应用 state 中的数据库资源。同步建表与管理员初始化在线程池执行；管理员初始化自身用 `session_scope` 保证 Session 创建、查询、提交/回滚和关闭在一个线程内。

```python
# 原来：初始化失败发生在 try/finally 之前，engine 不释放。
# 现在：资源创建后的全部初始化、服务与关闭都在清理边界内。
try:
    await run_in_threadpool(create_core_tables, engine)
    await run_in_threadpool(service.ensure_bootstrap_admin)
    yield
finally:
    await run_in_threadpool(engine.dispose)
```

上面是生命周期关键部分，实际代码保留配置开关并清空 state。Worker 构造/建表也进入清理边界；开发 init_db 工具完成或失败时释放 engine。其他 async 业务里的同步 UoW 尚未全面替换，不宣称事件循环阻塞已整体解决。

### 明确保留的待办

目录 AST provider 的原有源码查找暂时只调整包路径深度以避免本次移动改变行为，远端 schema 合同仍由 C1–C3 替换；不新增 fallback 或将路径扫描当作新范式。旧 `/api/assistants` 产品路由、假 resync 与运行协调仍等待对应任务，删除导入兼容包不代表这些能力已完成退役。

## 验证

- 新增 `tests/test_resource_lifecycle.py`：初始化在线程池执行、管理员两次启动只保留一条记录、API 初始化失败清理资源、Worker 构造失败清理资源，3 个测试通过。
- 离线 uv sync、wheel 构建通过；wheel 安装到仓库外临时目录，用 Python 隔离模式检查真实包来源、创建应用、存活探测与未认证项目请求 401，且不导入旧 app 包。
- 首次全量回归 158 项：153 通过、1 项已有目录失败、1 项本地 SSE 代理超时、3 跳过。堆栈确认本地 HTTP 测试走了环境代理；该测试增加 `trust_env=False` 后，相关 3 项复验全部通过。未隐藏初次失败，也没有放宽超时或删除 SSE 断言。
- shell 语法、Compose、Python 编译与最终镜像证据见 [04 验证记录](../04-service-structure-and-migration.md)。没有发布包、提交代码或操作业务数据库。

镜像构建及禁网、无源码挂载的容器烟测通过：安装包来源、lifespan、存活探测、未登录鉴权和异地工作目录下 Alembic 修订发现均验证成功。数据库已关闭，未执行 upgrade；当前旧修订头不能代表新 schema 基线。

本切片的包与启动资源边界已验证；对应 S1/S3/S4 及整体工程仍为 partial，剩余内容见 04。
