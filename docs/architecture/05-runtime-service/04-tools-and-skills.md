# 04-MCP 协议适配与 Skills 动态挂载 (MCP Protocol & Dynamic Skills Mounting)

## 模块定位与核心价值

智能体之所以被称为 Agent 而不是普通的问答机器人，核心就在于它具备通过**工具（Tools）**与**专业技能（Skills）**对外部物理世界产生影响的能力。但在生产环境中，如何安全、动态、可扩展地接入外部工具和专业知识，是衡量架构水平的试金石。

`runtime-service` 构建了一套支持**标准化协议**与**细粒度沙箱安全隔离**的扩展体系：
1. **MCP（Model Context Protocol）协议深度适配**：借助 `MultiServerMCPClient` 实现与 Anthropic 标准 MCP Server 的无缝握手。连接参数与鉴权凭证完全由服务端私有管控，严禁在上下文或工具入参中明文泄露；同时对三方 MCP 工具施加强制的只读安全断言（`readOnlyHint is True`）。
2. **企业级双轨制 Skills 技能系统**：划分预置系统公有技能（Public Skills，涵盖 20+ 类开箱即用的专业能力）与租户自定义私有技能（Custom Skills），支持通过 ZIP 包动态热加载与全生命周期版本治理。
3. **版本快照不可变性（Snapshot Immutability）**：智能体执行时基于当前技能集合的 `skills_hash` 固化快照。会话执行中途即使技能被更新或删除，正在运行的任务依然执行原快照，绝不受动态热更的副作用干扰。
4. **反自我篡改的文件系统沙箱（Sandbox Anti-Self-Tampering）**：挂载 `FilesystemMiddleware`，通过严格的白名单与黑名单机制，**强行禁止 Agent 擅自篡改自身的 `/skills/**` 目录或重写历史会话记录**。

---

## 零、知识前置与上下文串联（Knowledge Bridges）

### 1. 认知输入（前置模块输入）
- 依赖 [04-platform-api/04-catalog-management.md](../04-platform-api/04-catalog-management.md)：理解平台侧资产目录如何通过 Refresh 工作流同步图与工具元数据。
- 依赖 [03-hitl-and-interrupts.md](03-hitl-and-interrupts.md)：掌握任何对技能包产生写操作（`upload_skill`, `update_skill` 等）的工具调用，均受访问策略与 HITL 审批的拦截约束。

### 2. 本章核心流转
- **MCP 动态绑定解析**：解析 Thread 元数据中的 `runtime_resource_bindings`，从服务端加载安全连接配置并初始化客户端。
- **技能包校验与乐观锁更新**：通过 `SkillStorage` 检验 ZIP 包体积与文件结构，利用 `expected_revision` 校验实现防并发覆盖。
- **沙箱权限拦截**：在工具实际执行前，`FilesystemPermission` 阻断一切向系统保护路径发起的越权写操作。

### 3. 认知输出（支撑后续模块）
- 为 [07-agents/01-dearflow-agent.md](../07-agents/01-dearflow-agent/README.md) 提供 38 类核心工具与 20+ 专业技能的运行底层支撑。

---

## 一、核心架构澄清：我们常说的“薄封装”到底封装了什么？Tools / MCP / Skills / 沙箱来自哪里？

很多刚接触该项目的工程师常常产生一个巨大的认知偏差：
> *“既然我们宣传对 LangGraph 进行了‘薄封装’，那系统里的 Tools、MCP 协议、Skills 技能包和 Workspace 沙箱，难道全都是 LangGraph 原生自带的开箱即用能力吗？”*

**老王我必须斩钉截铁地骂醒这种糊涂想法：想得美！LangGraph 根本不管你的 Docker 沙箱怎么开，不管你如何防 Zip 炸弹，也压根不负责解析 `SKILL.md`！**

LangGraph 在整个底座中的定位极其克制且纯粹——它是一个**图计算状态机调度引擎（Pregel Execution Engine）**。它只负责状态图拓扑、节点转移、Checkpoint 检查点持久化与人机中断（`interrupt()`）。
至于各种异构的工具生态、外部协议与底层物理沙箱，是我们在其周边依据**“协议归一化（Protocol Normalization）”**思想构建的防御体系。

