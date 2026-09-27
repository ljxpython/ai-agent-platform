# 跨服务规范治理总入口

## 项目概述

- **启动日期：** 2026-09-22
- **本轮修订：** 2026-09-27
- **目标：** 对齐三个现役服务及 AI Harness 的契约，将四项业务契约独立实施和验收，AI规范路由按仓库级文档小改动处理。
- **负责人：** @lijiaxin
- **组织方式：** 总入口 + 四个独立专项；AI规范路由旧目录仅保留历史引用。
- **状态：** 部分完成。错误响应已完成Final；追踪T1—T6有阶段实现和单条真实提交→Run→Langfuse证据，完整矩阵、PG与性能未完成；JWT J1—J6及真实生命周期已验，后续消息回查修复代码与本机测试完成、部署后真实链路未验证；SSE S1—S10完成，S11容量Final受HTTP/1.1入口限制而blocked。
- **当前范围：** 四项原专项保持各自已批准边界；消息内部Run回查按2026-09-27单独授权修改Platform API与Runtime消息入口，GraphHarbor、原生白名单与Thread ACL不变。未执行迁移或部署；用户已授权将当前代码与文档提交并推送到现有分支，提交结果以Git记录为准。

## 阅读顺序与进度

本页是原治理项目的唯一纲领。新专项的 plan.md 是对应方案事实源，tasks.md 是任务进度事实源；本页仅同步摘要。

| 原编号 | 独立专项 | 当前阶段 | 交付边界 |
|---|---|---|---|
| 01 | [AI 服务规范路由](../20260926-ai-service-routing/README.md) | 不再独立立项，旧目录仅保留引用 | 后续按仓库级文档小改动处理；本轮未修改AGENTS规则 |
| 02 | [错误响应统一](../20260926-error-response-contract/README.md) | `done`：真实提交→Run→审计→Langfuse、memory409、SSE编号、peer ACL、workspace正向文件与现役浏览器错误态均通过 | 平台错误出口、上游转换、前端消费与新服务组合验证 |
| 03 | [跨服务链路追踪](../20260926-trace-context-propagation/README.md) | `partial`：T1—T6部分实现，SSE同编号日志及单条提交→Run→Langfuse通过；各任务完整矩阵未验，T7/T8未完成，Final未开始 | 平台内部编号、请求/提交/Run/既有观测闭环；不做完整W3C/OTel改造 |
| 04 | [Delegation JWT 契约](../20260926-delegation-jwt-contract/README.md) | `partial`：J1—J6及R01—R04真实生命周期已验；消息403的后续修复源码和本机测试通过，部署后真实链路未验证 | 原专项保持v2与平台边界；[后续消息回查专项](../20260927-message-run-read-delegation/README.md)单独授权Runtime消息入口改动，不扩大权限 |
| 05 | [SSE 事件契约](../20260926-sse-event-contract/README.md) | `partial`：S1—S10完成，真实普通SDK链路、1/4条短容量及390px前端检查通过；8条容量受HTTP/1.1浏览器origin连接槽限制，30分钟/h2/h3 Final blocked | 线程级持续保活；保持现有渲染和交互，不默认折叠；Runtime/GraphHarbor不改 |

02已完成；04与05主体开发完成但仍缺真实验收，03剩余验证工作最多。04已执行字段/23项operation/身份矩阵和R01—R04真实链路，真实工具Run执行68.499秒跨TTL通过；原Final保留当时消息403事实，后续修复不追溯改写旧证据。01不阻塞业务专项。
JWT 与追踪涉及共同字段，SSE 与错误响应涉及握手/流内失败边界，需要交叉复核；四项不是完全没有依赖。

## 当前剩余验收（2026-09-27）

- **追踪：** 并发/取消上下文隔离、scoped委托与调用方完整矩阵、审批/取消关联、审计PostgreSQL查询及权限HTTP、SSE关闭分类/线程跨Run、worker身份和R1—R6完整链路、查询性能；T7/T8与Final未完成。
- **JWT后续消息回查：** 部署新API与新Runtime后，验证真实运行中Run的消息入队、待处理列表及Thread ACL撤权拒绝。当前真实PostgreSQL队列和配对JWT测试通过，受控原生GET不能替代该链路。
- **SSE：** 需HTTP/2或HTTP/3浏览器入口验证8条并发、30分钟容量、堆增长、退出资源归零及三段脱敏样例；其余真实边界见专项V01—V21覆盖表。当前HTTP/1.1约6条长连接槽会阻塞后续握手和state请求，worker扩容不解决。
- **错误响应：** 本期无未完成项。各专项部署与生产发布另行安排，不把提交快照视为Final验收或上线。

## 2026-09-26 现状校正

