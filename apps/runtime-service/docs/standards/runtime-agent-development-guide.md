# Agent 设计与开发指南

> 适用范围：在本仓库 runtime-service 中新增或扩展 Agent。本文说明现有架构的使用方法，不新增权限或协议。
> 核对日期：2026-11-08。依据：当前 Graph 配置、组合根与测试源码；不代表本轮重新执行了运行验收。
> 配套：[开发规则](runtime-service-development-standard.md) · [案例与资料导航](runtime-service-reading-guide.md) · [运行与验证](runtime-service-onboarding-and-verification.md)。

## 1. 开发前先定义什么

在 Service README 或所属项目方案中回答以下问题，再选框架、工具和目录。单服务任务按根 AGENTS 判断是否需要轻量记录，不为每个 Agent 强制新建治理项目。

| 设计问题 | 必须明确的内容 |
|---|---|
| 业务目标 | Agent 为谁完成什么任务；哪些事情不做 |
| 输入与输出 | 聊天消息、附件或结构化输入；回复、文件或真实外部动作；失败如何表现 |
| 执行路径 | 由模型选择工具，还是由代码规定步骤/分支；哪里需要暂停和恢复 |
| 工具与副作用 | 每个工具读取/修改哪些资源；是否允许重试；结果未知时如何回查 |
| 权限与审批 | tenant/project/thread 范围，主/子角色工具集，哪些动作需要 HITL |
| 状态与资源 | 哪些进入 graph state，哪些放 Workspace；是否需要重启恢复/后台任务 |
| 平台能力 | 是否需要 Plan、附件、技能、子 Agent、调度、长期记忆；逐项选，不默认全开 |
| 验收 | 一个正常任务、一个拒绝/错误任务；有副作用时再补审批、恢复不重放和取消 |

例：只读“知识问答助手”先定义查询来源、项目权限、引用与无结果行为；不因为名称叫 Agent 就增加 shell、Workspace 写入、子 Agent 或专属 HTTP 服务。

## 2. 选择哪一种 Agent

| 需求 | 起点 | 优先参考 |
|---|---|---|
| 模型按问题调用少量业务工具 | `create_agent` | reference_agent 当前源码与测试 |
| 明确步骤、条件分支、审批/恢复点 | Typed `StateGraph`，需要推理的节点再调用 Agent | workflow_demo |
| 文件工作、按需 Skills、委派或复杂长任务 | `create_deep_agent`，显式选择 Backend、工具与角色 | deep_agent_demo 理解机制，Showcase 学平台装配 |
| 为现有图增加一种业务动作 | 先扩展该 Service 的工具与装配 | 原图组合根及对应测试 |