### 1. 多生态能力四分天下溯源表（谁负责什么，大白话讲透）

| 能力领域 | 真实生态来源 / 核心技术 | LangGraph 自身管不管？ | 本项目在底层到底做了什么“封装”与装配？ |
| :--- | :--- | :--- | :--- |
| **状态流转与图编排 (Pregel)** | **LangGraph 官方原生核心** | **管，且只管这个！**<br>负责 StateGraph 拓扑、超级步（Super-step）、状态快照持久化、流式事件分发。 | **坚守“薄封装”原则**：绝不魔改 LangGraph 源码，Agent 组合根直接导出标准的 `Pregel` 实例，控制面与图之间仅通过原生 `RunnableConfig["configurable"]` 注入上下文。 |
| **基础工具模型 (BaseTool)** | **LangChain 官方标准生态**<br>(`langchain_core.tools`) | **不管**。<br>LangGraph 只认继承自 LangChain 的标准 `BaseTool` 契约。 | **协议归一化底座**：定义统一的输入 Pydantic Schema、`ainvoke` 异步调用规范与结构化输出。无论是本地数据查询还是复杂算法工具，全部打包为标准 `BaseTool`。 |
| **MCP 外部协议工具** | **Anthropic 开放协议标准**<br>+ `langchain-mcp-adapters` (`MultiServerMCPClient`) | **完全不管**。<br>LangGraph 没有内置任何私有 MCP 连接池管理。 | **安全网关转译**：服务端私有环境变量安全托管 MCP 凭据（绝不向大模型泄露）；握手发现三方工具后动态转译为 `BaseTool`；**强制执行 `readOnlyHint is True` 只读断言与系统保留字防碰撞校验**。 |
| **Skills 动态技能体系** | **`deepagents` 开源框架**<br>+ 本项目自研治理模块 (`skill_governance.py`) | **完全不管**。<br>LangGraph 根本不知道什么是 `SKILL.md`，也不管技能包的发布。 | **双轨制技能治理与快照固化**：遵循 `SKILL.md` 规范，通过 `SkillStorage` 提供 ZIP 结构校验、解压安检、乐观锁版本控制（`expected_revision`）与运行时状态快照（`skills_hash`）强绑定。 |
| **操作系统级执行沙箱** | **本项目平台自研基础设施** (`runtime_service/workspace/`)<br>+ `deepagents` 虚拟文件系统抽象 | **完全不管**。<br>LangGraph 绝不负责 Docker 容器、断网隔离与物理命令截断。 | **防逃逸极苛隔离铁壁**：<br>1. `scoped.py`：单向 SHA-256 哈希物理隔离，杜绝绝对路径与 `../` 逃逸；<br>2. `execution.py`：启动断网（`--network=none`）、只读根、限内存 256MB、掐死 Fork 炸弹的无特权 Docker 容器；<br>3. `terminal.py`：1MB 环形缓冲区交互式 PTY 伪终端；<br>4. `archives.py` / `html_preview.py`：防御 100 倍解压炸弹与 Stored XSS；<br>5. `artifact_refs.py`：基于 Linux `dir_fd` + `os.link` 原子硬链接发布不可变交付物。 |

---

### 2. 什么是真正的“薄封装（Thin Wrapper）”？

老王经常看到很多团队一搞自研就把开源框架大卸八块，自己在外面套了十几层私有类，导致官方生态升级时自研代码全部沦为废纸。“薄封装”不是偷懒，而是一种克制的架构设计哲学：

