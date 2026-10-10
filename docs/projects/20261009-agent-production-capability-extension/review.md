# 人工评审单

> 本方案是治理改动。用户于 2026-10-09 在会话中明确批准实施、GraphHarbor 专项及本地凭据直接发布；本轮推进全部非前端任务。实际前端与浏览器验收交接同事，不据此宣称全栈完成。

[官方Server核对](07-langgraph-server-boundary.md) 确认GraphHarbor可以承载原生webhook、安全部署策略、通用身份与扩展。以下Outbox/projector/HMAC/严格ACK是本项目建议增强，不能以“官方已有”为理由视作批准；普通兼容webhook与平台受管契约必须明确区分。

## 待决事项

| 编号 | 建议决定 | 为什么需要人工决定 | 影响/批准标准 |
| --- | --- | --- | --- |
| R1 架构与外部依赖 | 原生webhook兼容 + Engine可靠Outbox → API；必要时Runtime纯projector | 涉及跨仓库核心执行与生产数据模型 | 先核对既有安全event/principal；冻结必要通用hook、兼容/受管payload、原子终态与正式版本 |
| R2 输入收紧 | 平台公网Run拒绝webhook/私有callback字段 | 改变现有透传行为，可能影响外部调用方 | 调用方清单、错误码与迁移通知；不静默覆盖、不变相公开自定义URL |
| R3 可信来源 | 新增可选受签origin_ref和schedule来源回填 | Delegation严格白名单、安全/身份契约变化 | 旧token/旧cron兼容，factory前fail/earlycallback/撤权已覆盖；无公开metadata信任 |
| R4 通知对象与范围 | 当前项目发起用户/定时owner；service-account仅历史/审计 | 是用户可见性/隐私策略，不能由AI按项目成员广播 | 只通知发起者，其他共享读取者仅历史；跨项目聚合、渠道推送后置 |
| R5 密钥与传输 | 正文HMAC+key_id+30s窗口+固定HTTPS目标/CA | 新生产认证与密钥轮换边界 | key→runtime绑定、不跟随redirect、双key轮换、time drift/重放验证 |
| R6 保留与删除 | 自动retry24h；pending/dead-letter至少30d，event30d/tombstone90d | 数据保留、恢复和删除策略 | pending不CASCADE、超期显式discard审计、删除不复活、最长run与重放来源仍在 |
| R7 SLO与容量 | 初始callback20/s、feed10req/s、100k事件；p95处理200ms、正常投递10s | 生产容量与通知体验需要实际业务基线 | 实测后调整/批准；不能把browser poll时间混作callback延迟 |
| R8 分工/发布门禁 | 后端与引擎共同交付；前端同事验收才全链路done | 多人跨服务联调与发布责任 | 负责人/环境/正式包/rollback/同事验收时间明确；发布生产另有授权 |

前端的详细交接入口：[05-frontend-handoff.md](05-frontend-handoff.md)。已后置范围不能被临时扩张为新总线/渠道/插件市场。

## 批准记录

| 日期 | 人类评审人 | 编号与范围 | 结论 | 条件/变更理由 |
| --- | --- | --- | --- | --- |
| 2026-10-09 | 当前会话用户（未提供姓名） | R1-R8、GraphHarbor 专项、正式包发布与平台适配 | 批准实施 | 原话：“我同意…可以开始实施了，任务推进到只剩下前端的相关事项，除非遇到block的事项”。直接使用本地 key 发布，保持引擎通用边界；未授权现役生产部署或 Git 提交/推送。 |

批准后先更新契约与tasks依赖，再进入implement-feature；拒绝某项则改方案重评，不沿用被拒绝的假设。

## 评审前材料已具备

- [x] 代码事实、参考版本、未验证范围与同事方案纠正。
- [x] 替代方案与推荐路径、三层职责、外部引擎配套和不纳入范围。
- [x] 回调签名/ACK、origin与cron竞态、当前ACL、DTO/feed/read交接。
- [x] 逐task文件/函数/结果/验收、真实故障/正式包/回滚验证计划。
- [x] 人类审阅和决策，授权范围见上述会话记录。

## 后续经验提案

建议在实施确认后向用户提议沉淀到 `docs/lessons/ai-workflow.md` 或 `runtime-service.md`：

“规划生产Run回调时，需先核对当前Worker实现和正式包；透传webhook或graph callback不等于持久终态投递。至少覆盖factory、reaper、cron新thread、callback早于启动响应和Run删除的Outbox保留。”

本条目前只是提案，未写入lessons。实施中另有两条建议：多专项共享双包发版时按实际artifact内容列能力/迁移，并保持各专项验收独立；native故障夹具按“先准备、后显式触发”控制once任务，不用接近当前时间的run_at，同时保留超时失败和宿主负载证据。只有用户确认后才写入经验库。
