# Showcase Demo 任务（2026-09-09 重评）

## 已完成的前置工作

- [x] 对照 11/13 号架构文档审查，复现授权、Todo、Skills、抓取与假执行缺陷。
- [x] 用户采纳审查建议并授权实施；确认简约、真实、官方 API 优先的原则。
- [x] 重置进度，旧测试通过不等于全部能力完成。

## 本轮实施

- [x] T1：恢复主/子 Agent 的 Runtime 授权与 Context/scope 校验，移除正式入口测试认证开关。
- [x] T2：使用官方 Todo 状态和文件工具，删除假执行/假完成以及无用 State。
- [x] T3：包资源 + /skills/ 虚拟来源，验证可发现、可读取、不可修改、可安装。
- [x] T4：真实 CSV 示例、线程隔离工作区和 Docker 执行，保留真实错误/退出码。
- [x] T5：显式子 Agent 最小工具集、HITL、超时和调用预算，纯分析不触发写入。
- [x] T6：文档抓取限制协议/站点/重定向/响应大小，覆盖失败分支。
- [x] T7：工厂探测无外部副作用；独立 Demo 部署注册。
- [x] T8：重新编写行为测试，覆盖 Todo、Skills、子图事件、审批恢复、授权和隔离。
- [x] T9：Demo README、实现记录、验证结果和功能总览同步。

## 仍需独立证据的能力

- [x] 真实 Docker 集成：写文件 → 审批 → 执行 → 检查产物与退出码。
- [x] 远程 Agent Server 的持久化/重启后恢复（审批暂停期间，真实 API/Worker + PostgreSQL/Redis）。
- [ ] platform-web → platform-api → runtime-service 真实界面联调。
- [ ] 前端子智能体 token、Sandbox 文件界面、推理 token 展示。

以上项目不会因代码装配完成自动打勾。

本轮 T1–T9 于 2026-09-09 完成；真实模型只读流式分析也已通过。当时剩余远程持久化和前端项未验收，项目整体为 `partial`；后续结果见下。

## 后端收尾（2026-09-10）

- [x] T10：两个并行子 Agent 的独立 interrupt ID 映射恢复与真实副作用检查。
- [x] T11：真实模型修复 → 审批 → 执行；审批期间重启 API/Worker 后恢复完整消息和原审批。
- [x] T12：修复框架 Context/增量状态/graph 关联，发布 post21，更新依赖锁与索引安装后复验。
- [x] T13：教学 README、状态、结构化证据和实现记录同步。

runtime-service 教学范围：`done`。整体项目：`partial`，仅保留本轮范围之外的前端验收项。

## 2026-09-10 平台后端验收与前端后置

- [x] 真实 Platform API 登录/项目/目录/模型/Agent/Thread/Run/审批链路；GraphHarbor 与 Runtime 使用 post25。
- [x] Platform API、Runtime API 和 Worker 三进程重启后恢复原 messages/interrupt；最终 Run success，独立 Docker 执行检查通过，报表 43.50、退出码 0。
- [x] 同 key 复用、不同 payload 冲突、Agent 禁用后审批拒绝、跨项目拒绝及公开流字段检查。
- [ ] 前端页面、token 展示、三栏 Sandbox、断线/刷新/多审批等浏览器验收：**deferred**，按用户本次决定统一后置。

证据：[平台 Showcase](../20260910-platform-api-refactor/evidence/20260910-platform-showcase-post25.json)。平台后端其余缺口见 [验收四态](../20260910-platform-api-refactor/implementation/10-operations-run-requests.md)；前端影响及实施步骤见 [05 前端交接](../20260910-platform-api-refactor/05-frontend-handoff.md)。本记录更新此前“等待平台联调”的状态，历史 post21 验收仍保留；本工程整体 partial。

## 2026-09-10 post26 后端收尾复验

- [x] 使用 GraphHarbor/Runtime `0.13.0.post26`，平台新模型 UUID 与精简后的 Agent 契约完成真实执行。
- [x] Run 排队实际等待 62 秒，超过默认 60 秒模型引用 TTL；轮换凭据后启动 Worker，真实模型执行成功。
- [x] pending 并发拒绝、取消后重发、同 key 复用/冲突通过；三进程重启后消息与 interrupt 一致，标准 `command.resume` 按 ID 恢复。
- [x] 六次真实工具审批，独立 Docker 回归测试通过，报表及 result.txt 为 43.50，SSE 读取 105030 字节。

[post26 证据](../20260910-platform-api-refactor/evidence/20260910-platform-showcase-post26.json) · [收尾记录](../20260910-platform-api-refactor/implementation/11-backend-closeout.md)。本次后端功能验收 done；前端按用户决定 deferred，Showcase 项目整体仍 partial。

2026-09-10 事务重构后 Docker 完整复验通过：三进程重启/标准审批/真实 execute、实际回归测试函数及报表 43.50 均通过，见 [最终证据](../20260910-platform-api-refactor/evidence/20260910-final-docker-showcase.json)。前端仍 deferred。
