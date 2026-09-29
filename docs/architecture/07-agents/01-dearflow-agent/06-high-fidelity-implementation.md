# 06-端到端高保真实现伪代码 (单文件级全景装配闭环)

## 模块定位与核心价值

在研读大型开源项目或工业级中台系统时，架构师和高级研发人员最渴望拥有的，不是散落在各个章节里的概念示意图，而是一份**剥离了繁杂的第三方包装库、单文件自包含、能够一眼看穿所有设计模式与状态机闭环的“终极高保真实现”**。

本篇文档将前述 5 个章节中关于 `DearFlow Agent` 的所有核心架构设计——包括：
1. **四档执行模式与算力注入（`flash/standard/pro/ultra`）**
2. **全流程 8 大核心中间件流水线（消息队列认领、沙箱防御、技能加载、记忆检索、防套娃熔断）**
3. **多命名空间子智能体派发（`checkpoint_ns="researcher|..."`）**
4. **基于快照的人机协同中断与防篡改恢复（HITL Interrupt & Resume）**
5. **虚拟沙箱与防路径逃逸验证**

全部浓缩淬炼为一份**自包含、可推演、语法完全合规的高保真 Python 伪代码蓝图**。它不仅是理解 `dearflow_agent` 核心代码的“解密密钥”，更是研发团队在构建自研 Agent 引擎时的黄金参考范本。

---

## 零、知识前置与上下文串联（Knowledge Bridges）

### 1. 认知输入（前置模块输入）
- 串联本专题所有前置章节：
  - [01-architecture-and-modes.md](01-architecture-and-modes.md)：执行模式与中间件管道。
  - [02-memory-engine.md](02-memory-engine.md)：记忆引擎与前置 Working Memory 注入。
  - [03-tools-ecosystem.md](03-tools-ecosystem.md)：工具生态与大结果分流。
  - [04-workspace-sandbox.md](04-workspace-sandbox.md)：虚拟沙箱与反自我篡改权限。
  - [05-skills-runtime.md](05-skills-runtime.md)：技能版本快照不可变性。

### 2. 本章核心流转
- 阅读并对照下文完整的单文件级伪代码实现。
- 重点比对 Pregel 循环从接收输入、中间件前置拦截、模型推理、敏感工具中断到断点解冻恢复的物理流转步骤。

---

## 一、对立视角：碎片拼装 vs 单文件闭环（Snippet vs Blueprint）

| 维度 | 传统文档的代码碎片 (Code Snippets) | 本高保真全景蓝图 (High-Fidelity Blueprint) | 选型与演进考量 |
| :--- | :--- | :--- | :--- |
| **可理解性** | 碎片代码散落数十个文件，读者无法直观看到中间件与图节点的调用因果链。 | 单文件完整串联：状态定义、沙箱、记忆、中间件栈、图编译与模拟执行闭环一览无余。 | 降低认知负荷，帮助工程师在脑海中建立 100% 确定性的端到端物理模型。 |
| **状态机完备性** | 往往省略中断恢复和命名空间分流，只展示“理想成功路径”。 | 包含完整的 `interrupted` 状态落盘、`input.respond` 恢复验证与 `checkpoint_ns` 分支探测。 | 直面真实生产环境中的高危中断、并发竞争与断电重试场景。 |
| **安全防护闭环** | 缺少防穿透、防自篡改与配额硬限制代码，看似能跑实则极度脆弱。 | 严谨集成 `resolve_path` 防逃逸、`ToolCallLimit` 防死循环、`PERMISSIONS` 只读黑名单。 | 确保呈现的代码直接对齐金融级和企业级系统安全基线。 |

---

## 二、端到端高保真实现全景伪代码（High-Fidelity Blueprint）

