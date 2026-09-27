# Delegation JWT 契约专项

- **启动日期：** 2026-09-26
- **负责人：** @lijiaxin
- **模板类型：** 标准模板
- **级别：** 治理改动（既有委托契约收口）
- **状态：** 部分完成；J1—J6平台范围任务与R01—R04真实生命周期已验。消息内部原生Run子调用的既有403作为Runtime兼容限制单列，Final结论见verification.md。
- **父入口：** [跨服务规范治理](../20260922-cross-service-governance/README.md)。

## 最小必读清单

1. 仓库 AGENTS.md、docs/CONTEXT.md，以及 [API文档导航](../../../apps/platform-api/docs/README.md)中的任务相关规范。
2. 本专项 [plan.md](plan.md) → [tasks.md](tasks.md) → [verification.md](verification.md)。它们给出完整矩阵、确定的修改点和验收方法。
3. [错误响应方案](../20260926-error-response-contract/plan.md)中委托错误与用户登录失效的区分；[追踪方案](../20260926-trace-context-propagation/plan.md)第2、5节的既有两个关联claim。若集成SSE，仅阅读其[生命周期与恢复规则](../20260926-sse-event-contract/plan.md)，不重做前端。
4. plan中的签发/校验源码与相关测试，核对当前工作树。无需阅读所有历史项目或重新选择架构。

## 批准记录

- 2026-09-26：用户批准整理现有v2契约、补齐签发端与校验端一致性测试，优先修平台侧不一致；Runtime/GraphHarbor保持不变。
- 同日确认简化生命周期：委托到期不自动取消已接受Run；不增加SSE持续重鉴权；重连、审批、取消等新请求按当前权限重新签发。
- 同日要求将本专项细化至其他开发者可直接执行。本次交付确定的claim/operation/身份矩阵、平台修正清单、双端测试执行方式与回退要求；不构成本轮编码或部署授权。
- 同日确认只验收新API与当前锁定Runtime组成的新服务组合；不要求旧API、旧Runtime或新旧混用兼容，也不设置旧产物切回测试门禁。
- 2026-09-27：用户授权按执行包实施和测试；迁移、部署、Git提交及分支操作另行安排。

## 范围与交接

仅修改platform-api签发校验、Catalog凭据传递及平台侧测试/文档。平台阶段改动见 [签发记录](implementation/01-platform-signer-inputs.md)、[契约矩阵](implementation/02-contract-matrix.md)与[真实链路阶段证据](implementation/03-live-lifecycle.md)。运行时校验器作为只读测试对象；Runtime/GraphHarbor源码、配置、依赖和数据库结构未改，隔离测试项目产生了Thread/Run记录。前端不改。

保持v2、HS256、既有TTL与单密钥机制；不新增claim、operation、共享契约包、续租、撤销服务、持续SSE鉴权或v3。权限与Run执行语义不变。

J1—J4已完成可执行矩阵；J5的Run跨TTL、SSE跨TTL、撤权后在途Run及新请求拒绝均有真实证据。消息入口内部原生Run回查仍为Runtime既有限制，保持拒绝行为，不绕过鉴权；完成度与命令结果以[tasks.md](tasks.md)、[verification.md](verification.md)为准。

2026-09-27后续：消息内部回查兼容修复已获单独授权并在[专项](../20260927-message-run-read-delegation/README.md)实施。本专项Final保留当时现役403证据；新代码的现役链路仍未验证，不追溯改写既有验收结论。
