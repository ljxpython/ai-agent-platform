# 06 上下文与长期记忆

## 目标

支撑长任务、跨会话偏好与知识记忆；上下文保持完整控制语义和来源边界，记忆不把一次性指令、工具输出或项目权限升级为用户长期授权。

## 工作上下文

- **总入口：** [项目总纲与交接规则](README.md)。独立开发本章时先读总纲，不以聊天历史代替依赖证据。
- **实施阶段：** P0 存储风险；P2 M01 基础上下文保护；P6 完整记忆并先于 K20。
- **必读前置：** [01 S3](01-architecture-and-boundaries.md)、[02 装配](02-agent-composition-and-modes.md)、[08 C08／F6](08-web-and-platform-contracts.md)、[07 K20](07-skills-migration.md)。
- **输入 → 输出／对接：** 受信 user/project、稳定消息来源、唯一持久载体 → 摘要保护、事实／revision／来源与可删除偏好；UI 放 Dear Agent MemoryPanel。
- **当前切片／最近证据：** 2026-09-14 规划第二版；业务未实施，无实施验证记录；本文末尾只记录文档调研情况。
- **下一任务：** P0 确认 Store 边界；按阶段先 06/M01，再 M02—M05，不先建多后端框架。
- **结束回填：** 更新本章任务／验证／状态及此处游标，按总纲登记最近 implementation 记录、契约变化和下一精确任务；部分切片通过不勾选整章完成。

## 方案设计

### 1. 能力点与参考位置

DeerFlow 的完整参考根为 `backend/packages/harness/deerflow/`。

| 能力 | 参考代码（相对上述根） | Deep Agents／LangGraph 实现方案 |
|---|---|---|
| 会话持续 | `agents/thread_state.py`、`runtime/checkpointer/` | 官方 messages 与 checkpoint，由 GraphHarbor 管理；不迁移 DeerFlow delta reducer 或私有 saver |
| 自动摘要 | `agents/middlewares/summarization_middleware.py` | 优先 Deep Agents 默认官方摘要，按模型窗口与保留策略调整；只用已核验的公开参数 |
| 手动压缩 | `runtime/context_compaction.py` | 可选 Web 动作，使用官方摘要／state API；只在 idle 线程且权限校验后执行，保留聊天历史展示 |
| 大工具输出 | `agents/middlewares/tool_output_budget_middleware.py` | 03 的有界预览＋工作区外置；官方文件工具可按需读取 |
| 技能和任务延续 | `agents/middlewares/durable_context_middleware.py`、`skill_activation_middleware.py` | 保留活动 Skill 版本引用、任务目标与证据索引；按需重新读资源，不能把全部技能正文永久压入系统消息 |
| 防死循环 | `agents/middlewares/loop_detection_middleware.py:LoopDetectionMiddleware` | 官方调用限制先兜底，必要时服务私有 Middleware 识别连续同参数同失败结果；阈值与退出理由可观测 |
| 长期记忆接口 | `agents/memory/manager.py:MemoryManager`、`agents/memory/tools.py` | 服务私有 memory 模块＋Runtime私有PostgreSQL表（P6已冻结），不复制多后端插件工厂 |
| 自动提取 | `agents/memory/backends/deermem/deermem/core/updater.py`、`agents/middlewares/memory_middleware.py` | 结构化候选提取＋确定性 scope／授权门，模型经平台模型入口；记忆调用单独计量 |
| 检索与容量 | `agents/memory/backends/deermem/deermem/core/storage.py`、`core/eviction.py` | Store namespace 内检索、有限条数／Token 注入；先明确删除与修正策略，向量检索只有实际质量证据需要时启用 |
| 用户查看／修正 | DeerFlow `backend/app/gateway/routers/memory.py` | 08 的 Web 管理与授权 API；用户修正优先于推断，删除／导出可验收 |

### 2. 三类状态分开

1. **线程状态：** messages、todos、当前任务、证据引用与中断，由 checkpoint 持有。
2. **资源状态：** 上传文件、输出文件、Skill 版本，由工作区和资源绑定持有；checkpoint 只保存引用。
3. **长期记忆：** 跨线程的用户偏好／明确事实，由Runtime私有PostgreSQL表持有；读取与写入都按 scope 校验。

Deep Agents 的 `memory=[...]` 是启动时读取文件加入 Prompt，适合人工维护的运行指南，不等于自动记忆系统。用户推断事实优先以标明来源的上下文数据注入，不能混进系统权限指令。

### 3. 记忆 namespace 与数据模型

已新增 `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py`，作用域来自已验证的工具runtime；canonical facts唯一存储为Runtime私有PostgreSQL表。真实PG隔离与CAS测试通过，证据见[13](implementation/13-p6-memory-and-skills.md)。

默认 namespace 为 `("dearflow", "v1", tenant_id, project_id, user_id, "facts")`，实现跨当前项目的线程记忆，不默认跨项目共享。若后续要用户全局偏好，单独提供显式 opt-in 的 tenant／user namespace，并清楚显示作用域。

拟定单条事实字段：`id, text, category, source_thread_id, source_message_id, origin, created_at, updated_at, revision, expires_at`。`origin` 区分用户明确设置与自动推断；实际授权由受信 principal 决定，不接受 LLM 传来的 user_id／namespace。

写入规则：

