# 经验库索引

> AI 读取规则：不需要全部加载。开始处理某个服务/领域改动前，按需读取对应文件。

| 文件 | 覆盖范围 | 条数 |
|---|---|---|
| [ai-workflow.md](ai-workflow.md) | AI 工作流、Harness、Skill 设计、文档规范与后续验收同步纠偏、Worktree 隔离/配置复用/审计验收、发布协作与宿主机生产Systemd沙箱实战 | 13 |
| [cross-service.md](cross-service.md) | Platform API、Runtime Service、GraphHarbor 跨服务契约、Delegation及长来源取证、checkpoint 游标分页与默认租户对齐 | 5 |
| [runtime-service.md](runtime-service.md) | runtime-service 服务内部、模块导入、工具治理、审批/回调恢复、迁移链保留、混合测试环境、聚合负载、Docker日志、全链路性能验收、同快照脏记录清理、远端文件路由与容器/数据分开回收、零隧道单向自治、LLM空内容防护、流式工具名增量兼容、内部CHAIN状态采集去重、独立目标恢复、正式包来源、故障夹具预算与缓存实验判定/记忆时效、ToolNode 异常封装、OTel 活跃 Span 判活与 Trace Tag 限长 | 28 |
| [platform-web.md](platform-web.md) | 权限状态、刷新作用域、组件 watch 响应式解构防崩、撤权回归与非 HTTPS 剪贴板降级 | 5 |

评测开发经验维护在关联 `mlflow-eval-platform` 仓库的 `docs/lessons/eval-architecture.md`（用户已确认），覆盖原生页面复用、结果契约、取消幂等、配置与审批恢复、Dataset冻结、源码／预算版本、审批预算、文件哈希职责、长Trace有界完整取证及客观／语义验收按需选择。2026-11-21修订完整取证的条数/字节预算和权限边界；软内存阈值校准、Loki高基数标签与恢复验证维护在该仓 `docs/lessons/sshmy1-deployment.md`。本仓只保留引用，不重复维护。

## 新增经验的流程

1. AI 犯了错，用户纠正
2. AI（或用户）将教训蒸馏为 ≤4 行，格式：场景 + 错误 + 正确做法 + 日期
3. 判断级别：
   - 任何场景都会犯 → 写进 `AGENTS.md` 的「严禁行为」章节（≤10 条上限）
   - 特定服务/领域才会犯 → 写进 `docs/lessons/{domain}.md`
4. 如果是新 domain 文件，更新本索引文件的表格行