```
                    【控制面请求 (Platform-API)】
                               │
                               ▼
        ┌──────────────────────────────────────────────┐
        │  1. 外部纯函数参数装配 (薄封装胶水层)            │
        │     - verified_delegation_from_user()        │
        │     - reject_untrusted_configurable() (消杀) │
        │     - resolve_runtime_config() (凭据拉取)    │
        └──────────────────────┬───────────────────────┘
                               │
            RunnableConfig["configurable"] 穿透传递
                               │
                               ▼
        ┌──────────────────────────────────────────────┐
        │  2. LangGraph 原生图引擎 (Pregel Core)        │
        │     - StateGraph 编译产生的原始 Pregel 实例    │
        │     - 原生 Checkpointer (Postgres/Memory)    │
        │     - 原生 interrupt_on 人机审批拦截          │
        └──────────────────────┬───────────────────────┘
                               │
                  节点流转触发工具调用 (tool.ainvoke)
                               │
                               ▼
        ┌──────────────────────────────────────────────┐
        │  3. 外挂式中间件与外挂式沙箱 (PEP 策略执行)     │
        │     - DocumentToolsMiddleware                │
        │     - FilesystemMiddleware (拦截篡改 /skills) │
        │     - WorkspaceBackend (Docker 断网沙箱)      │
        └──────────────────────────────────────────────┘
```

1. **零内核入侵（Non-Invasive）**：底座代码没有修改 LangGraph 的任何源码内部循环，也没有发明私有的节点状态转移语法；
2. **标准载荷穿透（Standard Payload Tunneling）**：运行时所需要的可信事实（`principal`、`tenant_id`、租户专属沙箱路径），全部通过 LangGraph 官方标准的 `RunnableConfig["configurable"]` 字典穿透，原生透明；
3. **组合根单向构建（One-Way Composition Root）**：在 `get_agent(config)` 入口处，根据配置一次性将模型、工具、沙箱组装完毕，编译成标准 `Pregel` 实例后直接交由官方运行时调度。

---

### 3. Tools、MCP、Skills、沙箱是如何层层封装进 LangGraph 的？

在大模型与底层系统之间，平台建立了**“全量归一化为 LangChain BaseTool”**的清晰流转链路：

```
                              大模型推理输出 (LLM Response)
                                            │
                                触发 Tool Call: {"name": "...", "args": {...}}
                                            │
                                            ▼
                             LangGraph 原生工具执行节点 (ToolNode)
                                            │
                                    tool.ainvoke(args)
                                            │
         ┌──────────────────┬───────────────┴───────────────┬──────────────────┐
         │                  │                               │                  │
         ▼                  ▼                               ▼                  ▼
  [本地原生业务工具]    [MCP 协议转译工具]            [Skills 技能工具]     [工作区沙箱工具]
    (BaseTool)      (MultiServerMCPClient)         (build_skill_tools)   (FilesystemMiddleware)
         │                  │                               │                  │
   执行本地逻辑:      通过 HTTP 转发外部:               动态读取/更新技能:    执行 Docker/读写工作区:
   - ArXiv 论文检索  - mcp-github-enterprise        - list_skills         - read_file
   - GitHub 仓库查看 - 强校验 readOnlyHint==True    - upload_skill (ZIP)  - write_file
   - 绘图渲染工具    - 封杀外部写操作                - 固化 skills_hash    - execute (断网容器)
         │                  │                               │                  │
         └──────────────────┴───────────────┬───────────────┴──────────────────┘
                                            │
                                  返回标准 ToolMessage
                                            │
                                            ▼
                               回到 LangGraph 状态机下一轮推演
```

#### 封装装配的核心源码实证（以 DearFlowAgent 组合根为例）

在 `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py` 中，四种能力的注入被组织得井井有条：

```python
# 1. 沙箱后端与防篡改权限声明 (自研底层 + deepagents 抽象)
workspace = DearWorkspaceBackend(facts.principal.tenant_id, facts.principal.project_id, thread_id)
backend = build_backend(workspace)
PERMISSIONS = [
    # 严禁智能体通过代码执行或文件工具篡改自身技能代码
    FilesystemPermission(operations=["write"], paths=["/skills/**"], mode="deny"),
    # 严禁智能体覆写历史会话记录以篡改事实
    FilesystemPermission(operations=["write"], paths=["/conversation_history/**"], mode="deny"),
]

# 2. 外部 MCP 工具动态发现与只读守卫 (Anthropic 协议标准 -> LangChain BaseTool)
mcp_tools = await load_mcp_tools(config, facts.principal, requested_mcp, reserved_names=DEAR_TOOLS)

# 3. 动态 Skills 技能管理工具装配 (自主研发治理引擎 -> LangChain BaseTool)
skill_tools = build_skill_tools(workspace, model)

# 4. 全部工具汇聚，一次性交由原生 Agent 构造器组装
agent = create_deep_agent(
    model=model,
    tools=[
        request_information,
        artifact_tool,          # 产物原子发布工具
        *research_tools,        # 基础检索工具
        *chart_tools,           # 图表生成工具
        *mcp_tools,             # 外部 MCP 协议工具
        *skill_tools,           # 动态技能治理工具
    ],
    backend=backend,            # 挂载工作区物理沙箱
    permissions=PERMISSIONS,    # 注入沙箱防篡改白名单/黑名单
    interrupt_on=interrupts_for_access_policy(...), # 接入 LangGraph 原生 HITL 人机中断
)
```

