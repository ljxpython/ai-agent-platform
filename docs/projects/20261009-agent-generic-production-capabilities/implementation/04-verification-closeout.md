# 后台任务验证收口

## 改动时间与范围

2026-10-09；T04/T05/T08 的阶段验证与交接。生产实现仍按原 event/key 对账，未改变未知派发的处理，也未修改前端。

## H/I 轮问题与修改

H轮首个完成回调在平台耗时11596ms，超过Runtime默认10秒ACL超时，随后Runtime保留unknown/inflight。平台HTTP200与调用者收到回执是两件事；此轮不能证明HITL等待通过，也不能自动再次POST。

I轮在Runtime就绪等待超时；Runtime在收尾前才记录ready，没有业务异常栈。宿主极高负载仅作为环境证据，不能声称生产负载验证通过。

J轮到达HITL等待和完成Run成功，但Stop摘要包含两个已存在目标，测试只预期正在运行的一个。`request_stop()` 还捕获accepted通知并只读确认其Run终态，这是现有保守清理语义；测试改为断言两项confirmed、旧成功结果与原Run ID保持、后续任务不被纳入。整条验证未通过前不将局部断言算为E06完成。

- `apps/runtime-service/tests/e2e/test_background_tasks.py::test_completion_waits_for_hitl_and_new_tasks_survive_old_stop()`：仅此隔离测试设置60秒ACL超时和360秒冷启动等待；仍使用当前interrupt ID显式恢复，等待Workspace同步文件后完成命令。
- `apps/runtime-service/tests/services/dearflow_agent/test_tool_error_platform.py::stack()`：Runtime与Worker就绪等待读取既有options，默认仍180秒；复用同一启动/退出fixture。
- `docs/projects/20261009-agent-generic-production-capabilities/verification.md`：保留失败轮、补充证据覆盖矩阵与资源收口；实际测试结果以Phase记录为准。

这两项只影响可选验收fixture，不改变生产ACL默认值、lease、命令期限或原生Run幂等。最终镜像已包含的生产实现没有再次变更。

## 资源收口

H轮53751、早期B轮60736/C轮51499的隔离PostgreSQL已通过各自数据目录执行fast shutdown，证据文件保留。I轮fixture正常收尾；本轮后续资源在测试退出后逐项盘点，只清理当前专项拥有的容器和临时服务。

不对Docker执行全局prune，不停止其他worktree服务；现役 `llmops-db`、`llmops-weaviate`、`llmops-redis` 保留。没有Git提交/推送、生产迁移或现役启用。

## 实际验证

- K轮HITL通知与固定Stop后新任务整条：1 passed，724.02秒；路径与安全DTO证据见verification.md T04 Phase。
- 55个变更Python文件Ruff check/format通过；经验入库后27个变更Markdown按仓库check_file规则零错误；git diff --check通过。专项11份文档/23本地链接/4 JSON示例通过，44项冻结验收与证据矩阵无缺项。
- 最后容器盘点两类专项标签均为0，K轮隔离服务已全部退出，无本专项验证进程遗留。
- 全项目保持blocked：B01需引擎正式只读接受回执；后端Final及前端联合验收未完成。

## 经验沉淀

用户于2026-10-09明确确认“写入上述经验”。已将回调200与收到回执的区别、先退应用迁移再启动旧源码、Docker local日志实际盘占用定位、受保护后台工作目录四条写入 `docs/lessons/runtime-service.md`；索引条数由4更新为8。
