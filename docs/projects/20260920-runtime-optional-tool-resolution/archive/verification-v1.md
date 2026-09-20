# 已取代：第一版验证计划和记录

验收以 [新版总览](../README.md) 的编号专题为准；本文件只保留第一次立项记录。

## 当前记录（2026-09-20）

- 已静态核对：默认全量校验、Policy/Principal 同码、项目缺省允许、Middleware 双边界过滤、刷新非法响应归空行为。
- 原文四个新增工具差集与刷新恢复是历史现场证据，本次未独立复现。
- 本轮仅创建规划文档；业务单元、集成、E2E、性能及回滚验证均未执行。
- 文档检查：`git diff --check` 通过；使用 Python 3 核验四份专项文档的 31 处相对链接及源码路径，全部存在。首次使用 `python` 因本机无该命令失败，改用 `python3` 后通过。
- 当前结论：规划中，不能标记修复或验收通过。

## 单元验证

主要文件：`apps/runtime-service/tests/runtime/test_contracts_and_resolver.py`。

| 输入/条件 | 批准推荐方案后的预期 |
|---|---|
| 未传 tools / tools=null，全部授权 | 保持原默认工具集合 |
| 默认项不在 Policy | 排除该项，其余保留，记录 policy_not_allowed |
| 默认项缺 Principal 权限 | 排除该项，记录 principal_permission_missing |
| tools=[] | 无 optional，required 仍严格校验 |
| 显式请求未授权项 | 保持 optional_tool.not_allowed |
| 显式请求未声明项 | 保持 optional_tool.not_declared |
| required 缺任意一层权限 | 保持 required_tool.not_allowed |
| 默认 optional 全被排除 | 模型和 required 合法时可解析为空工具对话 |
| 重复、坏类型、required/optional 重叠 | 保持错误，不被集合求交吞掉 |
| 输入顺序不同但语义相同 | resolved/config_hash 稳定 |
| null 与 [] | Context hash 保持不同 |
| 旧快照与新快照 | 解析/哈希兼容，无秘密字段 |

诊断测试：公开 code/field 兼容；服务端原因正确；无 token、凭据、完整权限输出；重复解析不造成每个工具节点刷同一条告警。

## 集成与安全验证

- [ ] `apps/runtime-service/tests/middlewares/test_runtime_middleware.py`：用记录型模型 handler 验证被排除工具 schema 不进入请求；伪造该工具调用必须在执行 handler 前拒绝。
- [ ] `apps/runtime-service/tests/services/dearflow_agent/`：根 Agent 与 researcher 子 Agent；模式禁用、治理开关关闭、显式 MCP 授权先于网络连接；审批机制不受默认收敛绕过。
- [ ] `apps/runtime-service/tests/services/test_r4_capability_demos.py` 及其他 Resolver 调用者：既有 required、显式 tools、默认工具行为符合新约定。
- [ ] `apps/platform-api/tests/test_runtime_catalog_delegation.py`：上游错误/格式错误/部分非法/重复 key 均不修改旧快照或成功同步时间；合法空目录按批准语义处理；事务失败无部分落库。
- [ ] 同名刷新 catalog_id 稳定、已有项目禁用不变；新工具缺省允许行为有明确断言，避免以“只刷新元数据”掩盖授权变化。
- [ ] `apps/platform-api/tests/test_runtime_gateway_runtime_contract.py` 与 `test_runtime_gateway_event_redaction.py`：签发允许集、Context、错误安全展示不回归。

## 端到端验证（隔离项目，实施后执行）

1. **原始故障复现：** 保留有效模型及基础工具，让目录缺少一个 DearFlow 默认可选工具；在旧实现记录失败，在新实现用相同条件验证普通对话流式完成。
2. **正常项目禁用：** 管理员禁用可选工具，刷新后仍禁用；从 platform-web 经 platform-api 到 runtime-service 发起默认对话成功。核对模型实际工具集合与执行审计，不能只看页面无红字。
3. **显式越权：** 使用相同项目显式选择被禁用项，必须拒绝且无工具副作用；required 缺失也拒绝。
4. **受控刷新恢复：** 新工具同步后新签发 policy 可按既定授权规则使用；旧 delegation 不被当成已自动更新，记录 run/request/policy 关联信息。
5. **恢复与前端：** 覆盖 DearFlow/Showcase/reference_agent 的新 Run、历史线程继续、审批恢复；检查 null 与 [] 没被前端转换，提示不泄露内部配置。
6. **坏响应保护：** 模拟能力接口格式错误/超时，平台保存旧目录、已有允许集和禁用项，错误可定位。

每项记录：环境、代码版本、执行命令或操作、Run/Request ID、预期与实际、证据位置；不保存凭据。数据库构造仅限隔离测试环境。

## 性能与回滚

- [ ] Resolver/Middleware 无新增网络或数据库访问；记录普通对话与多次工具调用的日志条数和耗时，确认未因重复解析产生明显退化。具体阈值以现有基线评审确定。
- [ ] 同步采用完整校验后事务落库；评审若纳入自动同步，补多进程并发、Runtime 晚启动与仅升级 Runtime 场景。
- [ ] 隔离环境回退旧解析版本，检查 HTTP/JWT/snapshot 兼容并记录旧全量拒绝行为；验证目录数据不会随代码自动回退。
- [ ] 用旧 Runtime 能力重新刷新，确认目录增删结果及项目禁用仍保留；未经批准不批量覆盖授权数据。

## 执行入口

实施后在各服务既有环境执行定向 pytest，再按改动范围运行项目既有 lint/类型检查；不得将下面计划命令当成执行记录。

```bash
cd "apps/runtime-service"
uv run pytest tests/runtime/test_contracts_and_resolver.py tests/middlewares/test_runtime_middleware.py
```

```bash
cd "apps/platform-api"
uv run pytest tests/test_runtime_catalog_delegation.py tests/test_runtime_gateway_runtime_contract.py tests/test_runtime_gateway_event_redaction.py
```

最终四态由实施后的 verify-change 验收生成，未执行项如实保留。
