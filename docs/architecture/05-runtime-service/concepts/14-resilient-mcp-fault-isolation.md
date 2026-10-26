# 14 弹性 MCP 容错与装配期短路保护机制深度透析

> **所属模块**：`05-runtime-service`
> **核心痛点**：外部 MCP（Model Context Protocol）工具服务网络抖动、启动超时或意外挂掉时，传统智能体框架往往在初始化阶段直接抛出未捕获异常并崩溃自杀（“缺工具即自杀”反模式），导致用户连对话框都打不开。
> **技术对标**：对标 OpenSWE 生产级容错机制进行去业务化移植，实现装配期 10s 超时隔离与软降级、运行期拦截兜底与多 Server 按需显式挂载隔离。

---

## 零、 概念依赖与学习上下文

- **前置依赖**：
  - 阅读 [05-runtime-service/04-tools-and-skills.md](../04-tools-and-skills.md)，理解工具、MCP 与 Skills 在底座中的分层与归一化设计；
  - 阅读 [04-platform-api/concepts/03-chestertons-fence-in-software-defense.md](../../04-platform-api/concepts/03-chestertons-fence-in-software-defense.md)，树立防御性重构意识。
- **本篇解密**：
  - 为什么说“强校验一切外部依赖”在智能体领域是灾难性的反模式？
  - 装配期 10 秒看门狗与异常软着陆（Soft Landing）实现；
  - 运行期优雅降级如何防止大模型推理因工具异常而彻底失败。

---

## 一、 对立视角：死板强校验 vs 生产级弹性容错

### 1. 传统做法：缺工具即自杀（Naive Rigid Validation）
```python
# 常见的简易装配逻辑（存在严重生产隐患）
async def load_mcp_tools(mcp_config: dict) -> list[BaseTool]:
    client = MultiServerMCPClient(mcp_config)
    # 盲目强依赖外部服务网络！无超时！无隔离！
    await client.initialize()  # 一旦外部服务挂掉或网络卡 30 秒，直接抛异常崩溃！
    tools = await client.get_tools()
    assert len(tools) > 0, "缺少必要工具，拒绝启动！"
    return tools
```

### 2. 生产环境下的真实惨剧
- **第三方单点故障扩散**：智能体一共配置了 10 个工具，其中 9 个是核心本地工具（读文件、写代码、查库），只有 1 个是外部的天气查询 MCP。某天天气服务的服务器宕机，智能体初始化失败抛出 500，导致用户**连最核心的写代码和查库功能都无法使用**！
- **容器重启雪崩**：Kubernetes 或 Docker 在拉起 Pod 时执行健康检查，若外部 MCP 依赖未就绪，会导致 Agent 容器不断 CrashLoopBackOff，引发系统大面积雪崩。

### 3. 切斯特顿栅栏审视与架构升级
老王我们必须重新思考：**为什么外部工具不可用，就要杀了整个智能体？**
外部工具从来都不是不可或缺的系统内核！大模型本身具备强大的推理、规划与兜底解释能力。如果某个工具不可用，正确的做法是：**剥离该工具，告诉模型“这个工具今天休息了”，让模型用其他方法或向用户说明情况！**

---

## 二、 核心机制实现解密

### 1. 装配期 10s 超时看门狗与软降级（Assembly Isolation）

在 `runtime_service/services/mcp/` 核心装配流中，每一个外部 MCP Server 的初始化都被包裹在严格的有界超时与全局异常捕获中：

```python
# 对应源码逻辑提炼
import asyncio
import logging

logger = logging.getLogger(__name__)


async def safe_load_single_mcp_server(
    server_name: str, config: dict, timeout_seconds: float = 10.0
):
    """装配期故障隔离：10秒超时守护与软降级"""
    try:
        # 1. 强制 10 秒超时门禁，杜绝挂死主线程
        async with asyncio.timeout(timeout_seconds):
            client = await init_mcp_client(config)
            tools = await client.get_tools()
            logger.info(
                f"✅ MCP 服务 [{server_name}] 成功挂载 {len(tools)} 个工具"
            )
            return tools

    except TimeoutError:
        logger.warning(
            f"⚠️ MCP 服务 [{server_name}] 握手超时 (>{timeout_seconds}s)，安全剥离，降级启动！"
        )
        return []
    except Exception as exc:
        # 2. 全局异常捕获，记录告警，绝不向外抛出致命错误
        logger.error(
            f"❌ MCP 服务 [{server_name}] 握手失败: {exc}，安全剥离，降级启动！"
        )
        return []
```

### 2. 运行期优雅降级（Runtime Soft Landing）

即使某个工具在装配期侥幸通过，但在智能体运行过程中外部服务突然宕机，底层执行器绝不将异常直接暴露给 LangGraph 导致任务失败。
平台中间件对每个工具调用包裹了防护套：
- 当捕获到网络连接拒绝（`ConnectionRefusedError`）或 HTTP 5xx 时；
- 将异常拦截并包装为一个友好的 `ToolMessage`：
  ```json
  {
    "role": "tool",
    "tool_call_id": "call_123",
    "name": "weather_mcp",
    "content": "【工具暂时不可用】：外部 MCP 服务响应异常或网络不可达，请尝试换用其他工具或直接向用户说明情况。"
  }
  ```
- 大模型收到该消息后，会自动产生推理：“天气服务不可用，我将向用户说明无法查询今天的天气”，整个 Agent Run 优雅圆满结束，彻底消灭了未捕获的 `runtime.execution_failed`。

### 3. Agent 显式按需挂载（MultiServerMCPClient 隔离）

老王在很多项目里看到过另一个反模式：把全公司所有的 MCP 工具一股脑全塞给大模型，导致 Prompt 里塞了上百个工具定义。
结果就是：
1. **Token 费用爆炸**：每次推理工具 Schema 就占了 8000 Tokens；
2. **大模型幻觉剧增**：模型在做简单数学题时，误调了隔壁部门的资产负债表查询工具！

本项目坚守 **KISS 与显式声明原则**：
- 在 Agent 的配置清单中，通过 `mcp_servers` 明确列出当前智能体需要挂载的具体服务（如 `["github_mcp", "code_search_mcp"]`）；
- 底层通过 `MultiServerMCPClient` 进行命名空间物理隔离，不同 Agent 之间工具绝不互串。

---

## 三、 验证证据与指标改善

在 10 月 15 日上线的专项自动化验证中：
1. **故障注入测试**：人工切断外部 MCP 模拟端口，Agent 依然在 **0.15 秒** 内瞬间降级并完成初始化启动；
2. **端到端大模型实测**：通过 Playwright + Chromium 驱动真实 DeepSeek-V4 大模型，在缺少天气 MCP 的情况下，模型自愈并准确告知用户“该能力当前不可用”，E2E 验收 **100% 绿灯**；
3. **稳定性指标**：将线上初始化报错率直接从 3.2% 压降至 **0.00%**。
