# Operations 已退役

> Status: Archived. 2026-09-10被当前文档替代，仅保留历史；替代入口见[归档索引](../../README.md)。

2026-09-10 起不再使用平台通用 Operations、Worker、Redis 队列或 artifacts。
禁止以本文件的历史版本作为开发模板。

- 图和工具目录刷新：受权限保护的同步 HTTP，返回真实结果或明确错误。
- Agent 执行：GraphHarbor Run/Worker；平台通过 run_requests 保存提交身份与幂等关联。
- 审计：平台 HTTP 审计及最小请求记录；执行状态直接查询 Agent Server。
- 新业务暂不引入通用异步框架；按实际需求单独评审。

当前标准见 [运行网关](../../../standards/runtime-gateway-interface-standard.md) 与
[重构工程](../../../../../../docs/projects/20260910-platform-api-refactor/README.md)。