看到没有？
**对大模型而言**，所有能力全都伪装成了标准的 JSON Schema 工具定义；
**对 LangGraph 而言**，它执行的全部都是标准的 LangChain `BaseTool` 实例；
**但在底层物理世界**，每一次 `tool.ainvoke()` 都经过了我们自研沙箱的路径隔离、断网执行、权限拦截与 CSP 消杀！这就叫外表极其标准，内里固若金汤！

---

## 二、对立视角：简易原型 vs 生产架构（Naive vs Production）

| 维度 | 简易原型方案 (Naive) | 本平台生产级架构 (Production Architecture) | 选型与演进考量 |
| :--- | :--- | :--- | :--- |
| **MCP 工具集成** | 在前端或 Prompt 里直接传 MCP Server 的 URL 和 Auth Token，由模型拼装调用。 | 凭证完全由服务端私有环境变量托管，通过 `resolve_resource_binding` 动态解析，模型无感知。 | 杜绝由于 Prompt Injection 或模型幻觉将企业内部 MCP 服务的访问密钥吐给外部。 |
| **外部工具安全约束** | 第三方 MCP 工具全盘接受，任何工具均可执行删除和写入操作。 | 严格校验 `readOnlyHint is True`；若非只读工具，强制阻断并要求接入专有的 HITL 审批策略。 | 杜绝恶意或不受信任的第三方 MCP 服务直接对企业数据库或文件系统造成破坏。 |
| **技能扩展机制** | 技能就是写死在代码里的函数，新增一个技能必须重启 Python 服务。 | 支持动态 ZIP 包上传与解压（`upload_skill`），支持启用/禁用热切换与版本快照固化。 | 支持领域专家、最终用户根据业务需求自定义专属 Agent 技能，无需平台发版。 |
| **执行沙箱防御** | Agent 拥有当前工作空间的全部写权限，模型可能写代码篡改自身技能代码形成死循环。 | 沙箱强行将 `/skills/**`、`/conversation_history/**` 标记为只读（`mode="deny"`）。 | 封死 Agent 的自我篡改（Self-Tampering）路径，保证代码执行沙箱的绝对稳定性。 |

---

## 三、源码精准坐标映射（Code Pointer Map）

### 1. MCP 协议集成与客户端适配
- [services/dearflow_agent/tools/mcp.py](../../../apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/mcp.py)：
  - `load_mcp_tools()`：加载并适配当前会话绑定的 MCP 工具，执行 `readOnlyHint` 安全断言与名称冲突校验。
  - `MultiServerMCPClient`：LangChain MCP 协议客户端包装器。

### 2. Skills 技能系统与生命周期治理
- [services/dearflow_agent/tools/skills.py](../../../apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/skills.py)：
  - `build_skill_tools()`：构建技能生命周期工具集（`list_skills`, `upload_skill`, `update_skill`, `set_skill_enabled`, `delete_skill`）。
- [services/dearflow_agent/skill_governance.py](../../../apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py)：
  - `SkillStorage`：技能包存储引擎，处理 ZIP 解析、修订版本（`expected_revision`）控制与哈希计算。
- [services/dearflow_agent/skill_catalog.py](../../../apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_catalog.py)：
  - `public_catalog()`：读取随代码分发的内置公共技能目录。

### 3. 沙箱权限与工作区后端
- [services/dearflow_agent/agent.py](../../../apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py)：
  - `PERMISSIONS`：声明 `FilesystemPermission` 规则，禁止对 `/skills/**` 写入。
