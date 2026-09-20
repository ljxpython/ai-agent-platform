# 已取代：第一版任务拆分

任务与状态以 [新版总览](../README.md) 的编号专题为准。

## Phase 0：立项与人工评审

- [x] 阅读原分析，核查 Resolver、DearFlow 装配、Middleware、Policy 构建及 Catalog 刷新。
- [x] 明确现场证据与本次静态核查边界，形成根因、方案对比和推荐。
- [x] 建立 README / plan / tasks / verification，登记 FEATURES。
- [ ] 人工评审 plan.md 第 7 节，记录批准人、时间与范围；当前未批准实施。

## Phase 1：默认工具语义与诊断

- [ ] 在 `apps/runtime-service/tests/runtime/test_contracts_and_resolver.py` 增加缺省/null/空列表/显式/required/Principal/Policy 矩阵；更新旧默认权限拒绝测试但保留严格分支。
- [ ] 修改 `apps/runtime-service/src/runtime_service/runtime/resolver.py` 的 `resolve_runtime_config()`；确定性排序、哈希、非法输入及纯函数约束保持。
- [ ] 核查 `apps/runtime-service/src/runtime_service/runtime/errors.py` 异常消费者，在既有边界记录安全诊断；不将全部策略传给 Web。
- [ ] 验证 `apps/runtime-service/src/runtime_service/middlewares/runtime_config.py` 的模型过滤、返回调用校验和工具执行拒绝一致；防止重复解析重复记录。
- [ ] 覆盖 DearFlow、Showcase、reference_agent、demo 与 mcp_probe 的共享调用；核查模式、环境开关、子 Agent、MCP 及 internal 例外。以 `rg resolve_runtime_config` 的当前调用点为清单。
- [ ] 更新 `apps/runtime-service/docs/knowledge/14-runtime-contracts-and-resolution-design.md`，对齐批准后的默认/显式语义；记录实现明细。

## Phase 2：受控刷新安全性

- [ ] 加固 `apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py` 的 `_normalize_tool_items()`、`refresh_tools()`：坏响应不写库，完整校验后事务更新。
- [ ] 在 `apps/platform-api/tests/test_runtime_catalog_delegation.py` 验证非法响应、合法空目录、部分非法条目、重复 key、上游失败及重复刷新。
- [ ] 验证 `RuntimePolicyOverlayService.build_delegation_policy()` 在刷新前后保留已有项目禁用、稳定 catalog_id，并明确新工具默认允许的现状。
- [ ] 评审新工具授权后，再决定是否添加发布同步；未批准自动同步时，本任务保留为后置，不声称已完成生命周期自愈。

## Phase 3：链路验证与交付

- [ ] 单元、集成、lint/类型检查及所有受影响关键链路验证。
- [ ] 隔离环境制造目录滞后和主动禁用；Web 发起默认对话，确认流式终态、模型工具集合及越权负向路径。
- [ ] 验证重新签发 policy、Context hash、snapshot、恢复与回滚，不把旧 token 当实时最新策略。
- [ ] 调用 verify-change 记录真实证据及 done / partial / blocked / deferred 状态，更新 README / FEATURES。

当前仅 Phase 0 的调研与文档完成；无业务实现或测试验收完成项。
