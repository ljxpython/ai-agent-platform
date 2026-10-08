# 人工评审清单

> **状态：** 2026-10-07 用户明确批准方案实施。本轮完成全部非前端开发及可执行验证，前端由同事负责。
> 治理改动批准依据：仓库 `AGENTS.md` 的治理流程，以及 `plan-project/SKILL.md` 的“对于治理改动，创建后需要评审才能开始实现”。本文档不替人批准。

## 建议确认项

| 编号 | 建议决策 | 理由与替代影响 |
|---|---|---|
| R01 | Stop 默认取消受理边界内当前执行和全部待执行 Run | 当前单 Run Stop 会让旧队列继续。若产品只想暂停当前 Run，应保留旧单 Run 接口并使用明确的独立动作名 |
| R02 | 边界后接受的新 Run 不被旧请求取消 | 相同 key 重试不能误伤后来工作；用户再次 Stop 是新动作 |
| R03 | `interrupt` 为首期唯一动作，不开放 rollback | 保留 Run/checkpoint；不能撤销外部副作用，不提供误导性的“全部回滚” |
| R04 | 确定性报告首期必做，LLM 润色后置 | 无模型成本/权限/可靠性依赖；后续只使用无工具 one-shot，不能复用生产 graph 摘要 Run |
| R05 | 只复用当前 Thread edit/read 权限，不新增角色 | 非 owner 是否能 Stop 取决于当前 share edit/takeover 规则，不移植 Slack 非 owner 停止策略 |
| R06 | 引擎配套原子目标、持久回执和查询，不做 API 内存锁替代 | 需要覆盖多 API/Worker、pending claim、unknown/retry；GraphHarbor 为正式依赖 |
| R07 | Runtime 控制动作/资源证据表与后台收敛可迁移 | 不复制 Run 状态机、不存 token；须 migration/rollback 验证后才能升级实际服务 |
| R08 | 已提交停止意图即持续收敛，撤权阻止后续操作/查询 | 引擎提交前须当前授权回查；接受后的受信后台仅能读取固定取消回执，narrow native scope 不能读 Run/state/input/output；故障为可重试不可用 |
| R09 | 已暂停 HITL 不自动解决，外部 detached 任务/手动 PTY 不随 Stop 取消 | 避免自动审批或错误取消用户独立资源；报告明确未知与待处理项 |
| R10 | 前端交给同事，后端完成仍只能记 Phase | [前端交接](frontend-handoff.md)与真实联合验收是功能完成条件 |

## 实施前需要核实的依赖

1. 当前实际 GraphHarbor post41 安装/现役进程与本地源码是否一致，worker cancel 配套版本是否已发布；本轮未运行/部署这些进程。
2. [持久消息队列](../20261005-durable-chat-prompt-queue/tasks.md) T7 的联调/迁移证据。其源码 T4-T6 已打勾，旧功能总览的 localStorage 描述过时；本项目不替它标 done。
3. 引擎维护方是否接受通用 cancel-active/receipt 设计。若不接受，必须缩小公开承诺并修改本方案；不能用非原子 list+cancel 宣称同等语义。
4. 准备执行集成测试的隔离平台库/Runtime 库/Redis、测试身份/模型和 Backend；不借用生产数据做破坏性用例。

## 评审记录

| 日期 | 评审人 | 范围 | 结论 | 备注 |
|---|---|---|---|---|
| 2026-10-07 | 用户 | R01-R10、整体方案与任务 | 批准 | “方案评审通过，可以开始实施了。把除了前端的开发项都开发完成，除非有 Block 项” |

批准后沿 tasks.md 执行，并在实施期间调用 implement-feature；Final 再调用 verify-change。远端部署、真实数据库迁移或包发布须沿用户授权与实际运维边界执行，本轮不自动进行。
