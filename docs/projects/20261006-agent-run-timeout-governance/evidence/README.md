# 正式包验收证据

2026-10-07，使用 PyPI `graphharbor=graphharbor-runtime=0.13.0.post42`。以下日志为实际执行产物的原样副本，JSON 为验收脚本或微基准直接生成；不将旧候选 wheel 结果算作正式包验收。

| 文件 | 内容与结果 |
| --- | --- |
| `run-budget-pypi-post42-http-e2e-r2.log` | 完整12组平台HTTP，退出0；末尾JSON含场景/run_id/真实Worker PID。保留SSE断开时SQLAlchemy连接取消诊断。 |
| `run-budget-pypi-post42-rollback.json`、`run-budget-pypi-post42-rollback-r6.log` | 当前Runtime/post42切换到匹配旧源码/post41，退出0；同Run checkpoint继续、pending/历史/产物保留、普通/取消/HITL通过。 |
| `run-budget-pypi-post42-runtime-phase.log`、`runtime-docker-recheck.log` | Runtime定向125 passed/1 failed/3 skipped；Docker未启动导致唯一失败，启动后该用例重跑1 passed，详见verification。 |
| `run-budget-pypi-post42-api-phase.log` | API定向84 passed/23 subtests；与其他定向集重叠，不相加。 |
| `run-budget-api-own-lock-phase.log` | API自身冻结SDK0.4.2/Python3.14.6，85项unittest通过；异常日志来自预期故障注入。 |
| `run-budget-pypi-post42-cancel-projection.log` | 新停止确认投影/脱敏回归19 passed/13 subtests。 |
| `run-budget-pypi-post42-runtime-all.log`、`run-budget-runtime-terminal-baseline.log` | 新源码617 passed/2 failed；旧源码同样两项PTY时序失败。 |
| `run-budget-pypi-post42-api-all.log`、`run-budget-api-workspace-baseline.log` | API全量326 passed/2 failed/654 subtests；旧Runtime源码同样两项HTML预览断言失败。全量运行早于新增停止确认测试。 |
| `run-budget-pypi-post42-frozen.txt` | 独立正式包验收环境的冻结依赖清单。 |
| `release-artifacts.json` | GraphHarbor取消专项正式发布的四产物哈希清单；本轮PyPI metadata核对一致，未重复上传。 |
| `pypi-post42-verification.json` | 本轮直接查询两个PyPI版本，四产物SHA256核对通过；同时记录已安装正式环境版本。 |
| `run-budget-microbenchmark.json` | 10000次进程内预算解析/模型middleware微基准；包含版本与当时负载，没有生产SLO或供应商效果保证。 |

源码定位、本机临时目录和隔离端口保留在原始日志中，帮助复查版本与导入来源；无真实凭据。验收脚本只使用受保护的专用测试库/Redis前缀，不得换成现役数据。当前共享现役服务没有被本会话升级。

进度看 [tasks.md](../tasks.md)，判据与证据边界看 [verification.md](../verification.md)。前端F01-F10与联合Final尚未执行。
