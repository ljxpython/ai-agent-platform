# Runtime Agent 组合根脚手架重构与 DX 体验治理 (RuntimeAgentHarness)

## 项目概述
- **时间：** 2026-09-30 至 2026-10-15
- **目标：** 解决 Runtime 执行层 Agent 组合根样板代码严重超标（150+行胶水代码）、安全验签逻辑各 Agent 重复建设、测试夹具构造心智负担重等问题，提炼高内聚的 `RuntimeAgentHarness` 框架脚手架与通用测试工具，实现安全防线下沉与算法业务关注点彻底解耦。
- **负责人：** @laowang
- **模板类型：** 标准模板
- **状态：** 规划中（待方案评审）

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** `runtime-service`
- **改动级别：** 治理改动（架构重构）
- **预计工作量：** 5 人天

## 关键决策
1. **安全下沉而非弱化**：严禁为了“简化代码”破坏切斯特顿栅栏；所有 Delegation 校验、`context_hash` 比对、工具黑名单物理剔除、多租户工作区隔离由框架级 `RuntimeAgentHarness` 统一收敛托管，业务代码只聚焦图状态机与 Prompt。
2. **高阶装饰器模式 `@runtime_agent`**：封装探测（Probe）与真实执行（Execution）的双重模式分支，对外向算法开发者暴露纯净的 `AgentBuildContext`。
3. **开箱即用的测试夹具工厂 `create_test_config()`**：彻底终结单元测试中手动拼装 30 行嵌套字典的恶劣开发体验。
