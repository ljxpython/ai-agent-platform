# 会话与运行时数据生命周期方案

状态：已完成（done，8/8 任务；Phase与Final核验通过）。实际实现、测试及限制见 [任务](tasks.md)、[验证](verification.md)、[维护手册](../../runbooks/session-retention-maintenance.md)。

## 评审结论与职责边界

2026-10-30 用户人工批准本方案边界与实施/发布方向，替代原“配置原生 90 天 TTL + Workspace 七天等待”方案。

| 所有方 | 本次职责 |
|---|---|
| Platform | 定义闲置 30 天；用户主动打开/查看、发送续期；权限校验；平台记录保留与清理 |
| GraphHarbor | 通用到期持久化与扫描、显式活动接口、引擎一致删除、可恢复任务和生命周期交接 |
| Runtime | 应用未结事项保护、释放资源、Workspace 随会话回收、应用关联事实安全清理 |

GraphHarbor 不识别平台业务语义或应用数据模型；平台不直连引擎数据库实现 TTL。单个 Thread 只有 GraphHarbor 判定过期；平台维护任务只清本服务数据。

## 用户使用与存量

- 30 天以服务端最后一次主动查看或发送计时。后台轮询、列表刷新、自动运行、标题/metadata 更新均不续期。
- 前端在实际打开历史会话时明确报告活动，后台历史读取不触发。
- 新会话初始化策略；存量缺真实查看时间，从策略启用日起给足 30 天，分批登记，不按旧 updated_at 集中删除。
- 活跃运行、未确认释放、启用 Cron 等有保护与可见阻塞原因；不静默强杀 unknown 外部操作。

## 删除闭环

手动或到期 → 持久任务/并发冻结 → Runtime 删除前检查 → 引擎数据事务清理 → Runtime Workspace/业务清理及平台关联处理 → 确认完成。各服务各自事务，远端 I/O 不持 SQL 锁；失败保留可重试依据。

Workspace 不额外等七天；仍验证 host/tenant/project/thread/node 绑定、无未结进程/挂载/资源、可信证据与路径安全。节点失联保留清理中。未经证明的历史孤儿不伪造删除事实。

## 关联数据保留

- Run 请求按终态、受理恢复、幂等与重试窗口判定；禁止仅按 created_at 删除。
- 完成通知详情 30 天、去重凭证 90 天；origin 与事件配套保留，迟到/重复回调按墓碑处理，不能因提前删除 origin 变成 503。
- Runtime 逐表检查 terminal、cleanup/delivery/cancel 状态；unknown、cancel_requested、未确认 Lease、外部操作凭证受保护。
- 审计按既有合规策略，首期不新建分区系统。删除数据后由 autovacuum 复用空间，不承诺数据库文件立即变小。

## 维护与交付

复用现有完成通知、后台日志和 Workspace 维护能力；候选有限、短事务、语句/锁超时、作业互斥、预算、有界重入，默认预览。交付一种 Linux systemd 调度模板，其他编排不在本期。

GraphHarbor 双包最终 `0.13.0.post48` 已完成源码/候选验证、本地打包和正式 PyPI 直接发布；平台已锁定正式版本、同步契约并在专属栈完成三服务及真实浏览器验证。GraphHarbor 详情由自身项目文档维护。

平台登记策略与平台记录维护各自默认30秒预算，limit100/最大1000、预算范围1–300秒；Runtime维护使用相同默认边界，各自互斥。小时systemd模板交付 platform/runtime 两个实例，账户与路径遵循原生部署手册；本机未安装或启用。GraphHarbor Worker每轮维护后等待60秒，无独立TTL关闭开关。

Runtime先清会话关联payload，再仅对 completed 删除墓碑满24小时、无Thread/活跃Run的终态inbox做行级回收；usage、幂等、审计、Stop/外部操作凭证保留各自规则。完成删除墓碑只留tenant/project授权字段，pending保留恢复资料。逐表规则以维护手册为准。

## 验收与回退

验证真实三服务“查看/发送续期、后台读取不续期、到期删除、手动删除、Workspace 即时回收、受保护任务、迟到回调、失败重启、多实例、跨环境/租户、dry-run”关键链路。远端失联/恢复由受控fixture验证，非真实离线节点；10轮维护耗时是隔离链路样本，不是生产容量压测。

migration014 拒绝破坏性downgrade，旧post45已实测被schema head门禁拒绝启动。冻结时需暂停相关写入口、GraphHarbor Worker和apply CLI，仅停平台两个timer不能关闭引擎TTL；保留任务和墓碑，恢复匹配post48续跑已验证。已清理文件不承诺恢复。不改主工作区或现役环境。
