# Agent Workspace 执行容错与安全失败报告

## 项目信息

| 项目 | 内容 |
| --- | --- |
| 启动日期 | 2026-10-07 |
| 目标 | 在共享 Workspace 执行边界补齐失败保护、不可达/结果未知时停止 Run，以及安全错误说明和诊断；启动重试按证据门禁决定 |
| 状态 | done；非前端本地与 Docker 范围全部完成并已合并进入主干；前端交接与 DTO 已固化，等待前端后续展示适配 |
| 模板 | 标准模板；执行、错误投影、诊断与前端属于同一条耦合链路 |
| 改动级别 | 治理改动：涉及副作用命令重放、生产执行边界和公开错误契约 |
| 服务 | runtime-service、platform-api；platform-web 由同事接手 |
| 开发位置 | 独立 detached worktree：`~/.codex/worktrees/agent-production-capabilities/ai-agent-platform` |
| 本仓基线 | `bf47991b7592b19cbda1051c6a674623450318ae` |
| 负责人 | Runtime/API：本轮实施者；Web：用户同事；方案批准：用户（2026-10-07） |

2026-10-07 用户批准治理方案并要求完成全部非前端开发。当前实施与验证均在上述 worktree，前端代码未改；不提交、不推送、不部署现役服务。进度以 [tasks.md](tasks.md) 为准。

## 阅读顺序

1. [参考与差距分析](reference-analysis.md)：open-swe 的真实实现、当前已有能力、同事建议的取舍及基线问题。
2. [整体方案](plan.md)：三层职责、重试证据门禁、错误分类、契约、逐文件改动和回退。
3. [任务拆分](tasks.md)：依赖关系、负责人、验收条件及实施状态。
4. [验证计划与真实记录](verification.md)：规划检查、Phase 验证与 Final 验证分别记录。
5. [前端交接](frontend-handoff.md)：同事可独立阅读的已实施契约、修改位置、交互边界与验收场景。
6. [前端交付报告](frontend-report.md)：可直接转交同事，含真实本地/Docker 样例、字段和验收任务。

`implementation/` 记录批准范围、代码变更和隔离证据，不作为进度来源。错误/SSE 标准按已批准契约同步，其他专项尚未验收的草案不升级。

## 本期结论

- 当前已有本地持久 Workspace、Docker 执行隔离、官方选择性 ToolErrorMiddleware、原生 Run/SSE 和 RunDiagnostics。重点是补齐共享边界，而非再建 Agent 循环或通知系统。
- transient 的关键条件是可信实现证明命令未启动。文件锁、权限错误、超时、一般连接错误和任意 5xx 都不构成这个证明。
- 真实 CPython 接线 EAGAIN 发生在文件副作用之后，选择批准的 G1 分支 B：Docker/local 自动启动 retry 为 deferred；当前命令只执行一次。
- Docker exit 125 本身不等于环境不可达。已实施一次有界只读健康探测；不可确认环境可用时停止并标记结果未知，不重新提交命令。
- Workspace 致命错误仍传播成原生失败终态；“优雅报告”不将故障变成成功回答，也不让 LLM 在预算耗尽后继续重试。
- 前端需要小范围适配错误说明和既有诊断面板。重试判定、次数、执行、终态与权限都由后端/Runtime 负责。

## 基线问题与处理

| 事实 | 影响与处理 |
| --- | --- |
| Runtime 非外部依赖基线：47 passed，2 deselected | 支持复用现有错误边界；不证明新重试正确 |
| API worktree 基线：3 failed，33 passed，114 subtests passed | 用户批准 G0；已补 tasks 脱敏并统一 code/字符串 `runtime.execution_failed`、对象固定说明 |
| 规划时 Docker daemon 不可用，用户曾调整为本地验收，随后恢复 Docker | 本地 Final 已独立完成；T32/T33 已补齐真实 Docker 生命周期、性能与 HTTP/Worker 链路，测试后关闭 Docker Desktop |
| 主工作目录存在同事未提交内容 | 本 worktree 从 HEAD 建立，未复制那些内容；前端与模型专项合并前重新核对基线 |
| open-swe 是有未提交改动的参考工作副本 | 借鉴实际文件快照；不宣称它等同 HEAD 或已通过参考项目测试 |

## 范围

本期包括共享 Docker 执行边界、失败分类与清理、原生错误槽位的精确安全投影、现有诊断查询扩展、主/子 Agent 接入回归及前端交接。

本期不增加 E2B/Daytona/Modal/LangSmith provider、全局 closed/open/half-open 熔断状态机、自动切换或删除 Workspace、宿主 shell 降级、PTY 输入重发、LLM 全局重试、模型/长任务/上下文专项、Slack/GitHub/Linear 通知业务。未来接入真实云 SDK 时，再按其“未提交”证据在 provider 内部应用同一原则。

## 交付门禁

人工批准已记录于 implementation/01-review-and-start-boundary.md。本轮非前端任务及 T30-T33 共13项完成；T23 与三服务浏览器联合验收交由同事。实际本地与 Docker 隔离链路、安全、取消、重启/回退均有证据，自动启动 retry 维持已批准的 G1 分支 B，不属于因 Docker 环境缺失而未完成的事项。

2026-10-07 用户先要求使用本地已有环境验收，原生 PostgreSQL/Redis 与 `RUNTIME_BACKEND=local` 的 Final 已完成；随后要求恢复 Docker 后延项并在用完后关闭。真实 Docker 执行、并行重复取消、成功路径测量及两条完整 HTTP/API/Worker 链路已通过，本轮临时资源已回收，Docker Desktop 的 engine/后台进程关闭已确认。两次 Final 分别保留于 verification.md；性能波动如实记录，不宣称生产 SLO 达标。
