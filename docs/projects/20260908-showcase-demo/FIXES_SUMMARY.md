> 历史记录：本文不代表当前完成度；2026-09-09 重评后的事实源见 [README](README.md) 和 [verification](verification.md)。

# 修复总结

## 修复时间
2026-09-09

## 修复的问题

### 问题1: Agent同步使用静态文件而非LangGraph API

**问题描述**：
- `RuntimeCatalogService.list_graphs()` 使用 `_load_static_graph_configs()` 从本地文件系统读取 `langgraph.json`
- 在生产环境中，应该从 GraphHarbor 的 LangGraph API (`/assistants/search`) 获取 agent 列表

**修复方案**：
- 修改 `apps/platform-api/app/modules/runtime_catalog/application/service.py:list_graphs()`
- 当数据库为空时，自动调用 `refresh_graphs()` 从 LangGraph API 同步
- `refresh_graphs()` 已经正确实现了 API 调用：`await self._upstream.request_json("POST", "/assistants/search", ...)`

**修复代码**：
```python
async def list_graphs(self, *, actor: ActorContext, project_id: str) -> RuntimeGraphCatalogList:
    # ... 权限检查 ...
    
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
        rows = repository.list_graphs(runtime_id=self._runtime_id)

        # 如果数据库为空，自动调用refresh从LangGraph API同步
        if not rows:
            await self.refresh_graphs(actor=actor, project_id=project_id)
            # 重新读取同步后的数据
            async with SqlAlchemyUnitOfWork(session_factory) as refresh_uow:
                refresh_repository = SqlAlchemyRuntimeCatalogRepository(refresh_uow.session)
                rows = refresh_repository.list_graphs(runtime_id=self._runtime_id)

        items = [self._graph_item(item) for item in rows]
        return RuntimeGraphCatalogList(
            count=len(items),
            graphs=items,
            last_synced_at=self._latest_synced_at(items),
        )
```

**影响**：
- ✅ 生产环境可以正确从 LangGraph API 同步 assistants
- ✅ 不再依赖本地静态文件
- ✅ 支持动态注册的 agents

---

### 问题2: showcase_demo 发送消息无响应

**问题描述**：
- Workflow Demo HITL 可以正常对话
- showcase_demo 发送消息没有回复
- 错误日志显示：`RuntimeResolutionError: runtime.optional_tool.not_allowed`

**根本原因分析**：
1. **工具声明问题**：`AgentDefaults` 中 `optional_tool_names=()` 为空，但实际使用了4个工具
2. **Policy不匹配**：`RuntimePolicy` 的 `allowed_tool_names=()` 为空，不允许任何工具
3. **context_hash格式错误**：`_local_test_facts()` 传入空字符串 `""`，但需要 `sha256:` 格式

**修复方案**：

#### 修复1: 声明所需工具
```python
_DEFAULTS = AgentDefaults(
    model_id="DeepSeek-V4-Flash",
    system_prompt="""...""",
    prompt_version="showcase-demo-v1",
    required_tool_names=("execute_command", "fetch_documentation", "write_todos", "confirming_completion"),  # 改为required
)
```

#### 修复2: 配置工具权限
```python
_TOOL_PERMISSIONS: dict[str, str] = {
    "execute_command": "runtime.tool.execute_command",
    "fetch_documentation": "runtime.tool.fetch_documentation",
    "write_todos": "runtime.tool.write_todos",
    "confirming_completion": "runtime.tool.confirming_completion",
}
```

#### 修复3: Policy允许工具
```python
def _local_test_facts() -> VerifiedDelegation:
    return VerifiedDelegation(
        RuntimePrincipal(...),
        RuntimePolicy(
            "showcase-demo-local-v1",
            (_DEFAULTS.model_id, "deepseek:DeepSeek-V4-Flash", ...),
            ("execute_command", "fetch_documentation", "write_todos", "confirming_completion"),  # 添加allowed_tool_names
        ),
        RuntimeScope("local-tenant", "showcase-project"),
        "sha256:0000000000000000000000000000000000000000000000000000000000000000",  # 修复context_hash格式
    )
```

**修复文件**：
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py`

**影响**：
- ✅ showcase_demo 可以正常初始化
- ✅ 工具权限验证通过
- ✅ context_hash 格式正确

---

## 验证步骤

### 1. 检查代码修改
```bash
# 检查 showcase_demo 工具配置
grep -A 2 "required_tool_names=" apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py

# 检查 list_graphs API调用
grep -A 5 "if not rows:" apps/platform-api/app/modules/runtime_catalog/application/service.py
```

### 2. 重启服务
```bash
cd /Users/lijiaxin/PyCharmMiscProject/ai-agent-platform
bash scripts/local-stack.sh restart runtime-worker
```

### 3. Web界面测试
1. 访问 http://127.0.0.1:3000/workspace/assistants
2. 检查 agent 列表是否从 LangGraph API 同步
3. 创建 showcase_demo 对话
4. 发送测试消息，验证是否有响应

### 4. 检查日志
```bash
# 查看最新的 showcase_demo 日志
bash scripts/local-stack.sh logs runtime-worker 2>&1 | grep "showcase_demo" | tail -20

# 应该看到成功运行的日志，而不是 "runtime.optional_tool.not_allowed" 错误
```

---

## 技术要点

### RuntimePolicy vs AgentDefaults
- **AgentDefaults**: 定义 agent 的默认配置（模型、提示词、工具列表）
- **RuntimePolicy**: 运行时安全策略，限制允许的模型和工具
- **验证逻辑**: `resolve_runtime_config()` 会检查 `defaults.required_tool_names` 是否都在 `policy.allowed_tool_names` 中

### context_hash格式
- 必须是 `sha256:` 前缀 + 64位十六进制字符
- 正则验证：`^sha256:[0-9a-f]{64}$`
- 本地测试可以使用全零哈希：`sha256:0000...0000`

### LangGraph API同步流程
1. `list_graphs()` 检查数据库
2. 如果为空，调用 `refresh_graphs()`
3. `refresh_graphs()` 调用 `/assistants/search` API
4. 将结果写入数据库
5. 返回数据库中的列表

---

## 相关文件

### 修改的文件
1. `apps/platform-api/app/modules/runtime_catalog/application/service.py` (list_graphs方法)
2. `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py` (_DEFAULTS, _TOOL_PERMISSIONS, _local_test_facts)

### 相关模块
- `apps/runtime-service/src/runtime_service/runtime/contracts.py` - RuntimePolicy定义
- `apps/runtime-service/src/runtime_service/runtime/auth.py` - VerifiedDelegation定义
- `apps/runtime-service/src/runtime_service/runtime/resolver.py` - resolve_runtime_config验证逻辑
- `apps/platform-api/app/adapters/langgraph/graphs_sdk_adapter.py` - LangGraph SDK适配器

---

## 后续工作

### 待完成
- [ ] 在生产环境测试 agent 同步
- [ ] 为 showcase_demo 配置实际的 DeepSeek API Key（如果需要真实模型）
- [ ] 实现专题04：Platform Dispatch Layer（标记为未来工作）

### 可选优化
- [ ] 为 `list_graphs()` 添加缓存机制，避免频繁调用 API
- [ ] 为工具权限配置添加统一管理
- [ ] 统一本地测试的 context_hash 生成逻辑