不要仅为“以后可能复杂”采用 Deep Agent 或多 Agent；也不要用 Prompt 模拟必须可靠执行的业务流程。官方概念见[资料导航](runtime-service-reading-guide.md#官方资料怎么查)。

## 3. 当前模块架构

```text
Platform API：身份、项目策略、模型目录和受管调用
    ↓ 受信委托 / Context / 模型连接引用
GraphHarbor：Graph 加载、Thread / Run / checkpoint / Worker
    ↓ langgraph*.json 中的 graphs.<graph_id>.path
runtime_service/graphs/<graph_id>.py：稳定部署入口
    ↓ get_agent(config)
runtime_service/services/<service>/agent.py：业务组合根
    ├── runtime/：Context、身份/策略解析、模型连接、能力声明
    ├── middlewares/：授权执行、预算、恢复/错误、隐私等横切能力
    ├── tools/、workspace/、observability/：可复用的平台能力
    └── 本 Service 的 prompts / tools / schemas / workflow / subagents / skills
```

这不是一条必须按图中顺序调用每个模块的固定流水线；具体生命周期由所选组合根和测试约束。

| 模块 | 负责什么 | 新 Agent 不应放在这里的内容 |
|---|---|---|
| `graphs/` | 对外稳定的 Python 导出；按需接入现有调度/后台完成包装 | 业务工具实现、大型 Prompt、第二套构图逻辑 |
| `services/<service>/agent.py` | 身份/Context/模型解析，显式装配图、工具、middleware、资源及追踪 | 把所有业务操作、HTTP client 和数据处理揉进组合根 |
| `runtime/` | 不可变运行值、策略解析、受管模型连接、能力声明 | Service 专有业务流程、模型生成的授权 |
| `middlewares/` | 跨调用/跨工具的统一运行约束 | 某个工具独有的业务动作 |
| `tools/` | 多个 Agent 已复用的文档、图片、知识等工具 | 为一次使用提前抽象出的万能工具层 |
| `workspace/` | 线程资源、文件引用、执行位置与沙箱边界 | 通过任意宿主路径绕过当前线程绑定 |
| `observability/` | 统一追踪、诊断和用量 | 打印密钥、原始身份令牌或私有运行配置 |
| `http/`、`webapp.py` | Runtime 专属公共 HTTP 接口和应用生命周期 | 每新增 Agent 就再建一个 FastAPI 服务 |

**业务边界：** Platform API 管理策略与目录，Runtime 验证并执行；GraphHarbor 持有运行/恢复事实。业务 Agent 不重建用户管理、模型配置中心、Run 队列或 checkpoint 状态机。

## 4. 新 Service 的目录怎么分

下面是职责示意，不是要求一次创建全部文件：

```text
src/runtime_service/
├── graphs/<graph_id>.py
└── services/<service_name>/
    ├── __init__.py
    ├── agent.py           # get_agent：唯一业务组合根
    ├── README.md          # 用途、边界、入口、工具、配置、验证
    ├── prompts.py        # 有独立提示词时
    ├── tools.py          # 有私有业务工具时；规模确有需要再变 tools/
    ├── schemas.py        # 有业务输入/输出或状态时
    ├── workflow.py       # 有确定流程时
    ├── subagents.py      # 有明确委派角色时
    ├── backend.py        # 需要服务特有资源适配时，优先复用公共 Workspace
    └── skills/           # 确有按需知识资源时
tests/services/<service_name>/
```

- 正式业务 Service 放 `services/<service_name>/`；机制教学示例放 `services/demo/`。
- 入口遵循 `async def get_agent(config: RunnableConfig) -> Pregel`。保持 `graphs/` 地址稳定，业务文件组织留在 Service 内。
- Prompt 只放文本或纯渲染逻辑，不读 env、不发网络请求；密钥和真实宿主路径不进入 Prompt。
- 业务工具先放本 Service；已有公共能力直接复用。新增 Service 不通过导入另一个 Service 的私有 helper 取得业务能力。
- 不创建空目录、空 schemas 或通用 Builder。目录和函数大小的现行建议见[代码粒度规则](runtime-service-development-standard.md#新增代码粒度规范)。

## 5. 组合根必须理解的生命周期

先读 [reference_agent/agent.py](../../src/runtime_service/services/reference_agent/agent.py) 的 `get_agent()` / `_build_agent()`，再读所选高级案例对应位置。

1. **区分探测与执行。** schema/state/checkpoint 读取不应获取真实模型连接、启动 MCP/容器或创建线程资源。探测图必须能描述 schema，但不能借探测身份执行任务。
2. **取得可信运行事实。** 使用现有身份/Context 解析与校验；不能从模型输入、客户端任意 configurable 或 Prompt 创建权限。
3. **解析模型与服务默认值。** `AgentDefaults` 定义服务默认；受信策略与 Context 经 resolver 约束后再构建模型。正式平台模型通过受管引用获取连接；不要复制教学用 key 或另开一套模型配置路径。
4. **按实际角色装配能力。** 工具实例、声明名称、执行授权、Plan 白名单、子角色能力保持一致；声明工具存在不等于授予用户权限。
5. **接入运行约束。** 依所选当前组合根保留 RuntimeConfig、预算、错误/重试、取消和隐私等必要行为；不同图的列表并不完全相同。
6. **返回图并接统一追踪。** 私有运行信息保持私有，真实身份元数据从受信事实获取；不把凭据写回图状态。

不要把“拓扑稳定”理解为可以缓存带着某个用户模型连接、授权或 Workspace 的 graph。当前 reference_agent 也会按运行事实构图；是否复用必须依据资源绑定和测试，不能照抄早期“所有静态图只编译一次”的描述。

Workflow 教学例的 `workflow.py:build_graph()` 目前仍显式使用 `InMemorySaver()`，内层 `checkpointer=True`；这是需要识别的案例限制，不是生产持久化的推荐方式。新生产 Workflow 不应照搬这个本地 saver；必须核对底座生命周期并验证跨进程恢复，不能因图已注册就宣称持久化已通过。

Middleware 的顺序影响 before/after/wrap 行为。先定位现有装配测试，例如 [reference 顺序测试](../../tests/services/reference_agent/test_middleware_order.py)，再有针对性地调整；不要按名称随意排序，也不要给所有 Agent 机械复制同一个列表。

## 6. 从设计到接入的具体步骤

| 步骤 | 改动位置 | 完成判断 |
|---|---|---|
| 1. 写设计与边界 | 新 Service README / 已有项目方案 | 第 1 节的问题都有答案；选定最小 Agent 类型和参考案例 |
| 2. 实现业务单元 | 本 Service 的 tools/prompts/schemas/workflow | 输入有校验，输出有界，外部动作真实；业务单元先可独立验证 |
| 3. 装配执行图 | `services/<service>/agent.py` | 保留受信运行链路，探测与执行分开，工具/角色明确 |
| 4. 导出和注册 | `graphs/<graph_id>.py`、选定的 `langgraph*.json` | 配置路径可导入，描述正确；学习图不因存在就自动进入正式配置 |
| 5. 接通工具目录 | `runtime/capabilities.py:graph_tools()/tool_catalog()` | 新图工具能被目录列出，目录/默认工具/实际装配一致；项目授权单独验证 |
| 6. 声明可用能力 | `graph_capabilities()` 及相关公共接入点 | 只声明真实支持的能力；配置注册、schema、执行与平台表现一致 |
| 7. 按需接入高级能力 | 见下表 | 不需要的能力不加入；涉及对端契约时按根 AGENTS 升级改动级别 |
| 8. 验证与交付 | 对应 Service 测试、配置测试、README | 不只测试正常答案；按第 9 节交付可复核结果 |

当前 `runtime/capabilities.py` 从 [DearFlow capabilities](../../src/runtime_service/services/dearflow_agent/capabilities.py) 重导出 `graph_capabilities()`。这是当前需要查找的真实位置，不是在建议新 Agent 依赖 DearFlow 的私有实现；本指南不顺带迁移这一结构。

| 需要的能力 | 额外检查什么 |
|---|---|
| Plan Mode | Runtime `runtime/planning.py:PLAN_GRAPHS`、[API planning](../../../platform-api/src/platform_api/modules/runtime_gateway/application/planning.py)、capability、只读工具实例和审批恢复；详见现行 Plan 规则 |
| 定时或后台完成接续 | 查看 DearFlow/Showcase 的 graphs 包装及 `runtime/scheduled.py`、`runtime/background_completion.py`；不要对所有新图无条件添加包装 |
| 文件、附件、执行 | 公共 Workspace、FileRef、资源注册与清理；构图探测不初始化资源；local 与 Docker/remote 验证边界不同 |
| 上下文治理/子 Agent | 当前 schema、摘要/输出预算、父子状态隔离和角色权限；不能只打开开关就宣称支持 |
| 共享 Skills | 安装包资源与当前技能装配；检查 `pyproject.toml` package-data，不能只在源码目录里能读到 |
| 平台可用 | 目录发现、项目授权、实际运行与所声明 UI 能力；只修改 JSON 不代表已完整接入 |

新增 graph_id 会影响现有配置断言，例如 [test_r0_baseline.py](../../tests/test_r0_baseline.py) 对正式图集合的断言；应更新明确的预期并增加新图测试，不能删除断言来躲过检查。

## 7. 工具、Skills、子 Agent 和流程的规则

| 对象 | 设计与开发要求 |
|---|---|
| 业务 Tool | 一个清楚的业务动作，明确参数/schema、权限范围和副作用；敏感运行信息由受信链路注入，不让模型填写凭据或租户授权 |
| 只读与写工具 | 同时控制模型可见性和实际执行；重试只用于已确认安全的操作；外部写入结果未知时不盲目重放 |
| Skills | 按需读取的任务知识/资源，不是执行权限；不能因为加载了 Skill 就自动获得 shell、网络或写权限 |
| Subagent | 明确任务、输入、输出、工具集和预算；使用父图审查过的最小角色，不默认继承所有主图能力或无限递归 |
| Workflow | 明确 State、节点输入输出、边和恢复点；HITL 沿现有 interrupt/resume；副作用需考虑重放，不另建审批状态机 |
| Backend/Workspace | 状态文件与真实持久文件的边界写清；不把 StateBackend 演示当作生产沙箱/多租户隔离证明 |

最重要的约束：

- 身份、Context 哈希、租户/项目/线程、工具策略在执行边界校验；审批不替代授权。
- 取消和中断保持控制流，未知缺陷不能伪装成成功；不要用兜底 `except Exception` 吞掉所有情况。
- 文件和命令执行使用现有资源边界；Docker/remote 失败不能回退宿主 shell。local 仅限受信开发，不提供生产 shell 隔离。
- 输出、调用和耗时有明确边界；公共工具已有外置/截断能力时复用，不把完整大文件反复塞入上下文。
- 不自建 Agent 循环、工具 Registry、Run 状态机或通用 Agent Builder。
- 详细规则见[现行开发规范](runtime-service-development-standard.md)。安全/权限/契约描述与实现不一致时记录差异，交由人工判断，不能自行降低校验。

## 8. 按什么顺序看案例

1. 普通 Agent：reference_agent 当前 `agent.py` → 私有工具 → 对应 Service 测试。
2. 业务流程固定：workflow_demo 的 schemas/workflow/agent → 审批与 resume 测试。
3. 需要文件/Skills/委派：先看 deep_agent_demo 或 backend_demo 的机制，再看 Showcase 的实际资源与权限装配。
4. 需要更复杂生产能力：按问题查 DearFlow 组合根、工具及测试，不整包复制记忆/媒体/调研能力。

完整路径与限制见[案例选择表](runtime-service-reading-guide.md#案例选择表)。特别注意：小 Demo 的 fake/进程内资源只证明机制；案例 README 中的旧版本、旧 Context 字段和旧部署描述不作为新 Agent 的契约。

## 9. 怎样验证和交付

先做当前 Service 的确定性单元/组合验证，再按引入的边界补真实资源验证。命令和环境要求见[运行与验证](runtime-service-onboarding-and-verification.md)。

交付前逐项说明：

- [ ] Service 用途、输入输出、目录职责、选型理由和不支持范围已写清。
- [ ] Graph 注册、工具目录、能力声明、包内资源和实际装配一致。
- [ ] 正常任务可完成；非法输入、越权、失败和空结果有明确结果。
- [ ] schema 探测不触发外部副作用，也不能执行真实任务。
- [ ] 有审批时覆盖批准/拒绝/resume；有写操作时检查恢复不重复执行。
- [ ] 子角色不能获得未声明权限；取消、预算或隐私失败不会被成功包装。
- [ ] 使用 Workspace/数据库/外部 MCP 时补对应真实集成证据；需要平台使用时跑完整受管调用链。
- [ ] 记录实际命令、环境、通过/失败/跳过与未验证边界。fake 成功、skip 或服务健康不能冒充真实业务验收。

在关联 Worktree 开发时，先读根级[资源隔离规范](../../../../docs/standards/worktree-development.md)，只使用本环境依赖、地址和资源。本文不授权创建生产资源、迁移生产数据或发布。
