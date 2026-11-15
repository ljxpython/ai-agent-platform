# EvalFlow 巡检接线准备（默认关闭）

2026-11-14 用户批准：先使用已鉴权的 EvalFlow 质量巡检汇总；Grafana 抓取与告警等待访问范围及 Contact Point 齐备。本目录不被现有 compose 挂载，不修改生产配置，也不包含凭据。

- `evalflow-inspection.prometheus.yml` 的抓取、规则和接收端均为空。注释中的 job 只说明后续配置形状，不能直接启用。
- `evalflow-inspection.rules.yml` 仅有抓取失败持续 5 分钟的候选规则；当前没有加载入口或接收端，不会发送通知。5 分钟是演练候选，需负责人冻结后才可启用。
- 指标接口需要原生 Basic 身份、明确的项目/实验 read 授权及有效批次 ACL。无凭据、权限过期、源不可用须拒绝；禁止将管理员账号用于抓取。
- 原生接口撤权后过滤记录，不能抹掉 Prometheus 已采集历史。启用前必须另定历史指标的受众、保留/删除责任与撤权策略；现有匿名 Editor Grafana 不满足条件。仅关闭目标不是历史资料权限整改。
- `evalflow_inspection_records{kind=...}` 只报告当前可见记录数量，非时间窗口事件率；不能把其 error/missing 存量直接当作持续故障或恢复通知，也不代表全部生产流量。当前不提供低样本质量下降告警。

后续验收：确认独立受众/身份/凭据文件和历史保留政策 → 用部署版本的 `promtool check config` / `check rules` 验证 → 合成环境验证 200/401/403/源失联、触发/去重/恢复 → 经明确授权发送到指定 Contact Point → 保存真实回执。本轮只做 YAML 和默认关闭检查，不声称告警接收、PromQL 引擎或生产部署通过。
