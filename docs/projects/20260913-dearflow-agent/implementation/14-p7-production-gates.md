# P7 生产门禁首批验证

日期：2026-09-15

## 范围

本批只做后端生产门禁，不实现平台前端 F7。K23、音视频、大文件和真实外部部署按既有范围后置或阻塞。

## 结果

| 门禁 | 证据 | 结果 |
|---|---|---|
| V01/V02 | `apps/runtime-service/tests/durable/test_backend_isolation.py`、`test_resource_bindings.py`、`test_resource_reconnect.py` | 9 passed，2 skipped；Runtime 隔离、资源绑定与重连通过；跳过项依赖外部环境 |
| V02 | `apps/platform-api/tests/test_security_boundaries.py` | 5 passed；授权边界通过。测试使用短测试 JWT，产生库警告，不代表生产密钥配置 |
| V03/V04/V05/V11/V12 | `apps/platform-api/tests/test_runtime_gateway_*.py` | 45 passed；网关契约、文件、图片、事件脱敏、治理私有路由和错误边界通过 |
| V06/V07 | `/tmp/dear-p6-runtime-fixed.log`、K17 真实 E2E | P6 定向 8 passed；K17真实链路通过。K18—K21仍需完成或记录外部模型结果 |
| V08 | P5/P6 ExternalTaskStorage实现与定向测试 | 代码具备幂等/unknown语义；未做真实付费供应商演练，partial |
| V09/V10 | 本地 stack 重启与 Runtime 测试 | 单进程重启/重连有证据；多机、数据库备份恢复和资源压力未验，partial |
| F7 | `frontend-handoff.md` | 后置，未实现、未验收 |

## 结论

当前 P7 不能标记整体完成。V01—V05、V11、V12 的确定性后端门禁通过；V06—V10 和 F7 仍有部分验证或外部依赖。生产发布前必须完成真实模型技能批次、备份恢复/资源压测、外部任务供应商演练，并由前端进行 F7 人工验收。

## 后续定向结果

- Runtime 子 Agent、P2 交互、文件契约：`/tmp/p7-runtime-contract.log`，6 passed、1 skipped、80.81s。
- K18 失败根因是验收测试把技能 ZIP 当网页 ZIP 解析；已修正 `tests/services/dearflow_agent/skills/platform_batch.py`，K18 现在按 `SKILL.md` 校验包内容。该修复尚未重新消耗模型请求。
- K19 失败根因是模型在已完成候选创建与 `find_skills` 后写报告阶段超时；服务端状态显示候选存在且 inactive，不能把超时冒称链路通过。记录为模型/长运行阻塞，代码链路已有确定性覆盖。

## 用户指定收尾验收（2026-09-15）

- **V08 外部任务**：`apps/runtime-service/tests/services/dearflow_agent/test_p5_media.py`，3 passed、1 skipped、56.19s。ACK/重启后的任务存储与幂等路径通过；真实供应商重复付费演练仍不具备条件，保留 partial。
- **K18**：已修复 E2E 验收器对 ZIP 类型的错误假设，代码检查通过；之前真实运行已完成候选、审查、评估和发布前流程，失败只发生在产物按网页 ZIP 解析。修复后的真实模型复验尚未重新执行，状态 partial。
- **K19**：真实运行完成候选创建与 `find_skills`，候选状态为 inactive；最终报告阶段因模型 `TimeoutError` 失败。状态 blocked（模型长运行），不是服务端授权或技能导入错误。
- **数据库备份恢复**：本地恢复演练未完成。当前本机 `pg_dump` 为 14.17，而目标 PostgreSQL 为 17.11，工具拒绝执行版本不匹配；没有安装新工具、没有修改数据库。状态 blocked，需使用 PostgreSQL 17 客户端后再执行 `pg_dump/pg_restore` 并比对表行摘要。
- **多机压测**：按用户决定从 P7 范围移除，不再作为门禁。

## 复核纠正：K19、数据库客户端、V08

- K19失败Run为5b72222e-8d46-4a5e-b140-497a25b9a033，模型节点ceaee32f-511f-ba6d-b75e-e8cd224e9521。Worker堆栈明确落在runtime_service/middlewares/model_call_timeout.py:21的asyncio.timeout；Dear组合根agent.py:206设置30秒。候选、find_skills及报告发布已成功，失败是后续模型调用超时；先前“写报告阶段/供应商阻塞”描述不准确。日志记录同一Run三次该异常，不能由此认定供应商故障。
- 本机已安装PostgreSQL 17.11，客户端位于/usr/local/opt/postgresql@17/bin；PATH上的/usr/local/bin/pg_dump为14.17。此前只查/opt/homebrew而遗漏本机/usr/local安装前缀，误把客户端选择问题当环境缺失。已使用17.11绝对路径启动备份恢复，当前尚待完成，不需要安装或修改全局PATH。
- V08“重复付费演练”应指通过可控故障模拟供应商接单但回执丢失，验证同幂等键不再次提交且保持unknown；不要求真实重复购买或破坏供应商服务。既有3 passed/1 skipped只证明所覆盖路径，不以“必须真实扣费”为上线门禁。
- K18已启动单项真实复验，日志/tmp/p7-k18-recheck.log，thread=39dc6844-dec3-417a-976a-56b1f8176f04；终态待回填。

### K18复验通过

/tmp/p7-k18-recheck.log：1 passed、19 deselected，613.76s；最终run=434c9330-073f-4be1-85d5-b52e0cb22d97。ZIP摘要ac073436fe99b83ca7a2e7a4a749c77862f2a0daa3d1d3bf259432d390bcb21c，报告摘要18170581b1c146756dff74dec0e24863b32e23fc207baf2f7bbe5b96762f40ad。候选/审查/文本评估/产物授权下载通过，不代表脚本基准或自动启用已验收。

### PostgreSQL 17备份恢复结果（2026-09-16）

使用/usr/local/opt/postgresql@17/bin/pg_dump与pg_restore完成Runtime数据库完整备份并恢复至本地隔离库p7_restore_probe。备份文件约336MiB，位于本机私有临时目录，权限600，不提交仓库。恢复库22张public表、103146条runtime_events、0个无效索引；dear_external_tasks=16、dear_memory=1、dear_skill_bindings=7、dear_skill_versions=3。

证据/tmp/p7-restore-evidence.json：备份前已完成K17线程35f61b7e-bbe6-4a56-8e9b-cc7cb1fea212的threads(1)、runs(4)、runtime_events(859)、checkpoints(79)、checkpoint_writes(127)、checkpoint_blobs(25)逐表全部行SHA256与源库一致。Runtime数据库恢复及该历史会话完整性验收通过。

边界：备份期间K18写入源库，因此取消了无效的“持续变化源库全量相等”检查，改为固定历史线程校验。未声称全库逐行一致；未恢复Platform数据库、工作区文件或演练跨库时间点一致性。隔离库保留供检查，没有切换运行服务连接。