- [services/dearflow_agent/workspace/backend.py](../../../apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py)：
  - `DearWorkspaceBackend` 与 `skills_hash()`：固化当前技能树的状态快照指纹。

---

## 四、真实数据结构与报文（Real Payloads & DB Schemas）

### 1. 服务端 MCP 预置连接配置（环境变量格式）
连接参数完全保留在服务端，对外通过 `resource_id` 隐式绑定：

```json
{
  "mcp-github-enterprise": {
    "transport": "streamable_http",
    "url": "https://mcp.internal.company.com/v1",
    "headers": {
      "Authorization": "Bearer mcp-internal-token-secret-xxxx"
    },
    "allowed_tools": ["mcp_github_search_repos", "mcp_github_read_issue"]
  }
}
```

### 2. 上传私有技能包的入参报文
技能包以标准 ZIP 格式提交，必须包含 `SKILL.md` 元数据入口：

```json
{
  "file_path": "/workspace/outputs/custom_data_analyzer.zip"
}
```

---

## 五、端到端函数级调用时序（Function-Level Trace）

从会话初始化动态装配 MCP 工具与 Skills 技能的完整时序：

```mermaid
sequenceDiagram
    autonumber
    participant Pregel as LangGraph 引擎
    participant MCPModule as tools/mcp.py
    participant MCPClient as MultiServerMCPClient
    participant SkillStorage as skill_governance.py
    participant Backend as DearWorkspaceBackend
    participant Sandbox as FilesystemMiddleware

    Note over Pregel,MCPClient: 阶段一：MCP 工具动态发现与安全校验
    Pregel->>MCPModule: load_mcp_tools(config, principal, requested, reserved)
    MCPModule->>MCPModule: 从 Thread Metadata 读取 runtime_resource_bindings
    MCPModule->>MCPClient: 初始化并连接 MultiServerMCPClient
    MCPClient-->>MCPModule: 返回可用工具列表 [tool1, tool2]
    MCPModule->>MCPModule: 检查名称是否与系统保留词冲突
    MCPModule->>MCPModule: 强校验 tool.metadata.readOnlyHint == True
    alt 存在写操作工具
        MCPModule-->>Pregel: 抛出 RuntimeResolutionError("runtime.mcp.read_only_required")
    else 全部满足只读安全约束
        MCPModule-->>Pregel: 返回合法的 [MCPToolInstance, ...]
    end

    Note over Pregel,Sandbox: 阶段二：Skills 挂载与沙箱权限设防
    Pregel->>SkillStorage: 读取公共技能 + 租户私有可用技能
    SkillStorage-->>Pregel: 返回启用的技能包列表
    Pregel->>Backend: 计算当前技能快照指纹 skills_hash()
    Backend-->>Pregel: 返回固定 Hash 绑定在当前 Checkpoint

    Pregel->>Sandbox: 挂载 FilesystemMiddleware(PERMISSIONS)
    Note over Sandbox: 永久设防：对 /skills/** 和 /conversation_history/** 设置 mode="deny"
```

---

## 六、核心实现高保真伪代码（High-Fidelity Pseudocode）

### 1. MCP 工具只读守卫与装配（load_mcp_tools）
```python
# 对应 apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/mcp.py

async def load_mcp_tools(config, principal, requested, reserved):
    # 1. 过滤需要挂载的 MCP 工具名称 (前缀以 mcp_ 开头)
    names = {name for name in requested if name.startswith("mcp_")}
    if not names:
        return []

    # 2. 从线程元数据中提取绑定的 MCP 资源凭据
    binding = resolve_resource_binding(config, principal, "mcp")
    connections = json.loads(os.environ.get("RUNTIME_MCP_CONNECTIONS_JSON", "{}"))
    connection = dict(connections[binding.resource_id])

    # 严格校验传输协议，只允许 streamable_http
    if binding.provider != "mcp_http" or connection.get("transport") != "streamable_http":
        raise RuntimeResolutionError("runtime.mcp.recovery_failed")

    # 3. 初始化 MCP 客户端获取工具定义
    client = MultiServerMCPClient({"bound": connection}, tool_name_prefix=False)
    tools = await client.get_tools()
    actual = [t.name for t in tools]

    # 4. 杜绝重名攻击与系统保留字污染
    if set(actual) & set(reserved):
        raise RuntimeResolutionError("runtime.tool.name_conflict")

    # 5. 核心安全红线：当前阶段必须严格要求 readOnlyHint 为 True！
    # 任何试图偷偷加入写操作、删库操作的第三方 MCP 工具在此处被强行阻断
    for tool in tools:
        if tool.name in names:
            is_read_only = (tool.metadata or {}).get("readOnlyHint") is True
            if not is_read_only:
                raise RuntimeResolutionError("runtime.mcp.read_only_required")

    return [t for t in tools if t.name in names]
```

