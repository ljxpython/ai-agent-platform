# 后端验收三项收尾

日期：2026-09-10。用户批准收尾负载、真实备份恢复、公开网关矩阵；沿用既定后端方案，不扩展前端、整套容器部署或 Server 完整等价性。

## 实现

- `scripts/platform_backend_closeout.py`：复用已有 Showcase 的私有环境，使用 PostgreSQL 原生 dump/restore 创建两个新隔离库；比较所有表的行数和有序行内容 SHA256，启动真实 Platform/Runtime API 读回，再执行混合负载。无 Worker，不重放旧输入；只停止自有进程。
- 同一脚本提供仅用于验收的 app factory，包装真实 lifespan，每 50 ms 在服务进程采集事件循环调度延迟和 SQLAlchemy 连接池占用。无新增产品接口或依赖。
- `apps/platform-api/tests/test_runtime_gateway_http_matrix.py`：显式登记当前 20 条公开路由，与 FastAPI 注册集合严格相等；增加接口必须补矩阵。此前人工清点的 21 条已纠正为 20 条。

## 公开接口矩阵：done

覆盖 `/info`、Graph search/count、Thread create/search/count/get/delete/state/history、Run create/stream/get/list/join/join stream/cancel、commands、Protocol events，共 20 条。

| 检查 | 范围 | 证据层级 |
| --- | --- | --- |
| 成功响应、作用域和路径/请求体/幂等键传递、嵌套私有字段过滤 | 20 条 | 真实 HTTP router，service 响应替身 |
| 授权错误保持 403，SSE 不先返回 200；缺项目返回 400 且不调用 service | 20 条 | HTTP 边界契约 |
| 未登录 401、无权限 403，数据库与 upstream 均不被访问 | 20 条 | 真实 RuntimeGatewayService 与权限引擎 |
| 已获得项目权限仍不能访问另一个项目的 Thread | 14 条含 thread_id 的路由 | 真实 Thread 作用域校验，upstream 返回异项目归属 |
| checkpoint/subgraphs、Run 分页/筛选/重复 select、SSE 重连参数 | 3 组 | HTTP 查询类型与转发契约 |

新增 1 个矩阵测试含 117 个 subTest 分支；不是 117 个独立 unittest。网关相关 **30 项通过**，请求幂等/审批 **16 项通过**，事务边界 **3 项通过**，合计本轮定向 **49 项通过、无跳过**。先前全量 **141 passed / 3 skipped** 的记录保留，本轮没有把跳过项改算通过。

HTTP 成功替身不替代真实业务行为证明：幂等竞争、撤权、标准 resume、多 interrupt、错误/重连/取消由已有用例与 [Docker Showcase](../evidence/20260910-final-docker-showcase.json) 覆盖。矩阵只针对平台实际公开面，不宣称与 LangGraph Server 全部接口等价。

## 真实备份恢复：done

- PostgreSQL 17.11；使用匹配的本机 17 版 `pg_dump -Fc` 和 `pg_restore --exit-on-error`，不覆盖源库，不执行旧数据迁移。
- Platform **20 个业务表 + alembic_version**、Runtime **17 个表**，所有行数和规范化内容摘要完全一致；dump 前后再次读取源库一致，确认本次备份窗口数据稳定。
- 包含 9 条平台请求记录、34 个 Runtime Run、287 条 checkpoints、545 条 checkpoint_writes、108 条 checkpoint_blobs、3707 条 runtime_events。
- 恢复库真实登录成功；读回原 Showcase Thread、20 条消息、61 条历史快照、五个 Run 的原状态，并核验请求父子 Run 关联。使用保留的业务密钥以及新的 Redis namespace，未启动 Worker、未重发已提交的旧输入。
- 本次证明静止验收库恢复和历史可读，不承诺不停写入时两库跨库原子快照。正式恢复需先停止写入和 Worker、配套保存密钥；恢复后核验关联再开放写入，不能盲目重放队列。
- 数据库备份不包含 Docker workspace、外部工具副作用或 Redis 队列；本轮没有声称恢复这些文件或实现工具 exactly-once。工作区执行结果沿用已通过的 Docker 证据。

首次调用因 PATH 中 pg_dump 14 与服务端 17 不匹配而失败，改为显式 `--pg-bin`；随后验收脚本的 `Headers.update` 参数错误已修正。最终完整运行退出码 0，服务正常关闭。两次失败不计通过，也未覆盖源数据库。

## 混合负载：done

真实恢复后的 Platform API → Runtime API，本机 PostgreSQL/Redis；4 个并发请求循环，每个循环交替登录和项目列表；同时保持 2 条真实 pending Run SSE。无 Worker，因此不触发模型或 Docker 执行，结束时显式取消该新建探针 Run。

| 指标 | 实测 |
| --- | --- |
| 负载时间 | 30.875 秒 |
| 登录 / 列表请求数 | 438 / 438，共 876 |
| 错误率 / 吞吐 | 0 / 28.37 请求每秒 |
| 登录 p50 / p95 / max | 194.00 / 315.26 / 1581.76 ms |
| 列表 p50 / p95 / max | 49.64 / 108.50 / 625.94 ms |
| 两条 SSE 持续时间 | 31.485 / 31.487 秒，各 111 bytes |
| Platform PG 实际连接峰值 | 4，不含采样连接 |
| 连接池占用峰值 / 结束占用 | 4 / 0，pool size 5 |
| 服务进程事件循环延迟 p50 / p95 / max | 0.67 / 3.41 / 126.54 ms |

事件循环和连接池共 866 个样本，覆盖 app lifespan 内的读回、负载和关闭前阶段；HTTP 延迟单独统计负载阶段。验收要求是长流与普通请求共存、无请求错误、无连接泄漏并记录指标，未预设或编造生产 QPS/p95 容量目标。

## 复跑与证据

在仓库根目录使用完成的真实 Showcase 验收输出目录：

```bash
apps/platform-api/.venv/bin/python scripts/platform_backend_closeout.py \
  --source /tmp/platform-final-docker-acceptance \
  --output /tmp/platform-backend-closeout-new \
  --pg-bin /usr/local/opt/postgresql@17/bin
apps/platform-api/.venv/bin/python -m unittest discover \
  -s apps/platform-api/tests -p 'test_runtime_gateway*.py'
apps/platform-api/.venv/bin/python -m unittest discover \
  -s apps/platform-api/tests -p 'test_run_requests.py'
apps/platform-api/.venv/bin/python -m unittest discover \
  -s apps/platform-api/tests -p 'test_transaction_boundaries.py'
```

`--source` 和 `--pg-bin` 是操作者选择的本机验收路径，不是产品运行契约。输出目录须不存在，工具版本须匹配数据库；保留新隔离库和私有 dump，未擅自清理数据库。

脱敏证据：[备份恢复与负载](../evidence/20260910-backend-closeout-final.json)。私有环境和 dump 保存在权限 0700 的 `/tmp/platform-backend-closeout-3/`，环境与 dump 为 0600，不提交仓库。证据只包含表摘要、ID、计数与性能指标。

收尾检查：新增 Python 文件 Ruff F 通过，`git diff --check` 通过，本次涉及的工程文档 50 个本地链接通过。

## 最终四态

- **done**：本阶段三项收尾；既有后端功能、事务/目录重构与 Docker Showcase 验收证据继续有效。
- **deferred（用户明确决定）**：前端/浏览器与前端 SDK 验收、整套容器部署、GraphHarbor 与 LangGraph Server 完整等价性。
- 无新增产品 API、数据库结构调整或依赖升级；不需要发布新包。本轮未提交或推送 Git。
