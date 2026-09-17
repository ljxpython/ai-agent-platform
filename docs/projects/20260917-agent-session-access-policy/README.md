# Agent 会话访问策略

## 项目概述
- **时间：** 2026-09-17 至待评审后确定
- **目标：** 让用户可为 Agent 对话选择受控的会话访问档位，减少逐操作审批，同时不绕过平台鉴权、工作区隔离和审计。
- **负责人：** @lijiaxin
- **状态：** 部分完成：Platform API、Runtime 与 Platform Web 已完成全部组件与单元验证；待全栈启动后跑最终 E2E 验收。

## 阅读顺序
1. [访问档位与边界](01-access-policy.md)：定义“完全授权”的实际含义和不可突破的安全边界。
2. [可信契约与审计](02-trusted-contract-and-audit.md)：定义前端请求、Platform API 签发和持久化审计。
3. [Runtime 执行](03-runtime-enforcement.md)：让已签发的档位决定 Agent 的 `interrupt_on`，而非相信浏览器。
4. [前端交互与验证](04-ui-and-verification.md)：选择器、升级确认、兼容策略及测试路径。

## 改动范围
- **影响服务：** `platform-web`、`platform-api`、`runtime-service`
- **改动级别：** 治理改动（授权边界与审计模型变更）
- **预计工作量：** 3 至 5 人天

## 关键决策
1. “完全授权”仅表示受控工作区内的已批准工具不再逐次 HITL；不表示 Agent 获得宿主机、项目外文件、平台 IAM 或任意网络权限。
2. 会话档位由 Platform API 校验、写入线程元数据并纳入 delegation token/context hash；Runtime 只信任该签发结果。
3. 高风险外部副作用（部署、发布、凭据、权限变更）始终保留审批，不能被会话档位关闭。
4. Platform Web 采用方案 A（ChatComposer 工具栏挂载，对齐 deepseek-harness）与方案 1（草稿态暂存与首发前置补发），已集成并完成类型与单元验证。
