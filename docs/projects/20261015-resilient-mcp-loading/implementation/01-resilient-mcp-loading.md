# 弹性 MCP 工具装配与运行时解耦保护 - 实现记录

## 改动时间
2026-10-15

## 相关任务
- Task 1.1: MCP 服务连接与工具检索超时与故障物理隔离
- Task 1.2: 废除强一致性自杀检查，实现宽松工具匹配
- Task 2.1: 工具执行期异常内化与超时保护
- Task 3.1: 更新既有单测契约并新增容错测试套件

## 改动文件
- `apps/runtime-service/src/runtime_service/tools/mcp.py`
- `apps/runtime-service/tests/services/dearflow_agent/test_mcp_tools.py`

## 具体改动

### 1. 对标 OpenSWE 移植装配期物理故障隔离与超时保护
**位置：** `apps/runtime-service/src/runtime_service/tools/mcp.py`

**改动前：**
```python
tools = await client.get_tools(server_name=server_key)
actual = [tool.name for tool in tools]
if len(set(actual)) != len(actual) or set(actual) & set(reserved):
    raise RuntimeResolutionError("runtime.tool.name_conflict")
if names - set(actual):
    raise RuntimeResolutionError("runtime.mcp.required_unavailable")
```

**改动后：**
```python
try:
    tools = await asyncio.wait_for(
        client.get_tools(server_name=server_key),
        timeout=_DISCOVERY_TIMEOUT_SECONDS,
    )
except Exception as exc:
    logger.warning(
        "Failed to load MCP tools from server %s: %s",
        server_key,
        exc,
        exc_info=True,
    )
    return []

actual = [tool.name for tool in tools]
if len(set(actual)) != len(actual) or set(actual) & set(reserved):
    raise RuntimeResolutionError("runtime.tool.name_conflict")
missing = names - set(actual)
if missing:
    logger.warning(
        "Requested MCP tools missing from %s: %s",
        server_key,
        sorted(missing),
    )
selected = [tool for tool in tools if tool.name in names]
if not selected:
    return []
```

**理由：**
彻底杜绝外部 MCP Server 离线、超时、协议报错或部分工具缺失时，抛出致命异常导致 Agent 装配中断的反模式；平滑降级并记录警告日志。

### 2. 强化运行时异常捕获与内化
**位置：** `apps/runtime-service/src/runtime_service/tools/mcp.py:handle_error`

**改动后：**
```python
def handle_error(exc, *, name=item.name, native=native_handler):
    content = tool_error_content(exc, name)
    if content is not None:
        return content
    if callable(native):
        try:
            return native(exc)
        except Exception:
            pass
    if is_transport_error(exc):
        return tool_error_content(
            ToolException("mcp_transport_unavailable"), name
        )
    logger.warning(
        "Unhandled MCP tool execution error on %s: %s",
        name,
        exc,
        exc_info=True,
    )
    return tool_error_content(
        ToolException("mcp_transport_unavailable"), name
    )
```

**理由：**
将所有未捕获异常、网络断连、超时统统转化为模型可识别的 `ToolMessage(status="error")`，杜绝异常逃逸导致状态机崩溃（`runtime.execution_failed`）。

### 3. 测试套件扩充与断言契约演进
**位置：** `apps/runtime-service/tests/services/dearflow_agent/test_mcp_tools.py`

**新增断言与用例：**
- 验证部分工具缺失时正常返回可用子集；
- 验证全部请求工具缺失时平滑返回 `[]`，不自杀；
- 验证服务端被强杀/离线后，装配调用平滑返回 `[]`；
- 新增 `test_mcp_discovery_server_unreachable_and_timeout` 独立测试，验证指向未开放端口时平稳降级返回 `[]`。

## 验证
- [x] `test_real_mcp_binding_permissions_disconnect_and_close` 通过
- [x] `test_mcp_discovery_server_unreachable_and_timeout` 通过
- [x] 52 项 runtime/tool/governance 测试全绿
- [x] 116 项 knowledge/r4/reconnect 测试全绿
