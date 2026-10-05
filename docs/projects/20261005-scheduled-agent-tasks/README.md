# 定时 Agent 任务

- **启动日期：** 2026-10-05
- **目标：** 项目内创建者私有的离线 Agent 定时执行、管理和追踪。
- **状态：** 本次后端交付 done：10 条平台接口、once/manual/预览/分页、执行前拒绝与留痕完成；GraphHarbor post41 双包已发布、平台已锁定安装、发布包隔离链路通过。前端由同事开发和浏览器验收、现役/远端平台部署均 deferred。
- **级别：** 治理改动（持续后台身份与执行权限边界）；未新增业务表或迁移。
- **影响：** platform-api、runtime-service、GraphHarbor；本次不改 platform-web。
- **回归限制：** 全量 API/Runtime 共 3 项外围失败，均用 HEAD 源码复现，详见 verification.md；不能称全仓回归全绿。

## 导航

- [方案、DeerFlow 对照和三层边界](plan.md)
- [任务与完成卡](tasks.md)
- [Phase/Final 验证证据](verification.md)
- [前端正式交接](frontend-handoff.md)
- [实现记录](implementation/02-platform-cron-and-execution-guard.md)

## 用户已批准决策（2026-10-05）

1. GraphHarbor 原生 cron/Run 为唯一事实源；平台无第二套 scheduler、cron/occurrence 表或 worker。
2. 首期 once/cron、fresh/reuse、暂停恢复、manual、历史与预览；interval/复制/通知/对话内建任务后置，前端由同事实施。
3. 每个 Run 构造图/工具前一次聚合核验身份/服务账号凭据/项目/Agent/模型/Thread；失效拒绝留痕且保留定义，运行中不周期重验。
4. 暂停/删除阻止未来派发，已接受 Run 按正常生命周期处理；编辑影响未来 Run，手动不消耗计划时间；无人值守审批转失败，不自动 approve。
5. 不保存用户 JWT；长期 marker 与通用签名分层，实时平台权限由 Platform API/Runtime 负责。
6. 用户明确授权 GraphHarbor 开发和使用 ~/.my_best/.env 直接发布；双包 post41 已上传并独立安装。此发布不代表生产平台应用部署。
