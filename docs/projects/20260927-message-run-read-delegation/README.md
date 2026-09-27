# 消息内部 Run 回查委托修复

- **启动日期：** 2026-09-27
- **级别：** 链路改动（Platform API 与 Runtime 的内部请求契约）
- **状态：** 部分完成：M1—M3代码与自动化验证已完成；现役跨服务真实链路未验证，需另行部署新API与新Runtime后验收。
- **来源：** [Delegation JWT v2 专项](../20260926-delegation-jwt-contract/README.md)的 C10 兼容限制
- **授权：** 用户在 2026-09-27 根因说明后明确回复“同意,继续”；本项目仅处理消息内部 Run 回查，不改变既有权限或 v2 JWT 契约。

## 导航

- [方案](plan.md)
- [任务](tasks.md)
- [验证](verification.md)

## 范围

Platform API 在消息请求内转发同一请求已签发的 `read` 委托；Runtime 验证它与消息委托的身份及资源绑定后，用它执行内部原生 Run 查询。原生资源白名单、Thread ACL 回查、消息入口操作约束和 GraphHarbor 保持不变。无迁移、依赖升级、部署或 Git 操作。

## 结果

代码与测试见[实现记录](implementation/01-message-run-read.md)；Phase和Final证据见[验证记录](verification.md)。当前可确认配对失败在内部查询和入队前拒绝；现役进程未切换到本次源码，不能将本机自动化测试当作线上链路通过。
