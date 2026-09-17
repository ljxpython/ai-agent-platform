# Runtime 执行

## 目标

在 Runtime 的单一组合根根据可信会话档位构造审批表，既消除重复确认，又不改变底层工具权限和工作区隔离。

## 方案设计

当前根因位于：

- `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`：`create_deep_agent(..., interrupt_on=APPROVALS)`。
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py`：同样固定传入审批表。

新增小型纯函数 `interrupts_for_access_policy(policy, approvals, bypassable_names)`：

- `review` 返回原审批表。
- `workspace_write` 从原表删除白名单工具的审批项。
- 对不在白名单的审批项一律保留。
- 未知值抛出 Runtime 合同错误；不采用默认放行。

它只改变 `interrupt_on`，不会修改 `FilesystemMiddleware`、`WorkspaceMiddleware`、`FilesystemPermission`、工具权限、命令超时、模型/工具调用上限或 delegation 验证。这样直接复用现有的强制边界，改动小且能避免 Agent 进程被浏览器配置接管。

在 `RuntimeContext`、解析器和 `runtime_context_hash` 纳入 `access_policy`。各 graph 在通过 `verified_delegation_from_user()` 和 hash 校验后再使用该字段。Showcase 的 `subagents.py::build_subagents()` 中 general-purpose 具有独立 APPROVALS，必须同步应用父 run 策略；research 与 DearFlow researcher 保持原工具限制，chart-agent 保持现有工具作用域，不能把所有子 agent 误认为只读。

Showcase local 展示模式与 Docker 生产模式使用同一 `access_policy`，不在 Runtime 按 backend 分叉审批表。Docker 的文件挂载、网络限制、超时与资源约束必须用真实执行测试验证；审批策略本身不是隔离机制。业务 `request_information` 和 workflow `interrupt()` 不受本功能影响。

## 任务拆分

- [x] 扩展 `RuntimeContext`、`parse_runtime_context()` 与 `runtime_context_hash()`，未知值严格拒绝。
- [x] 新增 `runtime/access_policy.py::interrupts_for_access_policy()`，仅由 `dearflow_agent`、`showcase_demo` 和 Showcase 实现子智能体组合根调用。
- [x] Runtime Gateway 把服务端策略写入 Context 和 `platform_runtime` 后签发 hash。
- [x] 补齐 Runtime 单元测试和 Showcase 实际 graph 写文件免审测试。

## 验证要求与记录

### 验证要求
- [ ] `review` 的现有审批测试不回归。
- [ ] `workspace_write` 下 `write_file`、`edit_file`、`execute` 真正执行且不产生 interrupt。
- [ ] `present_artifacts`、`deploy_preview`、技能治理工具仍中断等待人工决策。
- [ ] 无签名或 hash 不匹配的 `access_policy` 无法执行。
- [ ] general-purpose 子任务免审与根任务一致；local/Docker 使用同一审批策略。
- [ ] 双服务 context hash 序列化一致，缺省旧请求仍兼容，未知值拒绝。

### 验证记录

#### 2026-09-17 验证
- ✅ `pytest tests/runtime/test_access_policy.py tests/runtime/test_contracts_and_resolver.py tests/services/showcase_demo/test_agent.py -k 'not graph_approval_runs_real_python_and_preserves_exit_code' -q`：37 通过、1 跳过、1 条 Docker 集成用例主动排除。
- ✅ Showcase graph 在 `workspace_write` 下写文件并直接完成，不产生 LangGraph interrupt；`review` 与高风险审批保持现有行为。
- ✅ Docker daemon 就绪后，`pytest tests/services/showcase_demo/test_agent.py::test_graph_approval_runs_real_python_and_preserves_exit_code -q` 通过：真实 `edit_file -> interrupt/resume -> execute` 在容器工作区完成并保留退出码。

## 状态

已完成：Runtime 实现和 Docker 执行验证已完成；整体项目仍待 Platform Web 接入和浏览器端到端验证。
