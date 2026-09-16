# 会话清理、K19超时修复与V08故障验收

日期：2026-09-16。用户明确授权清空本地Agent对话数据、删除备份恢复测试数据，并验证K19和防重复付费。不提交代码，不实施前端，不做多机压测。

## 执行范围与状态

| 事项 | 具体内容/代码 | 状态 |
|---|---|---|
| K19 | apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py:middleware，单次完整模型响应30→120秒，父/子Agent共用该预算；不修改通用middleware或GraphHarbor | done：实现与单项真实链路通过 |
| V08 | apps/runtime-service/tests/services/dearflow_agent/test_p5_media.py:test_provider_accepts_but_drops_receipt_without_second_submission | done：真实SDK/HTTP断连/PG重提验收通过 |
| 当前对话清理 | Runtime graphharbor_acceptance中的会话/Run/事件/checkpoint/消息/回执/线程技能绑定；Platform SQLite中的run_requests及对话审计 | done：停写清理完成、各表为0，配置摘要不变 |
| 备份恢复清理 | 本轮p7_restore_probe隔离库、两次p7-backup临时目录、空/tmp/p7.dump | done：本轮恢复库与备份均已删除 |
| 保留 | 账号、项目、模型/工具配置、Agent注册、独立记忆和技能版本、非本轮创建的其他数据库 | 不属于对话清理 |

## 变更理由

K19此前已经发布报告，最终模型调用在本地ModelCallTimeoutMiddleware的30秒边界连续失败。采用有界120秒预算容纳推理模型完整响应，保留模型/工具调用次数上限，不引入无限重试。超时和取消语义沿既有中间件测试；真实链路日志/tmp/p7-k19-budget-recheck.log。

V08模拟“供应商已接单但HTTP回执丢失”，不调用付费服务、不伪造成功产物。必须证明同一scope/幂等键跨Run、并发重试和查询后，供应商仍只接单一次，存储attempts=1/status=unknown。并不保证换幂等键不会产生新请求，也不声称供应商退款。

## 已执行证据

- /tmp/p7-v08-real-http.log：3 passed、13 deselected，80.12s。真实OpenAI SDK请求本地HTTP服务；供应商接单后不返回HTTP响应并关闭TCP。随后重建工具/存储、切换Run并发重提3次及查询，接单账本仍1条，PG attempts=1/status=unknown，无生成产物。其余两项覆盖租约fencing/作用域/同键去重与取消后的未知结果。
- /tmp/p7-model-timeout.log：2 passed、9 deselected，26.42s；验证超时仍生效，CancelledError向上传播。
- /tmp/p7-closeout-lint.log：本轮修改的两个测试文件Ruff通过。
- /tmp/p7-k19-budget-recheck.log：Run成功完成，但测试断言未通过（336.21s）。原因是提示以创建候选开头，实际读取skill-creator，断言要求find-skills。保留失败记录，未放宽断言；改用明确的发现技能/导入候选/再次查询场景，单项重验日志/tmp/p7-k19-discovery-recheck.log。
- /tmp/p7-backup-cleanup.json：p7_restore_probe恢复测试库已删除；两次p7-backup目录已删除，包含338099654字节的成功备份与空失败备份；/tmp/p7.dump空文件已删除。保留不含凭据/原文的恢复验收摘要，不再保留这些原始数据库副本。

## K19最终结果

/tmp/p7-k19-discovery-recheck.log：1 passed、19 deselected，269.27s。thread=275f08d7-96f5-4944-9155-bc6fcbe83db8，final_run=b2c4030e-d174-4520-aa3a-15f0302729db；报告SHA256=1b4ea8d295b9b77dcc8f52554062167dd39e90a73d2d8d7863966dc921669367。只读复核确认find_skills两次执行，最后查询到p6-test-helper且status=candidate，没有启用。

本次证明已授权的本地目录发现/候选导入/查询/报告链路，未覆盖GitHub远端import_skill，因此不把远端导入标记为已验收。新场景保留必须读取find-skills的断言，没有通过关闭断言获得成功。清理完成后这些测试会话将不再可在线回看，保留脱敏日志结论与摘要。

## 对话清理执行结果

采用已核实表名的事务TRUNCATE（没有CASCADE），只对本地graphharbor_acceptance执行；Platform对已核实SQLite文件执行run_requests清空与按会话路径/动作筛选的审计删除，随后VACUUM。执行前停止三个后端进程；不删除账号/项目/模型/工具/Agent配置，保留独立memory、skill_versions和Store，逐项摘要对比不变。

| Runtime表 | 清理前行数 | 清理后 |
|---|---:|---:|
| runtime_events | 105568 | 0 |
| run_leases | 0 | 0 |
| retry_counters | 98 | 0 |
| runtime_message_inbox | 11 | 0 |
| checkpoint_writes | 15549 | 0 |
| checkpoint_blobs | 4303 | 0 |
| checkpoints | 9481 | 0 |
| dear_external_tasks | 16 | 0 |
| dear_skill_bindings | 9 | 0 |
| runs | 947 | 0 |
| threads | 564 | 0 |

Runtime数据库大小：1132877491 → 11146931字节（约1.13GB→11MB）。Platform删除run_requests 424条、对话审计14906条。证据/tmp/p7-conversation-cleanup.json；原始操作为本地一次性管理操作，没有加入生产请求接口或GraphHarbor源码。

恢复测试库p7_restore_probe和本轮两个p7-backup目录已移除。其他非本轮创建的数据库未删除，工作区文件不属于本次“数据库内对话”清理。历史验收thread/run现在已删除，后续复查使用本文脱敏摘要；不能再将历史ID当在线可访问会话。

前端无新增开发或契约变化；当前页面若停留在已删除历史线程，需返回会话列表并刷新。页面验收仍deferred。

最终恢复核对：runtime-api /ready与platform-api /_system/health均HTTP200，runtime-worker进程恢复；重启后threads/runs/runtime_events仍全部为0，p7_restore_probe不存在。git diff --check通过。
