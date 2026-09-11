# 旧 Chat 视觉恢复与 Agent 入口归一

## 目标与批准

2026-09-11 用户批准：stop 停止本仓库遗留进程；恢复重构前 Chat 视觉，保留新逻辑；已授权 Graph 自动成为可聊天 Agent，Agents 对齐展示。该决定替代 02/03 中 Chat 并列 Agent/Graph 入口的设计，不修改 GraphHarbor 业务边界。

## 方案

- 脚本使用可执行命令与精确 app 工作目录识别进程，覆盖无 PID 文件的手工启动；TERM 后等待、必要时 KILL，只处理本仓库，不能只根据端口杀进程，也不信任失效 PID 文件。
- 视觉以 Git 612fbde 的 BaseChatTemplate/ChatMessageList 及现有 pw-chat 样式为准，复用布局、字号、气泡、标识、工具栏和输入框；继续使用新 SDK/Transcript/审批/回执逻辑。
- Agent 列表按当前 Graph 目录和项目有效授权自动对齐，首次读取幂等补齐缺少的平台配置，数据库 project+graph 唯一约束防重复。按现有策略，无显式 overlay 时继承允许；显式禁用/Graph 离线不出现在可选列表。已有名称、模型、工具配置和历史身份保留。
- Web 仅选择 Agent；Graphs 管理页的聊天入口解析对应 Agent。Agents 移除新建/删除流程，保留现有配置详情。撤权由执行网关再次校验，历史仍可读。不新增服务、表或 GraphHarbor 业务代码。

## 任务

- [x] 修复 stop 所有权识别并验证本仓库进程停止、无关进程存活。
- [x] 自动 Agent 对齐，验证重复读取、现有配置、授权变化与权限拒绝。
- [x] Chat/Agents/Graphs 导航归一。
- [ ] 完整旧 Chat 工作台恢复；用户后续确认以 Git `8056869` 含高级模型选择器的完整版本为准，取代前文局部视觉基线。差异见 [09](09-chat-workbench-restoration-audit.md)。
- [x] 前序类型/lint/定向测试及真实浏览器回归，见 12。
- [ ] 完整工作台补齐后的最终回归、截图与实施记录。

## 追加验证范围

- SDK scoped 消息投影的父子数据覆盖与终态/回放竞态，通过锁定补丁修正；补丁及复现测试见 [12 实施记录](implementation/12-visual-agent-and-local-stack.md)。
- 用户明确批准备份后重建旧本地 Platform API 开发库。备份、27 表行数核对、新 20 表初始化及真实登录/目录验证已完成，详情同上。
- 双浏览器同 Thread 入队、完整文件/Skills API、PTY 仍为 deferred。

## 验证记录

2026-09-11：最终 Web 77 passed / 1 skipped，API Agent 4 passed、网关流与 adapter 16 passed；真实浏览器三尺寸并行/嵌套 3 passed，真实 Graph Agent/移动端 3 passed。类型检查、lint、生产构建及进程启停实测通过。截图与日志索引见 [12 实施记录](implementation/12-visual-agent-and-local-stack.md)。跳过的 SDK chain 单测不计为通过，真实链路由单独浏览器验收覆盖。

## 状态

`partial`：Agent 入口与进程启停的既有验收保留；旧工作台展示组件已直接取回并接入当前 SDK；历史摘要数据与部分专项验收仍待补齐。功能缺口和验收任务见 [09](09-chat-workbench-restoration-audit.md)，最新实施见 [14](implementation/14-copy-original-chat-components.md)。既定 deferred 项保持后置。