1. **现役链路只有三个服务：** platform-web → platform-api → runtime-service。interaction-data-service 已退役，取消原 2.4、3.4 及其他 IDS 实施任务，不能算作已实现。
2. **错误处理已有基础：** Platform API 已有 ErrorResponse / core.errors，上游公共转换函数和前端公共解析均已存在。专项应补缺口，不能按旧方案重建全部错误类。
3. **请求关联已经存在：** API 的 core/context/runtime.py 生成或接收 x-request-id/x-trace-id；委托与 Runtime 观测已有 request_id/platform_trace_id。当前是否完成端到端关联仍须验证，“完全无关联”的旧判断不成立。
4. **JWT 文档已过时：** 当前签发端含 23 个 operation，并增加 request_id/platform_trace_id/credential_id；assistant_id 必填例外也已增加。旧 15 项枚举不再作为实施依据。
5. **SSE 不是尚无实现：** 网关已有脱敏、生命周期转换；前端已有 SDK adapter 与 patch、会话保活。需要以现有代码及 GraphHarbor 边界专项为基础核对协议。
6. **AI 服务索引部分已存在：** AGENTS.md 已列出三个服务与规范。任务改为补齐读取触发、入口与冲突处理，不重复建表。
7. **原预设不是当前生效决策：** request_id 移到 meta、request_id 截取 trace 后 16 位、改写全部 Runtime HTTPException、JWT 所有结构变化必须同时部署，均取消其“默认执行”地位。

本轮核对的是工作区代码及当前项目记录；已有未提交改动未由本轮修改。代码后续变化时，各专项实施前必须复核基线，不能复制本页数字作为永久契约。

## 与现有项目的关系

- [IDS 退役](../20260924-interaction-data-service-retirement/README.md)：作为已退役边界，不重复治理。
- [Runtime / GraphHarbor 边界解耦](../20260925-runtime-business-boundary-decoupling/README.md)：依赖 post33、Thread ACL、pending 对账、业务 trace、事件保留等当前实现；该项目仍为 partial，不能替它宣布 Final 通过。
- [会话缓存与流式保活](../20260924-chat-session-cache-and-stream-resumption/README.md)：SSE 专项复用现状和已有验收范围。
- [个人记忆闭环](../20260920-dear-agent-memory/README.md)：JWT operation 与无会话权限边界的输入资料。

## 统一的“可开工”门槛

四个专项都要逐项满足以下条件，不能只创建目录就标记为已对齐：

- [ ] 范围、非目标、责任服务和跨专项边界明确。
- [ ] 现状有代码路径/函数或真实协议样例支撑。
- [ ] 字段、错误码、状态、权限和敏感信息规则逐项冻结；仅针对新服务组合验收。
- [ ] 每项任务写明改动内容、代码位置、预期行为、最小验证。
- [ ] Phase 与 Final 分开；测试输入、预期输出、执行方式和环境要求明确。
- [ ] 新服务组合的发布方式、外部消费者及在途运行影响明确；不设置旧版本兼容门禁。

## 四专项统一版本边界

2026-09-26 用户确认：本轮只面向新 Web、新 API 与当前锁定的 Runtime/GraphHarbor。无需支持新旧服务混用，也无需旧版本兼容测试、历史格式回归或旧产物切回验证。四个专项的验收以新服务组合的功能、安全及真实链路为准；原有业务动作的幂等、权限及已接受 Run 的状态语义仍须验证。旧验证记录保留为历史事实，不作为剩余任务。
- [ ] plan.md 中未决项清零；人工评审人、日期、批准范围记入专项 README。

四专项已有独立执行方案与任务/验收要求，均进入阶段实施，完成度以各专项文档为准。SSE 的线程保活与展示保护范围已获批准；追踪范围及契约已批准；JWT已批准整理现有v2、双端一致性测试及优先修平台侧，并确认到期不自动取消已接受Run、不增加SSE持续重鉴权、新请求按当前权限重新签发。以上清单是总门槛，具体批准记录与任务状态以各专项为准。

## 文档迁移规则

原 01—05 文件保留为失效提示和跳转，防止旧链接失效；旧方案正文不再作为第二份可执行方案。
独立专项是唯一维护位置，不重复维护原任务表。不创建尚未冻结的 docs/standards 契约冒充现行规范。

## 本轮文档验证（2026-09-26）

- `python3 scripts/check_docs.py`：通过。
- 前序26份Markdown检查记录保留；本次复核追踪四文件、任务状态及本轮修改的相对链接/围栏。FEATURES存在一条既有无关链接缺陷，详见[追踪文档验证](../20260926-trace-context-propagation/verification.md)，不宣称其整页链接全通过。
- `git diff --check`：通过。
- 业务代码未修改；未执行应用单元、集成或E2E测试。上述检查不能作为任一专项的功能验收。
