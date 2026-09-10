# 全服务事务规范化与必要目录精简

日期：2026-09-10。用户已批准：先完成同步 SQLAlchemy 的事务/线程规范，再只精简明显多余的层级。保持 HTTP 契约和数据库表结构不变；不新增异步驱动、事务框架或兼容包。

## 实施与验收

- 删除伪异步 UoW；纯 CRUD 使用同步 service/endpoint，异步编排将完整 Session 生命周期交给线程池。
- 网络 await 与事务分离，所有实际 DB 调用（含认证、策略、审计和依赖）检查线程边界。
- 简单模块按 router/schemas/service/models/repository 组织；复杂网关保留必要分工。删除未消费 Protocol 和纯重导出层，更新所有调用者。
- 验证提交/回滚、异常关闭、线程归属与网络等待期间无事务占用，执行平台全量和真实 Runtime/Showcase 复验。

状态：事务与目录范围 done；本地真实链路 done，完整 Docker 工具复验已通过。具体证据与边界见文末。

## 已落地

- 11 个业务模块的同步数据库用例改为 def；纯 CRUD 路由和网关依赖使用 FastAPI 的同步线程池。异步网关的授权、默认值与模型引用查询通过 run_in_threadpool 执行，Run 请求记录已有的完整事务继续复用。
- Agent 创建先异步查询真实 schema，再在线程池中保存；Graph/Tool 刷新先完成授权/签发、关闭事务，再等待网络，最后独立事务更新快照。
- core/db/uow.py 删除，session_scope 直接返回 sessionmaker.begin()。用户和服务账号认证、审计写入都离开事件循环；审计收尾使用 AnyIO CancelScope 保护，保持取消结果可追溯。
- 七个简单模块压平，48 个实现文件迁到模块直属位置；旧四层导入包移除，初始化、路由、跨模块消费者和测试同步更新。删除 8 个无实际作用的仓储 Protocol，保留真正使用的外部能力边界。
- 三份活手册已重写，删除强制四层、Operations 和队列预留等失效规则。复杂网关/catalog/IAM 保留必要分工，不为了统一目录而搬动所有模块。

## 验证记录

第一轮 142 项：4 failures、4 errors、3 skipped。原因是旧 AsyncMock 契约、旧依赖 asyncio.run 调用及 SQLite 内存库跨线程不共享；已按真实同步契约修正测试，目录刷新测试改用临时文件数据库。
第二轮完整平台回归：144 项，141 passed、3 skipped，207.623 秒，无失败/错误。后续审计取消保护与新增线程测试继续定向复验，真实 Runtime/Showcase 复验进行中。

新增事务边界 3 项定向复验通过（4.282 秒）：HTTP CRUD/异步刷新 SQL 离开事件循环、Session 创建/查询/提交/关闭同线程、网络等待前关闭事务、原生提交/异常回滚与连接释放、已取消请求仍在线程池写审计。Ruff F 与异步数据库作用域扫描通过。

干净 wheel 构建及隔离导入通过：48 个新位置文件全部存在、旧路径/UoW/Operations 不存在，应用工厂可创建，ORM 仍为 20 表。首次增量构建发现本机旧 build 缓存混入删除文件，已将旧缓存移至临时目录再干净构建；未发布新包。

真实验收第一轮在已完成三进程重启、标准审批后，一次 GET Run 状态触发客户端 45 秒 ReadTimeout；上游日志显示请求最终 200，无 SQL/审计异常。该轮不计完整通过，保留原 Thread，恢复同一隔离环境继续读取/审批，不重发原始输入。验收脚本仅对 GET 读取超时最多重试 3 次，写请求不自动重放。

恢复尝试曾因 PostgreSQL 建连超时导致启动失败；随后独立 SELECT 1 成功（3.41 秒），pg_stat_activity 无 idle in transaction。继续重启自有进程恢复原 Thread，不操作其他服务或删除数据库。GET 重试/POST 不重放的独立检查通过。

