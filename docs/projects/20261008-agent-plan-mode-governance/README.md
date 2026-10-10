# Agent 通用 Plan Mode 与计划审批治理

## 项目信息

| 项目 | 内容 |
| --- | --- |
| 启动日期 | 2026-10-08；规划收口 2026-10-09 |
| 目标 | 为 Agent 提供可组合的先规划、人工审阅、批准后执行能力，规划期间在工具执行边界限制副作用 |
| 状态 | 已完成（done）；三服务（Runtime/API/Web）全链路实施完成，静态门禁 100% 通过，Playwright + Chromium 真实大模型（DeepSeek-V4-Flash）端到端测试闭环通过，双主题三视口截图与对账证据齐全 |
| 模板类型 | 标准模板；三层契约共同构成一条审批链路，不能分别上线验收 |
| 改动级别 | 治理改动：工具权限、安全状态与跨服务审批契约 |
| 影响服务 | runtime-service、platform-api、platform-web |
| 负责人 | 全链路实施与端到端验证：实施者；方案评审：用户 |
| 本仓源码基线 | `85d63d87bdf84dabbb963f79e8dd4b2db4432ade` |
| 预计工作量 | Runtime/API 7-10 人天，前端 2-3 人天，联合验收 2-3 人天；为排期估算，不是交付承诺 |

三服务全链路实施与自动化验收已完成，进度与真实证据见 [tasks.md](tasks.md) 与 [verification.md](verification.md)。

## 阅读顺序

1. [源码对照与取舍](reference-analysis.md)：open-swe 怎么做、当前已有能力、真实差距、同事建议哪些采用。
2. [整体方案](plan.md)：安全边界、状态转移、三层职责、契约、文件清单、上线与回退。
3. [任务拆分](tasks.md)：依赖、负责人、具体代码位置、每项验收和人工评审门禁。
4. [验证计划与记录](verification.md)：规划检查与后续单元、集成、真实端到端、安全、性能和回退矩阵。
5. [前端交接](frontend-handoff.md)：已冻结 DTO、错误码、真实公开样例、接入位置、复跑入口和验收任务。

实施记录位于 `implementation/`（01-04）；三服务全链路真实模型端到端测试与截图见 `verification.md`；DearFlow 真实模型与 Reference 真实 HTTP 的公开样例见 `samples/`。隔离 E2E 不提供持久联调 URL。

## 推荐结论

- 借鉴 open-swe 的按运行启用规划、模型动态工具裁剪、独立计划展示和人工反馈交互。
- 采用 `enter_plan_mode`、`save_plan`、`submit_plan` 三个通用工具；人工批准走现有 `input.respond` 和原生 interrupt，不向模型提供可以自我放权的 `approve_plan`。
- 复用当前显式 Agent 组合根、`RuntimeConfigMiddleware` 授权、GraphHarbor 持久 checkpoint、平台 ACL、RunRequests 幂等与官方前端 SDK。
- 规划期同时裁剪模型工具列表和拒绝实际越权调用；默认拒绝未审查工具、MCP、shell、普通写文件与 `task`。
- 首期计划存 Markdown checkpoint 快照，提交审批冻结 plan ID/revision/hash。无需开放 `/workspace/plans/`、新增计划数据库表或复制 HTML 评论平台。
- 计划批准只解除规划附加限制，原有项目禁用工具、会话访问策略和逐工具 HITL 继续生效。

## 三层是否需要

| 层 | 是否需要 | 本期责任 |
| --- | --- | --- |
| platform-web | 已完成 | 下一次运行的规划开关（“+”号菜单展开）、计划预览、批准/修改/放弃、真实中断与恢复状态、输入框安全锁定 |
| platform-api | 必须 | 选项与私有状态边界、当前审批权限、回复校验、版本匹配、幂等恢复、签名执行绑定、安全公开投影与审计 |
| runtime-service | 必须，是执行事实源 | 状态/checkpoint、三个工具、原生 interrupt、模型与执行双重门禁、主子图装配、隐式副作用治理 |

## 本期边界

本期只补 Plan Mode，四个正式图 Showcase/DearFlow/Reference/Workflow 都在适配清单中。执行预算、超时、工具容错、模型重试、停止、Token/Cost 和 Workspace 容错复用已有专项，不再立第二套实现。新增 Agent 可通过公共 middleware/tools 和明确的安全工具声明接入；能力声明不等于授权，也不能把任意图自动标为支持。

首期不做任意 shell 命令只读判断、规划子 Agent 委托、MCP 自动信任、计划 HTML/批注编辑器、Slack/GitHub/Linear 集成、PR/提交工作流或计划内容逐语义约束执行。普通模式沿用现有授权；Plan Mode 是可选择的附加约束，不是整个运行环境绝对零写入。

## 人工评审入口

用户已于 2026-10-09 确认 [plan.md 的 G01-G08](plan.md#人工评审清单) 并授权实施，批准记录见 `implementation/01-review.md`。三服务（Runtime/API/Web）实施已全部交付并经真实大模型端到端闭环验证。旧 Runtime 不能保护计划 Thread，按批准方案保留当前门禁并封锁 Agent，未执行旧二进制降版。
