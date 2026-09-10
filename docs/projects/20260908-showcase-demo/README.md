# Showcase Demo：真实可用的教学 Agent

- **启动时间：** 2026-09-08
- **重评时间：** 2026-09-09
- **状态：** partial（runtime-service 与平台后端 Showcase 主链路已验收；前端按用户决定 deferred）
- **范围：** runtime-service 的 showcase_demo、必要的公共运行时接入、部署配置和验证。
- **级别：** 治理改动（授权与执行边界）。
- **评审依据：** 用户在本轮审查后明确采纳建议，要求保持简约、去除模拟、修复路径可移植性，并授权按规划实施。具体实现选择及限制见 plan.md。

## 当前事实源

1. [方案](plan.md)
2. [任务](tasks.md)
3. [验证](verification.md)
4. [实现记录](implementation/08-teaching-demo.md)
5. 教学入口：apps/runtime-service/src/runtime_service/services/demo/showcase_demo/README.md

本目录此前的 FINAL_*、FIXES_SUMMARY、STATE_SCHEMA_FIX 等报告是旧版本记录，不再证明当前能力已完成。当前状态只以上面四份核心文档和可复现测试为准。

## 重评结论

上一版 9 个测试通过，但工具 allowlist 为空仍可调用工具，Context 哈希没有执行校验，Todo 没有更新状态，Skills 未被加载，execute_command 返回固定成功文本。子图事件测试没有实际调用子图。真实沙箱、隔离、恢复和前端链路不能据此记为完成。

## 关键决策

- 使用官方 create_deep_agent、TodoListMiddleware、FilesystemMiddleware、SubAgent 和 HITL。
- 私有工具只保留真实文档抓取；文件、搜索、计划、执行不再重复实现。
- Docker 只隔离命令执行，线程工作区由独立目录持久化；不挂载源码、凭据或 Docker socket。
- Skills 与示例资源随包发布，模型只接触虚拟路径。
- 保留项目启动日期；不再新建多个最终报告。

## 本轮结果（2026-09-09）

已完成官方 Todo/Skills/子 Agent/HITL 接入、Runtime 授权、可移植包资源、线程工作区、真实 Docker 执行和受限文档抓取。相关回归 151 passed，真实模型只读分析 1 passed；干净 wheel 安装后的资源和探测验证通过。具体命令、限制与未验收项见 verification.md。

## 后端收尾（2026-09-10）

真实模型完整修复、多个独立审批和 API/Worker 重启后的持久化恢复均已通过。验收发现并修复 GraphHarbor 的 Context 传递及增量状态读取问题，已发布并安装 `0.13.0.post21`。升级后 runtime-service 回归 152 passed，正式索引安装版本的真实重启验收通过。

后端完成范围与前端待办以 [验证记录](verification.md) 为准；实现细节见 [收尾记录](implementation/09-backend-acceptance.md)。

## 后续顺序调整（2026-09-10）

按用户要求，先推进 [Platform API 重构工程](../20260910-platform-api-refactor/README.md) 的方案讨论、实施与验收，再恢复本工程的平台联调和前端验收。已有 runtime-service 验收不撤销；本工程整体不标 done，后续待办保持 deferred。

## 平台后端联调验收（2026-09-10）

GraphHarbor post25 下真实平台 → Runtime → 模型/工具链路通过，审批期间重启 Platform API、Runtime API/Worker 后恢复，最终独立执行输出 43.50。见 [验证记录](verification.md) 和 [前端调整清单](../20260910-platform-api-refactor/05-frontend-handoff.md)。本次只验收后端，前端统一后置；整体保持 partial。

post26 收尾复验已通过：实际超 TTL 排队、凭据轮换、取消重发、标准审批与三进程恢复均成功，独立报表仍为 43.50。[最新验证记录](verification.md#2026-09-10-post26-后端收尾复验)。前端继续 deferred。

2026-09-10 事务重构后 Docker 完整复验通过：三进程重启/标准审批/真实 execute、实际回归测试函数及报表 43.50 均通过，见 [最终证据](../20260910-platform-api-refactor/evidence/20260910-final-docker-showcase.json)。前端仍 deferred。