用户告知已禁用 Docker，当前使用本地 PostgreSQL/Redis。二者原本就是本轮真实联调的基础设施；Showcase execute 另依赖 Docker 工具沙箱。已停止新一轮完整 Showcase 复验，不改为宿主机执行。独立本地 PostgreSQL 事务提交、异常回滚、线程池事务与连接释放验证通过，证据见 [真实 PG](../evidence/20260910-transactions-postgres.json)。完整 Docker 工具结果待确认验收范围后记录，不计成功。

## 最终判定

- **done：事务规范化与必要目录精简。** 平台全量 144 项（141 passed、3 skipped），新增/补充事务边界 3 项通过，原生 PostgreSQL 事务验证与干净 wheel 隔离导入通过。
- **done：本地 PG/Redis 真实 Runtime 链路。** Thread db150c90-1ccd-4b6a-afdc-eb1996f69f74，Run d35719ed-cb20-46ca-99a8-18bf0a6e8f25 为 success；真实只读 Showcase、62 秒排队、密钥轮换、取消重发、幂等冲突、跨项目隔离通过，SSE 335102 字节。[证据](../evidence/20260910-transactions-local-runtime.json)。
- **blocked：本轮完整 Docker 工具结果复验。** 用户停用 Docker，未改为宿主机执行；此前完整流程在状态读取超时后中断，恢复时原 Run 为 error，不算成功。该限制不影响已取得的事务/目录及本地 Runtime 证据。
- 前端与整套容器部署仍 deferred；本轮不改 HTTP 契约及数据库表结构。无新包发布、无 git 提交/推送。

正式验收脚本新增 --read-only 模式，保留真实目录/模型/幂等/排队轮换/SSE/隔离检查，明确不计 Docker 执行与审批重启；本轮实际证据来自同流程的临时只读探针。运行时仍需指定隔离 Platform 数据库、Runtime DATABASE_URI/REDIS_URI 和不存在的输出目录。

## Docker 恢复后的最终复验

用户重新启动 Docker 并要求复验。使用本地 PostgreSQL/Redis、新隔离平台库及正式 post26 Runtime，完整 Showcase 通过：Thread `02c4e533-350b-462d-ba2c-40b193b9a6c7`，最终 Run `8cb0cb80-eb75-4831-9fcd-7a9b45adf9f1` success。

- 62 秒排队与凭据轮换、pending 并发拒绝/取消重发、同 key 复用/冲突通过。
- Platform API、Runtime API/Worker 三进程重启后消息与 interrupt 一致；禁用 Agent 审批拒绝，重新启用后标准 resume 恢复。
- 真实 edit_file/write_file/execute 审批通过；Docker 禁网络、只读根文件系统、非 root 用户等原沙箱限制保持。
- 独立 Docker 执行实际调用了 1 个生成的回归测试函数，输出 `1 regression test executed`、`Total sales: 43.50`，退出码 0；result.txt 同为 43.50。
- 原验收命令仅执行 python test_report.py，会空跑 pytest 风格函数；本次补上 test_ 函数调用，并独立复验，不将空跑记为测试通过。
- SSE 97501 字节，跨项目拒绝、Operations/resync 404 通过。探针正常结束并停止自有进程。

本节替代此前 Docker blocked 状态：[完整证据](../evidence/20260910-final-docker-showcase.json)。事务与目录调整后的完整后端主链路为 done。

## 原工程仍需如实保留的验收缺口

不能据此宣称除用户后置项外全工程全部完成：04 的并发登录/列表与长 SSE 共存负载记录（p95、错误率、连接与事件循环指标）、真实备份恢复演练尚无证据；02/G1 的全公开 Runs/commands/读面完整矩阵仍未逐项闭合。已有关键路径、故障回归和多 interrupt 契约不等于所有边界穷举。三项未被用户明确后置，保留 partial。

用户明确后置的前端/浏览器、整套容器部署和 LangGraph Server 完整等价性仍 deferred；Docker 工具沙箱验收不等于整套容器部署验收。

### 三项缺口已收尾（2026-09-10）

上述三项 partial 已被后续真实验收关闭，见 [13](13-backend-acceptance-closeout.md)。用户后置项仍为 deferred。
