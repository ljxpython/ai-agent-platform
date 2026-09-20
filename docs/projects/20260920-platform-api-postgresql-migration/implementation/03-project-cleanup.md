# 项目清理及 Graph / Agent 范围核验

2026-09-20，用户授权只保留一个 test 项目，检查清理脚本并排查 Graph / Agent。作为本地 PG 运维补充执行，未改变全局目录或授权默认值。

## 实现

- `apps/platform-api/scripts/database.py`：新增 `clean_projects()` 和 `clean-projects`，明确保留活动项目 UUID；默认预览，执行要求 local/dev、数据库名称确认、事务和项目表写锁；按现有项目软删除语义更新状态及时间。
- `scripts/cleanup_env.sh`：新增独立 `--keep-project` 模式；测试报告由整目录 `rm -rf` 改为 Git 未跟踪文件清理，避免删除跟踪文件；显示缓存大小，旧 Runtime 工作区清理要求停写。外部工作区不自动删除。
- `apps/runtime-service/tests/services/dearflow_agent/test_platform.py`：测试项目创建成功立即注册 ExitStack 清理，成功或异常退出均调用项目 DELETE API；此前缺少统一清理是大量 `dear-p1-verification-*` 活动项目残留的来源。
- `apps/platform-web/src/modules/graphs/pages/GraphsPage.vue`：纠正“当前项目已授权”文案；实际接口返回全局目录。
- `apps/platform-web/src/modules/agents/pages/AgentsPage.vue`：说明按全局 Graph 自动补齐项目 Agent，配置仍按项目独立。
- `apps/platform-api/tests/test_project_cleanup.py`：真实 PG 临时表覆盖 UUID/活动状态保护、预览无写入、同名不同 UUID、重复执行及事务回滚。

## 实际执行

备份：`apps/platform-api/.data/backups/20260920T015830Z-project-cleanup/platform.dump`，目录 0700，文件 0600。相邻私有 JSON/日志保存执行前后计数及命令输出，不提交备份。

保留 `test`：`5a5b7239-43e3-40e6-bba3-e64d96057607`。执行前 98 个活动、21 个已删除项目；本次软删除 97 个，最终 1 个活动、118 个已删除。4 个 test Agent 完整字段核验一致。

## 其他数据盘点（本轮保留）

| 数据 | 盘点 | 建议 |
| --- | --- | --- |
| 刷新令牌 | 执行前 344 条，其中 127 条过期或已撤销 | 可按到期/撤销条件和保留期清理，不能清空有效登录会话 |
| Agent / 成员 | 全库 171 / 119 条 | 软删除项目的历史仍保留；物理清理需要单独跨库方案 |
| 请求 / 审计 | 执行前 23 / 1024 条，验证后审计 1032 条 | 有幂等和审计意义；已有显式流水清理模式，不默认删除 |
| Runtime | 10 个线程，23 个运行（15 success、8 interrupted） | 包括可恢复中断运行，不能当作纯垃圾直接清库 |
| 迁移测试数据库 | 6 个 `platform_migration_test_*` 库 | 压测、恢复及权限验证副本；另行确认保留期后按完整名称处理 |
| 工作区 / 备份 | 当前真实工作区在配置的外部路径；迁移备份仍在回退保留范围 | 不因旧 `.runtime` 目录清空就声称真实工作区已清；备份保留 |
| 全局目录 | 4 个 Graph、7 个模型 | 共享配置保留 |

## 验证边界

HTTP 对比两个真实项目：Graph 目录相同；四组同名 Agent 的 UUID 集合不相交。清理后项目列表 total=1，test Agent 未变，已删除项目 Agent 接口拒绝访问。数据库计数和保留对象字段再次核对。四个本地进程仍运行且健康。

这次没有改变授权默认启用或自动创建策略，也没有清空 Runtime、删除历史项目行、取消中断运行、清除令牌及测试库。此次项目清理是软删除，不应描述成物理清库。