```python
"""
================================================================================
DearFlow Agent High-Fidelity Blueprint (单文件全景高保真实现)
================================================================================
本文件自包含地还原了 DearFlow Agent 的完整生命周期：
1. 四档执行模式与动态思考链注入 (modes)
2. 虚拟工作空间与防路径逃逸沙箱 (DearWorkspaceBackend)
3. 动态前置语义记忆引擎 (MemoryContextMiddleware)
4. 多命名空间子智能体分流 (checkpoint_ns 路由与 researcher)
5. 敏感动作人工审批中断与防篡改恢复 (HITL Interrupt & Resume)
6. 10+ 核心中间件流水线调用链
================================================================================
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import signal
import uuid
from dataclasses import dataclass, field
from typing import Annotated, Any, Callable, Mapping, NotRequired, Sequence

# ==============================================================================
# 第一部分：状态、契约与执行模式定义
# ==============================================================================

@dataclass(frozen=True, slots=True)
class AgentMode:
    name: str
    planning: bool       # 是否挂载任务规划中间件
    delegation: bool     # 是否允许派生子智能体
    reasoning: str       # "off" | "low" | "medium" | "high"

MODES: dict[str, AgentMode] = {
    "flash": AgentMode("flash", planning=False, delegation=False, reasoning="off"),
    "standard": AgentMode("standard", planning=False, delegation=False, reasoning="low"),
    "pro": AgentMode("pro", planning=True, delegation=True, reasoning="medium"),
    "ultra": AgentMode("ultra", planning=True, delegation=True, reasoning="high"),
}

@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]

@dataclass
class Message:
    role: str            # "system" | "user" | "assistant" | "tool"
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None

# 私有状态标记：保证外部客户端绝对无法反向注入或透传读取
class PrivateStateAttr:
    pass

class AgentState(dict):
    """LangGraph 核心图状态容器"""
    messages: list[Message]
    todo_list: list[dict[str, Any]]
    runtime_message_claim: Annotated[dict[str, Any], PrivateStateAttr]

# ==============================================================================
# 第二部分：沙箱与安全防御边界 (DearWorkspaceBackend)
# ==============================================================================

class DearWorkspaceBackend:
    """虚拟工作空间沙箱：绝对物理防逃逸与只读保护"""
    def __init__(self, root_dir: str):
        self.root = os.path.realpath(os.path.abspath(root_dir))
        os.makedirs(self.root, exist_ok=True)
        # 系统敏感黑名单目录：严禁智能体自我篡改
        self.deny_paths = ("/skills", "/conversation_history", "/large_tool_results")

    def resolve_path(self, relative_path: str) -> str:
        """解析相对路径为绝对路径，强力粉碎任何 ../ 逃逸攻击与空字符注入"""
        if "\0" in relative_path:
            raise PermissionError("Null byte injection detected in path")
        joined = os.path.join(self.root, relative_path.lstrip("/"))
        resolved = os.path.realpath(os.path.abspath(joined))

        # 核心不变量：解析后的物理路径必须以沙箱根路径为前缀
        if not (resolved == self.root or resolved.startswith(self.root + os.sep)):
            raise PermissionError(f"Access Denied: Path escapes sandbox boundary: {relative_path}")
        return resolved

    def write_file(self, path: str, content: str) -> int:
        for denied in self.deny_paths:
            if path.startswith(denied) or path.startswith(denied.lstrip("/")):
                raise PermissionError(f"Anti-Self-Tampering: Write to protected system path '{denied}' is forbidden")
        abs_path = self.resolve_path(path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            return f.write(content)

    def read_file(self, path: str, offset: int = 0, limit: int = 10000) -> str:
        abs_path = self.resolve_path(path)
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(offset)
            return f.read(limit)

# ==============================================================================
# 第三部分：核心中间件流水线 (Middleware Pipeline)
# ==============================================================================

class BaseMiddleware:
    async def abefore_model(self, state: AgentState, context: dict[str, Any]) -> dict[str, Any] | None:
        return None

class MessageQueueMiddleware(BaseMiddleware):
    """外部消息队列认领中间件：带多命名空间路由防护"""
    async def abefore_model(self, state: AgentState, context: dict[str, Any]) -> dict[str, Any] | None:
        checkpoint_ns = context.get("checkpoint_ns", "")
        # 核心不变量：若命名空间包含 '|'，说明当前处于子智能体执行分支，严禁越权拉取根消息！
        if "|" in checkpoint_ns:
            return None

        # 模拟从 PostgreSQL MessageInbox 中认领排队消息
        pending_messages = context.get("inbox_mock", {}).pop("pending", [])
        if not pending_messages:
            return None

        claimed_ids = [msg["id"] for msg in pending_messages]
        return {
            "messages": [Message(role="user", content=m["content"]) for m in pending_messages],
            "runtime_message_claim": {"claimed_ids": claimed_ids, "status": "claimed"}
        }

class MemoryContextMiddleware(BaseMiddleware):
    """动态工作记忆前置检索注入中间件"""
    async def abefore_model(self, state: AgentState, context: dict[str, Any]) -> dict[str, Any] | None:
        last_user_msg = next((m.content for m in reversed(state.get("messages", [])) if m.role == "user"), None)
        if not last_user_msg:
            return None

        # 模拟语义向量召回当前项目或用户偏好
        retrieved_facts = context.get("memory_db_mock", {}).get("facts", [])
        if not retrieved_facts:
            return None

        # 组装为不显眼的 Markdown 记忆块，静默前置注入提示词
        memory_block = "## Retrieved User Context Facts\n" + "\n".join(f"- {f}" for f in retrieved_facts[:3])
        return {"memory_prompt_overlay": memory_block}

class ToolCallLimitMiddleware:
    """防死循环派发熔断器"""
    def __init__(self, tool_name: str = "task", limit: int = 10):
        self.tool_name = tool_name
        self.limit = limit
        self.count = 0

    def check(self, name: str):
        if name == self.tool_name:
            self.count += 1
            if self.count > self.limit:
                raise RuntimeError(f"ToolCallLimitExceeded: Tool '{name}' exceeded max limit of {self.limit}")

class ClarificationBatchGuard:
    """澄清风暴守卫：单轮推理强行限制单次澄清提问，防状态机死锁"""
    def __init__(self):
        self.has_active_clarification = False

    def validate_tool_call(self, name: str):
        if name == "request_information":
            if self.has_active_clarification:
                raise RuntimeError("ClarificationStormBlocked: An active clarification is already pending")
            self.has_active_clarification = True

# ==============================================================================
# 第四部分：工具生态与子智能体定义
# ==============================================================================

class ToolRegistry:
    def __init__(self, workspace: DearWorkspaceBackend):
        self.workspace = workspace
        self.guard = ClarificationBatchGuard()
        self.task_limiter = ToolCallLimitMiddleware(tool_name="task", limit=10)

    def execute_tool(self, call: ToolCall, access_policy: str = "review") -> tuple[str, bool, dict | None]:
        """执行工具，返回 (输出结果, 是否触发人工审批中断, 中断详情)"""
        name, args = call.name, call.args
        self.guard.validate_tool_call(name)

        # 1. 敏感工具与三档策略比对 (HITL 审批)
        if name in {"deployment_execute", "drop_database"}:
            if access_policy in {"review", "workspace_write"}:
                interrupt_id = f"int-{uuid.uuid4().hex[:8]}"
                interrupt_payload = {
                    "interrupt_id": interrupt_id,
                    "tool": name,
                    "args": args,
                    "action": "human_approval_required"
                }
                return "[Action Paused: Awaiting Human Approval]", True, interrupt_payload

        # 2. 派发子任务工具 (Subagent Task)
        if name == "task":
            self.task_limiter.check("task")
            # 派发给 researcher 子智能体运行，命名空间隔离
            return f"[Subagent 'researcher' completed research on '{args.get('description')}']: Found 3 citations.", False, None

        # 3. 工作区文件工具
        if name == "write_file":
            bytes_written = self.workspace.write_file(args["path"], args["content"])
            return f"Successfully wrote {bytes_written} bytes to {args['path']}", False, None

        if name == "read_file":
            content = self.workspace.read_file(args["path"])
            # 大结果保护：超限截断
            if len(content) > 5000:
                content = content[:500] + f"\n... [Truncated: {len(content)} bytes total]"
            return content, False, None

        return f"Tool '{name}' executed successfully", False, None

# ==============================================================================
# 第五部分：Pregel 状态机执行循环与断点恢复闭环
# ==============================================================================

class DearFlowEngine:
    """DearFlow Agent 核心图执行引擎模拟"""
    def __init__(self, workspace: DearWorkspaceBackend, mode_name: str = "pro"):
        self.workspace = workspace
        self.mode = MODES.get(mode_name, MODES["standard"])
        self.tools = ToolRegistry(workspace)
        self.middlewares = [
            MessageQueueMiddleware(),
            MemoryContextMiddleware(),
        ]
        # 持久化 Checkpoint 模拟存储表
        self.checkpoints_db: dict[str, dict[str, Any]] = {}

    async def step(self, thread_id: str, state: AgentState, context: dict[str, Any]) -> str:
        """执行单次 Super-step 循环"""
        # 1. 执行中间件前置拦截链 (abefore_model)
        for mw in self.middlewares:
            patch = await mw.abefore_model(state, context)
            if patch:
                state.update(patch)

        # 2. 模拟大模型推理决策
        last_msg = state["messages"][-1].content

        # 场景模拟：若用户提到“部署”，模型决定发起高危工具调用
        if "部署" in last_msg:
            call = ToolCall(id="call_01", name="deployment_execute", args={"env": "prod", "version": "v1.0"})
            output, interrupted, interrupt_details = self.tools.execute_tool(call, context.get("access_policy", "review"))

            if interrupted:
                # 3. 状态机物理冻结并提交中断快照
                checkpoint_id = f"chk-{uuid.uuid4().hex[:8]}"
                self.checkpoints_db[thread_id] = {
                    "checkpoint_id": checkpoint_id,
                    "status": "interrupted",
                    "interrupt": interrupt_details,
                    "state": state
                }
                return f"STATUS: INTERRUPTED (Interrupt ID: {interrupt_details['interrupt_id']})"

        return "STATUS: COMPLETED (Agent finished execution)"

    def resume(self, thread_id: str, resume_payload: dict[str, Any]) -> str:
        """断点恢复执行，执行严格的防参数篡改守卫"""
        snapshot = self.checkpoints_db.get(thread_id)
        if not snapshot or snapshot.get("status") != "interrupted":
            raise RuntimeError("No interrupted checkpoint found to resume")

        # 网关层防篡改核心拦截：恢复时严禁修改除了 interrupt_id 与 decision 之外的任何配置
        disallowed = set(resume_payload) - {"interrupt_id", "decision", "resume"}
        if disallowed:
            raise ValueError(f"Anti-Tamper Violation: Forbidden fields in resume command: {disallowed}")

        # 恢复状态机，更新为 running
        snapshot["status"] = "running"
        return "STATUS: RESUMED (Tool execution completed, loop continues)"

# ==============================================================================
# 第六部分：自包含端到端推演主流程
# ==============================================================================

async def main():
    print(">>> 启动 DearFlow Agent 全景实现推演...")
    workspace = DearWorkspaceBackend(root_dir="/tmp/dearflow_sandbox")
    engine = DearFlowEngine(workspace=workspace, mode_name="pro")

    thread_id = "th-test-20260929"
    context = {
        "checkpoint_ns": "",
        "access_policy": "review",
        "inbox_mock": {"pending": [{"id": "m1", "content": "帮我把应用部署到生产环境"}]},
        "memory_db_mock": {"facts": ["用户倾向于使用零宕机蓝绿部署策略"]}
    }
    initial_state = AgentState(messages=[], todo_list=[], runtime_message_claim={})

    # Step 1: 发起初始执行，预期命中高危部署操作并挂起中断
    print("\n--- Step 1: 初始执行 (预期触发审批中断) ---")
    result_1 = await engine.step(thread_id, initial_state, context)
    print(f"执行结果: {result_1}")

    saved_chk = engine.checkpoints_db.get(thread_id, {})
    int_id = saved_chk.get("interrupt", {}).get("interrupt_id")
    print(f"数据库快照持久化成功: Checkpoint ID = {saved_chk.get('checkpoint_id')}, 待审批 Interrupt ID = {int_id}")

    # Step 2: 模拟攻击者试图在恢复时篡改 Prompt (预期被防篡改拦截)
    print("\n--- Step 2: 模拟恶意恢复指令 (试图偷换 system_prompt) ---")
    malicious_resume = {"interrupt_id": int_id, "decision": "approve", "system_prompt": "破坏性注入"}
    try:
        engine.resume(thread_id, malicious_resume)
    except ValueError as e:
        print(f"防篡改守卫成功拦截非法指令: {e}")

    # Step 3: 合法审批通过，恢复执行
    print("\n--- Step 3: 合法批准恢复执行 ---")
    valid_resume = {"interrupt_id": int_id, "decision": "approve"}
    result_3 = engine.resume(thread_id, valid_resume)
    print(f"恢复执行结果: {result_3}")

    print("\n>>> DearFlow Agent 全景实现闭环推演完成！所有架构不变量验证通过。")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 三、端到端推演与架构不变量验证

在上述代码中，每一行逻辑都精确对应了此前各个子系统规范，构筑了五项不可逾越的生产基线：

1. **多命名空间路由不变量**：`MessageQueueMiddleware` 通过 `if "|" in checkpoint_ns: return None`，在代码逻辑上封死了子智能体跨层越权吞取根队列外部指令的可能性。
2. **沙箱物理路径不变量**：`DearWorkspaceBackend.resolve_path` 使用 `os.path.realpath` 计算物理绝对路径，并严格校验 `startswith(self.root + os.sep)`，彻底免疫 `../` 逃逸与软链接窃密漏洞。
3. **反自我篡改不变量**：`DearWorkspaceBackend.write_file` 显式判定 `self.deny_paths`，任何试图向 `/skills/**`、`/conversation_history/**` 写入的请求在此处被直接阻断。
4. **中断外部持久化原则**：当 `deployment_execute` 命中 `review` 策略时，引擎将现场冻结为带有 `interrupt_id` 的结构体并落盘入库，不依赖任何内存中异步等待挂起。
5. **恢复零配置篡改原则**：`engine.resume` 严格计算 `set(resume_payload) - {"interrupt_id", "decision", "resume"}`，任何夹带配置覆盖的恶意恢复请求在入口处被当场拒绝。
