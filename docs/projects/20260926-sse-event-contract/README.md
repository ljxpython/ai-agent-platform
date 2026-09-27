# SSE 事件契约与线程持续保活专项

- **启动日期：** 2026-09-26
- **负责人：** @lijiaxin
- **模板：** plan-project标准模板
- **级别：** API/Web跨服务治理
- **状态：** 部分完成（S1—S10 已完成；真实三服务普通 SDK 链路、1/4 条容量短测和 390px 前端检查有证据；8 条 Runtime-backed SSE 受本地 HTTP/1.1 浏览器 origin 连接槽限制，30 分钟/h2/h3 容量 Final 未完成）。Runtime、GraphHarbor、迁移、部署和 Git 操作均未涉及。
- **父项目：** [跨服务规范治理](../20260922-cross-service-governance/README.md)

## 阅读顺序

1. [实施方案](plan.md)：范围、完整实例宿主、恢复/410、网关帧规则、展示保护、发布边界。
2. [任务清单](tasks.md)：唯一任务进度源，每项含位置、行为和验证要求。
3. [验证执行包](verification.md)：21组场景、输入/断言、夹具与真实链路命令、容量门禁。
4. [open-swe对照](open-swe-comparison.md)：借鉴证据及不能照搬的行为。

## 已确认与本次补齐

用户已确认：本期纳入线程级持续保活；现有前端渲染展示及交互保持不变；不采用默认折叠等展示改造。本期继续只改API/Web，Runtime/GraphHarbor保持不变，不改DB或事件保留策略。

版本边界：只验收新Web+新API+当前锁定Runtime；不要求旧服务兼容、新旧服务混用或旧产物切回测试。新组合内的恢复、权限、安全和在途Run行为仍须验证。

本次具体化：Workspace统一持有完整ChatSession，条目独享草稿/附件/参数；SDK传输层唯一自动恢复；手动恢复保留逻辑订阅；410按已确认状态安全降级；终态不截尾；8MiB帧限额和安全关闭；权限与迟到结果隔离；明确测试/发布/回退步骤。

为保留当前展开/阅读/输入状态，不采用60秒/8条自动卸载；当前作用域内条目保留到退出或显式删除，按8个活跃/30个访问条目验证容量，线性资源增长取舍见plan4.4。保活不包含关闭浏览器或跨项目驻留。

## 评审记录

- 2026-09-26：用户要求各专项独立建立、细化至可交接；错误响应专项方向已确认。
- 2026-09-26：用户指定open-swe参考，确认SSE线程保活及展示保护。
- 2026-09-26：前序补齐执行细则及源码/隔离探针证据；本次交接确认用户随后已同意进入下一专项，移除已过期的“新增细则待评审”状态。线程级持续保活、现有渲染与交互保护继续生效。
- **业务实施批准：** 2026-09-26 用户明确“继续”，授权按执行包实施和测试；范围为 platform-api/platform-web 及现有 SDK patch，保持现有渲染和交互，线程级保活纳入本期。排除 Runtime/GraphHarbor、迁移、部署、提交和分支。

## 交接判断

文档粒度已从方向稿补到可按任务实施；本轮已完成 API/Web 阶段实现、受控浏览器验证及真实 Runtime 普通链路验证。390px 顶栏重叠已修复并复核；实施前基线不可追补，按用户要求不执行旧版本兼容矩阵。8 条容量的直接阻塞根因已确认是 HTTP/1.1 浏览器 origin 连接槽，h2/h3 和 30 分钟 Final 仍按 blocked/未验证处理，证据见 [真实 Runtime 验证](implementation/04-real-runtime-validation.md)。

关联：[错误响应](../20260926-error-response-contract/README.md)、[追踪](../20260926-trace-context-propagation/README.md)、[既有页面缓存保活](../20260924-chat-session-cache-and-stream-resumption/README.md)、[Runtime边界](../20260925-runtime-business-boundary-decoupling/README.md)。