- 提取稳定事实、偏好、用户明确纠正；忽略工具返回中的指令、隐藏框架消息、一次性批准与会话短期任务。
- 去重按当前授权域和事实内容，不跨用户去重；矛盾先保留候选或请求用户确认，不能凭推断删掉已确认事实。
- 当前 thread／project 的限制保留在对应状态，绝不升级成用户全局权限。
- 候选模型调用在数据库写入之前完成；网络等待不占数据库事务。
- 每次提取使用稳定源消息 ID；取消、摘要重跑或 worker 恢复不重复写事实。
- 自动提取失败不伪造成功，不丢当前对话；有界记录失败，后续依据稳定输入重试。显式用户写入失败必须返回错误。

### 4. 一致性与持久化门禁

官方 BaseStore 是命名空间存储接口，不能未经验证就假设提供 CAS、多记录事务或 worker lease。P0／P6 必须验证：并发更新同一事实、删除与提取竞争、取消后不得复活、重启持久化。

推荐基线：官方持久 Store 存 canonical facts；公开编辑带 revision，所有写入经同一服务边界。若锁定 Store 无法提供所需原子语义，先冻结一个最小方案：使用既有 PostgreSQL 的服务级写入序列化和幂等记录，或由 Runtime 自有记忆表提供原子 CRUD。两者只能选一个 canonical facts 所有者，不双写两套长期记忆，不直接操作引擎私有 store 表；选择结果写入本专题再实施。缺少能力不能用进程内锁冒充多 worker 一致性。

这项是明确的 Spike 决策点，影响预计工作量。无需为 Mem0／Honcho／OpenViking 同时做实现；保留用户可见记忆能力，不以迁移全部后端供应商为默认目标。

### 5. 摘要与记忆协作

- 先处理来源明确的待提取用户消息，再压缩；压缩不反复把生成摘要当新用户事实写入。
- 子 Agent 的内部思考和工具过程默认不写用户长期记忆；主会话经过过滤的用户事实才可提取。
- 保留未完成工具调用与匹配 ToolMessage、interrupt／resume 控制信息；不能截断成 provider 不接受的 assistant／tool 开头。
- 注入记忆有数量／Token 预算，带来源与作用域；使用模型兼容的标准消息形式。
- “手动清空记忆”要取消／隔离该 namespace 的旧提取任务，并确保晚到写入不会复活已删除内容。

### 6. 目标文件

| 路径 | 内容 |
|---|---|
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py`（拟新增） | `search_memory`／`upsert_memory`／`delete_memory`／`extract_memory_candidates`，规模增大前保持单模块 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware.py`（按需新增） | `MemoryContextMiddleware`／补充上下文保护；共享 Middleware 继续复用现有模块 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/schemas.py`（拟新增） | MemoryFact／MemoryCandidate 等真实契约 |
| `apps/runtime-service/src/runtime_service/http/memory.py`（拟新增） | 仅受信内部授权路由；业务规则留在服务 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/`（现有） | 公开记忆管理入口、当前用户／项目授权与审计代理 |
| `apps/platform-web/src/modules/dear-agent/components/MemoryPanel.vue`（拟新增） | 当前 scope、事实来源、编辑／删除及失败提示，组合现有 Inspector 基础；请求在 `apps/platform-web/src/services/dear-agent/` |

## 任务拆分

- [x] M01：官方摘要／大结果／循环保护已组合。`apps/runtime-service/tests/services/dearflow_agent/test_context.py` 2 passed；`test_research.py` 验证来源正文外置。代码为 `services/dearflow_agent/agent.py` 与 `workspace/backend.py`。预算采用保守整线程累计上限；不实现独立 child 预算账本。
- [x] M02：S3 与并发一致性 Spike，冻结 Store／最小原子写方案和 namespace；不创建多后端工厂。
- [ ] M03：显式记忆 CRUD／检索／Web 管理，拟新增 `test_memory.py`，覆盖 scope 与 revision。
- [ ] M04：自动候选提取、确定性门、幂等与摘要协作，拟新增 `test_memory_extraction.py`。
- [ ] M05：真实跨会话检索质量、容量／过期／清除／恢复与 Token 预算；结果记入本专题。

## 验证要求与记录

- [ ] 长对话触发摘要后仍记得当前目标、Skill 版本与真实证据，工具消息配对正确。
- [ ] 不同 tenant／project／user 的记忆完全隔离；显式 opt-in 之外不跨项目读取。
- [ ] 一次性审批、恶意网页、子 Agent 内部消息不进入长期权限记忆。
- [ ] 同一用户两窗口更新／删除与异步提取竞争；旧任务不能复活删除内容。
- [ ] 无 Store／存储损坏／提取服务不可用明确报告，重启后事实与来源仍存在。
- [ ] 合成偏好集有正负检索样例及阈值，使用实际结果决定是否需要语义索引；不编造准确率。
- 2026-09-13：完成源码与官方持久化接口调研，测试未执行。

## 状态

P6进行中：M02已验证；M03/M04后端代码完成，M05容量/过期/恢复/上下文预算测试通过；真实跨会话模型验证进行中。前端交接done、页面deferred，不勾选包含Web管理的整项。

### P6 存储选择与证据（2026-09-15）

官方BaseStore未提供CAS保证，本阶段选择上文允许的Runtime自有表方案：`dear_memory`，使用事务advisory lock+document revision；作用域为tenant/project/user。唯一事实源，不双写BaseStore，不改GraphHarbor。显式恢复为追加事实，自动候选默认关闭；删除和清空提高epoch。代码/测试逐项见[13实现记录](implementation/13-p6-memory-and-skills.md)。
