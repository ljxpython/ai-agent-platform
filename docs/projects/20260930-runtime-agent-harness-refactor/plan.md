# Runtime Agent 组合根脚手架重构与 DX 体验治理 - 整体方案

## 背景
在对 `runtime-service` 现有代码库（特别是旗舰智能体 `dearflow_agent`、`workflow_demo`、`reference_agent`）进行深度架构审视时，我们发现底层执行层虽然做到了极致的安全防护与微服务自治，但在**开发者体验（Developer Experience, DX）与模块解耦**上积累了显著的架构技术债：

1. **组合根样板代码超标严重**：在 [`dearflow_agent/agent.py`](../../../apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py) 中，前 150 行几乎全在做 `facts` 解包、`context_hash` 比对、`workspace` 目录解析与模型解密。每个新 Agent 的开发都需要重复复制粘贴这一长串复杂的安全胶水代码。
2. **测试夹具构造摩擦巨大**：新开发者在编写单测时，被迫手动拼装一个包含 `runtime_principal`, `runtime_policy`, `runtime_scope`, `runtime_context_hash` 的庞大嵌套字典，严重阻碍测试左移。
3. **元数据探测与执行流杂糅**：为了支持控制面目录刷新（Catalog Probe）与正式执行（Run Execution），函数内充斥着 `None if workspace is None else ...` 等防御性分支，代码可读性极差。

## 目标
1. **安全与业务关注点彻底分离**：将所有 Delegation JWT 验签、`context_hash` 校验、租户工作空间装配、黑名单工具物理剔除沉淀到框架级基础设施。
2. **Agent 业务代码量骤降 60%~70%**：单 Agent 组合根从 400+ 行压缩到 100 行以内纯粹的图编排与 Prompt 定义。
3. **极简测试体验**：提供标准的 `create_test_config()` 夹具工厂，一行代码即可生成合法的单测配置。
4. **不变量零破损**：现有跨服务契约（Delegation Claims、Context Hash、工具只减不增原则）100% 保持严格兼容。

---

## 方案设计

### 1. 整体架构分层（Harness 模式）

```
[上层网关 Platform-API]
        │ (透传 Delegation JWT & Configurable)
        ▼
[RuntimeAgentHarness 框架层] ◄── 统一托管验签、防伪指纹比对、多租户沙箱初始化、黑名单物理剥离
        │ (组装出纯净的 AgentBuildContext)
        ▼
[业务 Agent 开发者代码]     ◄── 只面向模型、工具、沙箱、Prompt 构筑 LangGraph 状态机！
```

### 2. 核心领域契约：`AgentBuildContext`
框架为 Agent 构建过程提供高内聚上下文容器：

```python
@dataclass(frozen=True)
class AgentBuildContext:
    model: BaseChatModel                 # 经安全策略授权、解密并配置完成的真实/测试模型
    tools: tuple[BaseTool, ...]          # 已依据 tool_overrides 物理剥离黑名单后的安全工具集合
    workspace: DearWorkspaceBackend      # 已完成租户与线程绑定的独立文件沙箱
    principal: RuntimePrincipal          # 经过验签的当前调用方上下文主体
    mode: ExecutionMode                  # 当前执行模式（flash / standard / pro / ultra）
    is_probe: bool                       # 是否仅为元数据探测请求
```

### 3. 核心装饰器与组合抽象：`@runtime_agent`

```python
# 框架层 apps/runtime-service/src/runtime_service/framework/harness.py

def runtime_agent(
    *,
    name: str,
    defaults: AgentDefaults,
    approvals: Mapping[str, Any] | None = None,
    permissions: Sequence[FilesystemPermission] | None = None,
):
    """统一收敛 PEP 安全拦截、上下文解包与探针模式分支的高阶包装器"""
    def decorator(builder_func: Callable[[AgentBuildContext], Pregel]):
        async def entrypoint(config: RunnableConfig) -> Pregel:
            # 1. 拦截不可信 configurable 注入
            reject_untrusted_configurable(config.get("configurable") or {})

            # 2. 提取并校验委托事实
            facts = extract_and_verify_facts(config, assistant_id=name)

            # 3. 初始化或 Mock 隔离工作空间
            workspace = resolve_scoped_workspace(facts, config)

            # 4. 解析与物理筛选工具清单（应用 tool_overrides 黑名单只减不增）
            safe_tools = filter_authorized_tools(defaults, facts)

            # 5. 依赖注入测试模型或在线解密拉取生产模型
            model = resolve_target_model(config, facts, defaults)

            # 6. 构造纯净构建上下文并交由业务函数构图
            ctx = AgentBuildContext(
                model=model, tools=safe_tools, workspace=workspace,
                principal=facts.principal, mode=resolve_mode(config),
                is_probe=facts is None or facts.scope.operation != "run-create"
            )
            return builder_func(ctx)
        return entrypoint
    return decorator
```

### 4. 测试支持工具集：`testing.py`
为开发者提供开箱即用的测试构造器：

```python
# 框架层 apps/runtime-service/src/runtime_service/framework/testing.py

def create_test_config(
    *,
    assistant_id: str = "dearflow_agent",
    thread_id: str = "test-thread-01",
    model: BaseChatModel | None = None,
    tool_overrides: Mapping[str, bool] | None = None,
) -> RunnableConfig:
    """生成具备合法数学签名的单测配置字典，支持直接注入 Mock 模型"""
    ...
```

---

## 关键改动点

#### 1. 新增框架核心模块
- **文件：** `apps/runtime-service/src/runtime_service/framework/harness.py`
- **改动：** 实现 `AgentBuildContext` 与 `runtime_agent` 核心抽象。
- **理由：** 消除组合根中高达 150 行的样板代码，杜绝各 Agent 重复编写安全校验。

#### 2. 重构 `dearflow_agent/agent.py`
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`
- **改动：** 切换至 `@runtime_agent` 装饰器，删除繁琐的手动解包与 `None` 判定。
- **理由：** 降本增效，提升代码可读性与可维护性。

#### 3. 提炼测试脚手架
- **文件：** `apps/runtime-service/src/runtime_service/framework/testing.py`
- **改动：** 提供 `create_test_config()` 与通用的 `FakeModel` 辅助函数。
- **理由：** 降低单测门槛，消除测试编写心智摩擦。

---

## 风险和依赖
- **风险 1：** 抽象层过度封装可能导致特定 Agent 的个性化中间件装配困难。
  - **应对：** `AgentBuildContext` 保留扩展字段，允许 Agent 自由挂载子智能体与私有中间件链条。
- **风险 2：** 修改入口可能破坏既有端到端测试（如 `test_dearflow_skills.py`）。
  - **应对：** 严格对齐当前的 `verified_delegation_from_user` 行为，以既有 24 组测试作为回归基线。

---

## 实施计划
1. **Phase 1（基础建设）**：开发 `framework/harness.py` 与 `framework/testing.py`，编写框架自身的高覆盖率单测。
2. **Phase 2（参考智能体迁移）**：率先将 `reference_agent` 与 `workflow_demo` 迁移至新 Harness，验证设计通用性。
3. **Phase 3（核心旗舰迁移与全量回归）**：迁移 `dearflow_agent`，跑通包括沙箱、记忆、技能在内的全部既有测试套件。