### 2. 沙箱权限防御配置（FilesystemPermission）
```python
# 对应 apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py

PERMISSIONS = [
    # 严禁智能体通过代码执行或文件工具篡改其自身的技能代码与提示词
    FilesystemPermission(operations=["write"], paths=["/skills/**"], mode="deny"),
    # 严禁智能体覆写历史会话记录以篡改执行事实
    FilesystemPermission(
        operations=["write"],
        paths=["/conversation_history/**", "/large_tool_results/**"],
        mode="deny"
    ),
]
```

---

## 七、假想断电与极限场景推演（Thought Experiments）

### 场景一：第三方 MCP 服务提供商私自修改工具增加了删除功能
- **推演过程**：企业接入了外部第三方的 GitHub MCP 服务，某天服务方在更新工具元数据时，将 `mcp_github_delete_repo` 工具加入了服务清单，且其 `readOnlyHint` 未被标为 `true`。
- **系统表现**：`runtime-service` 在执行 `load_mcp_tools` 握手校验时，检测到该工具的 `readOnlyHint is not True`，立即触发熔断抛出 `RuntimeResolutionError("runtime.mcp.read_only_required")`，执行被立即阻断，绝不允许不受控的删除类工具被装载入 Agent 的工具执行树中。

### 场景二：智能体在推理循环中试图修改 `/skills/search.py`
- **推演过程**：智能体执行某个 Python 脚本时遇到报错，模型产生幻觉，决定写一个 Python 脚本直接覆写 `/skills/find-skills/run.py` 以“修复自身的 Bug”。
- **系统表现**：执行写操作时触发底座的 `FilesystemMiddleware`，命中内置规则 `FilesystemPermission(operations=["write"], paths=["/skills/**"], mode="deny")`，底层工作空间直接拒绝写入并返回 `PermissionDeniedError: write access to /skills/** is denied`。智能体的自我篡改企图被沙箱当场粉碎。

### 场景三：技能上传并发版本覆盖（乐观锁竞争）
- **推演过程**：两名管理员同时尝试更新同一个私有技能 `data_extractor`，分别基于版本 `rev_001` 提交了不同的 ZIP 包。
- **系统表现**：`SkillStorage().update` 要求调用者必须传入 `expected_revision`。第一个管理员的更新成功落地，技能版本跃迁为 `rev_002`；第二个管理员的请求到达时，发现数据库中当前的修订版本已经是 `rev_002`，与其预期的 `rev_001` 不符，更新被立即拒绝并提示版本冲突，防止了代码覆盖事故。

---

## 八、架构不变量清单（Architectural Invariants）

1. **MCP 凭据私密性不变量**：MCP 连接串、密钥与认证 Header 属于服务端专属资源，绝对禁止注入到 LLM 上下文、Prompt 或工具参数中。
2. **MCP 只读安全硬约束**：当前运行时装载的外部 MCP 工具，其元数据必须显式声明 `readOnlyHint=True`，严禁未经审批挂载外部写操作工具。
3. **沙箱自我保护不变量**：`/skills/**` 目录必须对智能体执行进程强行置为只读（`mode="deny"`），绝对禁止智能体在推理运行期间动态篡改自身的技能实现代码。
4. **技能快照执行确定性原则**：单次 Run 一旦启动，必须锁定当前周期的 `skills_hash` 快照，后续任何外部动态上传、更新或删除，绝对不得干扰正在执行中的历史图状态。
