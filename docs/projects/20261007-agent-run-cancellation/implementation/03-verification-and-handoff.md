# 验证与交接实现记录

## 日期

2026-10-07

## 相关任务

- Task 5.1–5.2
- Task 4.1–4.2（交接）

## 改动文件与函数

- `scripts/verify_thread_stop.py:45::main()`：在隔离PG/Redis中启动真实Platform API、GraphHarbor API/Worker与Runtime组合根；以lease/固定回执/checkpoint/inbox/审计对账，15条场景。故障包括HTTP未知、Runtime重启、500目标10秒上游等待超时后恢复同stop_id。只使用合成模型/身份，无付费调用或现役写入。
- `apps/runtime-service/tests/fixtures/run_control_platform.py:35::graph()` 与 `platform_app():159`：沿reference/workflow/showcase/dearflow真实工厂构图，仅替换模型/供应商，保留middleware/子图/工具装配与ACL；不是用mock router证明执行。
- `apps/runtime-service/tests/fixtures/tool_error_platform.py`：补支持合成子Agent工具回执，复用既有可执行fixture，不另造Agent执行器。
- `scripts/verify_stop_migrations.py:29::seed()`、`snapshot():88`、`main():144`：候选双wheel/head011 HTTP、Runtime downgrade保留回执/再upgrade、真实pg_dump/pg_restore、引擎回退保留取消意图、正式旧post41单Run cancel、引擎再upgrade，共7条。
- `docs/projects/20261007-agent-run-cancellation/evidence/{acceptance,migrations,packages}.json`：保存脱敏回执、7条恢复结果、候选来源/双包版本/哈希/head；不保存secret/原始日志。实际临时结果原件见verification环境记录。
- `docs/projects/20261007-agent-run-cancellation/frontend-handoff.md`：规划建议更新为实际三接口、StopRequest v1上限/null语义、六phase/unknown原key、502存储错误、审批边界快照、轮询/新Run竞态、报告纯文本与F01–F10。
- `docs/{CONTEXT,FEATURES,CHANGELOG}.md`、`docs/standards/{delegation-jwt,error-envelope,README}.md`、Platform网关/审计活标准、Runtime开发标准：同步源码能力与blocked部署边界，Delegation仍draft。
- `docs/lessons/runtime-service.md`、`docs/lessons/index.md`：经用户“确认写入经验库”，补审批ID/原快照和同版本候选/正式来源两条经验；条数2→4。

## 关键前后变化

之前handoff是待实现方案；现已按DTO/路由、安全回执核对，将执行状态、资源确认与HTTP未知分开，报告不走AIMessage/自动建议管线。Runtime正式锁仍post41；唯一post43四产物/冷安装/临时锁接入已验，但正式上传待明确指令，不把候选通过写成正式上线。

HITL真实fixture最初携新配置被400拒绝、非ID映射被409拒绝；修正为 `{"command":{"resume":{"<当前 interrupt ID>":{"decisions":[{"type":"approve"}]}}}}` 并沿原快照恢复。未放宽现有审批规则。此教训已获得经验写入确认。

## 结果

15 条真实 HTTP 场景、7条候选迁移/备份/回退通过；Runtime 25项、API 66项/376子测试通过，保留1条已在HEAD复现的无关fatal文案断言失败。最新静态检查结果写入[Phase验证](../verification.md)，不重复跑已通过场景冒充整体Final。

本轮post43包版16场景和真实Docker后端/PPTX3项、7条恢复通过，B01解除。Showcase/DearFlow取消前核实PG active、开始文件与daemon running容器，取消后持久cleanup_confirmed、无lease、inspect不存在及8秒后无延迟写入。夹具返回平台DEFAULT_TENANT_ID，避免将数据库tenant UUID误用作执行workspace scope。

GraphHarbor双包pyproject/check_versions/uv.lock/compatibility-matrix已准备post43；迁移测试改断言011与取消表存在，跨实例fanout测试有界跳过合法recheck再核实interrupt。主回归297 passed/8 skipped、Cron3 passed；3.12契约124 passed/4 skipped，3.13冷安装wheel150 passed/4 skipped。四产物及源码相对正式post42仅5处新增/修改见packages.json和release-handoff。

发布前收口：四产物twine check全部PASSED，SHA256复核一致；check_versions、兼容基线和uv lock --check通过。同步GraphHarbor项目/CONTEXT/FEATURES/CHANGELOG与REST契约的旧候选和Docker状态。30份两仓文档、291个相对链接、21个闭合代码块与9份JSON检查无新增错误；3条使用方FEATURES既有断链保留并以HEAD核实。PyPI双包仍为正式post42，post43未上传；发布指令确认后才更新正式源锁。

仅B02正式上传/正式源锁接入与同事前端待办；整体Final待条件满足。tasks是进度来源，未提交、发布或部署现役。
