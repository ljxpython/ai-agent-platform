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
- 依赖 [04-platform-api/04-catalog-management.md](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/docs/architecture/04-platform-api/04-catalog-management.md)：理解平台侧资产目录如何通过 Refresh 工作流同步图与工具元数据。
- 依赖 [03-hitl-and-interrupts.md](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/docs/architecture/05-runtime-service/03-hitl-and-interrupts.md)：掌握任何对技能包产生写操作（`upload_skill`, `update_skill` 等）的工具调用，均受访问策略与 HITL 审批的拦截约束。

### 2. 本章核心流转
- **MCP 动态绑定解析**：解析 Thread 元数据中的 `runtime_resource_bindings`，从服务端加载安全连接配置并初始化客户端。
- **技能包校验与乐观锁更新**：通过 `SkillStorage` 检验 ZIP 包体积与文件结构，利用 `expected_revision` 校验实现防并发覆盖。
- **沙箱权限拦截**：在工具实际执行前，`FilesystemPermission` 阻断一切向系统保护路径发起的越权写操作。

### 3. 认知输出（支撑后续模块）
- 为 [07-agents/01-dearflow-agent.md](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/docs/architecture/07-agents/01-dearflow-agent.md) 提供 38 类核心工具与 20+ 专业技能的运行底层支撑。

---

## 一、对立视角：简易原型 vs 生产架构（Naive vs Production）

| 维度 | 简易原型方案 (Naive) | 本平台生产级架构 (Production Architecture) | 选型与演进考量 |
| :--- | :--- | :--- | :--- |
| **MCP 工具集成** | 在前端或 Prompt 里直接传 MCP Server 的 URL 和 Auth Token，由模型拼装调用。 | 凭证完全由服务端私有环境变量托管，通过 `resolve_resource_binding` 动态解析，模型无感知。 | 杜绝由于 Prompt Injection 或模型幻觉将企业内部 MCP 服务的访问密钥吐给外部。 |
| **外部工具安全约束** | 第三方 MCP 工具全盘接受，任何工具均可执行删除和写入操作。 | 严格校验 `readOnlyHint is True`；若非只读工具，强制阻断并要求接入专有的 HITL 审批策略。 | 杜绝恶意或不受信任的第三方 MCP 服务直接对企业数据库或文件系统造成破坏。 |
| **技能扩展机制** | 技能就是写死在代码里的函数，新增一个技能必须重启 Python 服务。 | 支持动态 ZIP 包上传与解压（`upload_skill`），支持启用/禁用热切换与版本快照固化。 | 支持领域专家、最终用户根据业务需求自定义专属 Agent 技能，无需平台发版。 |
| **执行沙箱防御** | Agent 拥有当前工作空间的全部写权限，模型可能写代码篡改自身技能代码形成死循环。 | 沙箱强行将 `/skills/**`、`/conversation_history/**` 标记为只读（`mode="deny"`）。 | 封死 Agent 的自我篡改（Self-Tampering）路径，保证代码执行沙箱的绝对稳定性。 |

---

## 二、源码精准坐标映射（Code Pointer Map）

### 1. MCP 协议集成与客户端适配
- [services/dearflow_agent/tools/mcp.py](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/mcp.py)：
  - `load_mcp_tools()`：加载并适配当前会话绑定的 MCP 工具，执行 `readOnlyHint` 安全断言与名称冲突校验。
  - `MultiServerMCPClient`：LangChain MCP 协议客户端包装器。

### 2. Skills 技能系统与生命周期治理
- [services/dearflow_agent/tools/skills.py](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/skills.py)：
  - `build_skill_tools()`：构建技能生命周期工具集（`list_skills`, `upload_skill`, `update_skill`, `set_skill_enabled`, `delete_skill`）。
- [services/dearflow_agent/skill_governance.py](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py)：
  - `SkillStorage`：技能包存储引擎，处理 ZIP 解析、修订版本（`expected_revision`）控制与哈希计算。
- [services/dearflow_agent/skill_catalog.py](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_catalog.py)：
  - `public_catalog()`：读取随代码分发的内置公共技能目录。

### 3. 沙箱权限与工作区后端
- [services/dearflow_agent/agent.py](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py)：
  - `PERMISSIONS`：声明 `FilesystemPermission` 规则，禁止对 `/skills/**` 写入。
- [services/dearflow_agent/workspace/backend.py](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py)：
  - `DearWorkspaceBackend` 与 `skills_hash()`：固化当前技能树的状态快照指纹。

---

## 三、真实数据结构与报文（Real Payloads & DB Schemas）

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

## 四、端到端函数级调用时序（Function-Level Trace）

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

## 五、核心实现高保真伪代码（High-Fidelity Pseudocode）

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

## 六、假想断电与极限场景推演（Thought Experiments）

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

## 七、架构不变量清单（Architectural Invariants）

1. **MCP 凭据私密性不变量**：MCP 连接串、密钥与认证 Header 属于服务端专属资源，绝对禁止注入到 LLM 上下文、Prompt 或工具参数中。
2. **MCP 只读安全硬约束**：当前运行时装载的外部 MCP 工具，其元数据必须显式声明 `readOnlyHint=True`，严禁未经审批挂载外部写操作工具。
3. **沙箱自我保护不变量**：`/skills/**` 目录必须对智能体执行进程强行置为只读（`mode="deny"`），绝对禁止智能体在推理运行期间动态篡改自身的技能实现代码。
4. **技能快照执行确定性原则**：单次 Run 一旦启动，必须锁定当前周期的 `skills_hash` 快照，后续任何外部动态上传、更新或删除，绝对不得干扰正在执行中的历史图状态。
