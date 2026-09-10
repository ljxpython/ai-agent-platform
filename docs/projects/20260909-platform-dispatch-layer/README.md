# Platform Dispatch Layer Implementation

## 项目概述
- **时间：** 2026-09-09 至 2026-09-10
- **目标：** 实现统一的 dispatch_agent_run 层，标准化 LangGraph run 创建流程
- **负责人：** @lijiaxin
- **状态：** deferred（2026-09-10 统一入口职责纳入已确认的 platform-api 重构方案，暂缓独立实施）

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** platform-api, runtime-service
- **改动级别：** 链路改动
- **预计工作量：** 1.5 人天

## 关键决策

以下为旧方案，尚未实施。当前已有 `RuntimeGatewayService.launch_runtime_run()`；新方案见 [运行网关专题](../20260910-platform-api-refactor/02-runtime-gateway.md)。不再直接新增同义 dispatch 层；默认 interrupt、webhook 和私有协议标记需按实际产品/上游能力重新评审。

1. 参考 open-swe 的 dispatch.py 实现统一 dispatch 层
2. 默认使用 Protocol v2 配置（stream_mode, stream_subgraphs）
3. 默认 durability="sync" 和 multitask_strategy="interrupt"
4. 支持 webhook 回调机制

## 背景
来源于 graphharbor 业务边界分离项目（专题 04），从 graphharbor 迁移而来。

参考实现：`/Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/dispatch.py`
