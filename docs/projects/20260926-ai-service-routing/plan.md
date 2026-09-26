# AI 服务规范路由 - 讨论稿

> 2026-09-26：不再独立立项。下方为停止维护的原规划，不作为实施任务；后续仅按仓库级文档小改动更新现有规则，并在docs/changes/留痕。旧文件保留用于已有引用，本轮未修改AGENTS规则。


> 本文件目前用于确定讨论边界，不是已经批准的执行方案。其他人不能据此开始业务改造。

## 背景与当前事实

AGENTS.md 已列三个服务与标准文档；Runtime standards/README.md 已规定代码/tests与规范的事实来源。原方案“从零新增服务索引”过时；docs/standards/cross-service-contract.md 当前不存在。

## 范围

补齐触发式阅读、短入口导航与冲突处理；不新增业务功能，不做自动扫描器，不要求每次读所有handbook文件。

## 建议方向

保留 AGENTS.md 现有服务边界结构，在会话初始化补一句“涉及服务时读该服务规范入口，再按任务读相关条目”。使用已有目录入口；仅对已批准且在范围内的契约建立引用。遇到规范/代码冲突，记录现状与目标差异并按已批准方案实施，不能以“跨服务规范优先”让过期草案覆盖当前安全边界。

## 当前代码/规范入口

- `AGENTS.md`
- `apps/platform-api/docs/README.md`
- `apps/runtime-service/docs/standards/README.md`
- `apps/platform-web/docs/frontend-development-playbook.md`

这些是调研起点，不是承诺全部修改的文件清单。具体函数、输入输出和验收必须在本专项讨论时补齐。

## 必须逐项对齐的决策

- [ ] D1：规范入口是必读一个导航还是必读多个全文；推荐导航+任务相关规则。
- [ ] D2：未来跨服务契约放在哪里；推荐仅在真正冻结时建立标准入口，现在引用专项总入口且明确草案状态。
- [ ] D3：冲突优先级与升级路径；推荐先核事实和批准状态，涉及安全/契约冲突需人工评审。

## 与其他专项的边界

- [错误响应](../20260926-error-response-contract/README.md)：公开HTTP Envelope与上游转换；不顺带决定鉴权/流内协议。
- [SSE契约](../20260926-sse-event-contract/README.md)：事件、断线、恢复、执行状态。
- [追踪](../20260926-trace-context-propagation/README.md)：关联ID语义和传播，不以文档化为由改JWT字段。
- [JWT契约](../20260926-delegation-jwt-contract/README.md)：字段信任和签发/校验规则。
- [AI路由](../20260926-ai-service-routing/README.md)：规范读取与冲突处理，不将未批准规划稿当正式标准。
- [Runtime/GraphHarbor边界](../20260925-runtime-business-boundary-decoupling/README.md)：继承现役责任边界，已有partial验收不得改写成done。

## 发布、回退与风险

文档输出采用单一事实源，旧入口跳转；不复制两套有效契约。
若讨论确定需要代码，必须先补部署顺序、混合版本、在途请求/Run影响、回退目标与验证，然后评审。
当前未定义发布方案、无部署授权，也不预填工期承诺。
