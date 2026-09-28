# GraphHarbor 功能增强需求提案：子智能体（Subagent）执行轨迹与工具调用历史暴露

- **提案编号：** RFC-20260928-GH-SUBAGENT-HISTORY
- **提案方：** AI Agent Platform 平台研发团队
- **接收方：** GraphHarbor 核心研发团队
- **状态：** 提审中 (Proposed)
- **优先级：** P1 (影响多智能体审查回溯体验与可解释性)

---

## 一、需求背景与业务痛点

在当前 AI Agent Platform 平台的多智能体执行场景中（例如代码审计与独立验证的 `research`、`general-purpose` 子智能体），主 Agent 采用 **LangGraph Subagent / Tool-based Delegation** 模式（通过调用 `task` 工具动态派发子图执行）。

### 1. 实时流式与历史回放的断层表现
- **实时执行时（Streaming）**：GraphHarbor 会通过 SSE 向下游下发带有 `namespace: ["tools:<call_id>"]` 的实时事件流，前端能够实时捕捉并展示子智能体调用的工具（如 `ls`、`read_file`、`grep` 等）。
- **会话持久化与历史加载时（Historical Reload）**：用户刷新浏览器或重新进入历史线程时，平台前端调用 `GET /threads/{id}/state` 或 `POST /threads/{id}/history`。此时 **GraphHarbor 只返回了根命名空间（`checkpoint_ns = ""`）的 Checkpoint 状态**，子智能体在主图仅表现为一条普通的 `ToolMessage (name="task")` 聚合文本。
- **痛点后果**：子智能体曾经执行过的**完整工具调用序列、具体调用的文件路径、命令参数以及报错信息**在历史回放中全部丢失不可见。用户无法审计子智能体到底读了哪些文件、做了什么操作，严重影响了企业级智能体平台的合规审计与可溯源性。

---

## 二、底层存储现状与技术依据（实测验证）

经过平台团队对底层 Checkpointer 数据库（PostgreSQL `graphharbor_acceptance`）的实测反序列化分析，**确认子智能体的所有消息和工具调用数据在底层均 100% 完整保留，并没有发生数据丢失**。

### 实测证据（线程 `fba64a6c-0268-4609-bfc8-802c72b26dec`）：
1. 在 `checkpoints` 表中，清晰记录了子命名空间：
   ```sql
   SELECT DISTINCT checkpoint_ns FROM checkpoints WHERE thread_id = 'fba64a6c-0268-4609-bfc8-802c72b26dec';
   -- 返回结果：
   -- '' (根图)
   -- 'tools:89b00bd9-03c0-6b3a-4dc0-566fe060a451' (子智能体命名空间)
   ```
2. 在 `checkpoint_blobs` 表中，使用 `JsonPlusSerializer` 解码子图的 `messages` blob，包含了完整的 **16 条消息与 10 次工具调用**：
   ```text
   [0] type=human, name=None, tool_calls=[]
   [1] type=ai, name=research, tool_calls=['ls', 'read_file']
   [2] type=tool, name=ls, tool_calls=[]
   [3] type=tool, name=read_file, tool_calls=[]
   [4] type=ai, name=research, tool_calls=['read_file', 'read_file', 'read_file']
   [5] type=tool, name=read_file, tool_calls=[]
   [6] type=tool, name=read_file, tool_calls=[]
   [7] type=tool, name=read_file, tool_calls=[]
   [8] type=ai, name=research, tool_calls=['grep', 'grep', 'glob']
   [9] type=tool, name=grep, tool_calls=[]
   [10] type=tool, name=grep, tool_calls=[]
   [11] type=tool, name=glob, tool_calls=[]
   [12] type=ai, name=research, tool_calls=['glob', 'read_file']
   [13] type=tool, name=glob, tool_calls=[]
   [14] type=tool, name=read_file, tool_calls=[]
   [15] type=ai, name=research, tool_calls=[]
   ```

### 瓶颈定位
LangGraph 官方在 `multi-agent/subagents` 规范中指出：
> *"Because subagents are called inside tool functions, LangGraph cannot statically discover them. This means `get_state` with `subgraphs` will not return subagent state."*

由于 LangGraph 原生 `subgraphs=true` 仅静态遍历编译拓扑中的静态节点，无法动态关联由工具调起的子图，因此**需要 GraphHarbor Agent Server 在 REST 状态层补充子图命名空间的读取能力**。

---

## 三、需求建议与接口契约设计（供 GraphHarbor 选择）

为了兼顾通用性与开发成本，我们提出以下两套方案供 GraphHarbor 团队评估：

### 方案 1（强烈推荐·开箱即用）：支持 `expand_subagents=true` 自动聚合

- **设计思路**：客户端查询线程最新状态时，Server 端在返回 Root 状态的同时，自动汇聚该 Thread 下关联的所有子命名空间数据。
- **请求端点**：
  ```http
  GET /threads/{thread_id}/state?expand_subagents=true
  ```
- **响应体扩展**（在现有的 `ThreadState` 结构中新增 `subagents` 字段）：
  ```json
  {
    "values": {
      "messages": [ ...主图消息... ]
    },
    "checkpoint": {
      "thread_id": "fba64a6c-0268-4609-bfc8-802c72b26dec",
      "checkpoint_ns": "",
      "checkpoint_id": "1f1bad43-..."
    },
    "subagents": {
      "tools:89b00bd9-03c0-6b3a-4dc0-566fe060a451": {
        "namespace": ["tools:89b00bd9-03c0-6b3a-4dc0-566fe060a451"],
        "trigger_call_id": "call_00_mc3n55mycghn1euoyfzodwiv",
        "checkpoint_id": "1f1bad43-84ff-6078-8020-ad4e4fa8610c",
        "values": {
          "messages": [
            { "role": "ai", "name": "research", "tool_calls": [...] },
            { "role": "tool", "name": "ls", "content": "..." },
            { "role": "tool", "name": "read_file", "content": "..." }
          ]
        }
      }
    }
  }
  ```
- **实现成本**：Server 端在读取完根 checkpoint 后，仅需一条 SQL 查询当前 thread 下所有 `checkpoint_ns LIKE 'tools:%'` 的最新记录并组装返回，开销在毫秒级以内，客户端无需发起多次 HTTP 请求。

---

### 方案 2（标准扩展）：对齐 LangGraph SDK Checkpoint 指定命名空间查询

- **设计思路**：支持客户端按指定的 `checkpoint_ns` 单独拉取子图 State 或 History，对齐 LangGraph 最新 Python SDK 规范。
- **端点 A：支持按 checkpoint 参数查询 State**
  ```http
  POST /threads/{thread_id}/state/checkpoint
  Content-Type: application/json

  {
    "checkpoint": {
      "checkpoint_ns": "tools:89b00bd9-03c0-6b3a-4dc0-566fe060a451"
    }
  }
  ```
  或者简化为 Query 参数：
  ```http
  GET /threads/{thread_id}/state?checkpoint_ns=tools:89b00bd9-03c0-6b3a-4dc0-566fe060a451
  ```
- **端点 B：支持按 checkpoint 参数查询 History**
  ```http
  POST /threads/{thread_id}/history
  Content-Type: application/json

  {
    "checkpoint": {
      "checkpoint_ns": "tools:89b00bd9-03c0-6b3a-4dc0-566fe060a451"
    },
    "limit": 10
  }
  ```
- **底层对接**：GraphHarbor 将 `checkpoint_ns` 传递给底层 Checkpointer 的 `config["configurable"]["checkpoint_ns"]`。

---

## 四、安全与性能评估

1. **鉴权与权限继承**：
   子图 checkpoint 严格归属于同一个 `thread_id`，GraphHarbor 原有的 Thread 鉴权策略（如基于 `thread_access` 和 `project_id` 的校验）对子图完全生效，无需引入新的权限模型。
2. **性能与索引利用**：
   PostgreSQL 库中的 `checkpoints` 与 `checkpoint_blobs` 表均以 `(thread_id, checkpoint_ns)` 建有复合索引，查询单条线程的子图数据不经过全表扫描，性能极其高效。

---

## 五、期望交付与对接计划

1. **评估确认**：请 GraphHarbor 团队评估上述方案 1 与方案 2 的可行性及排期；
2. **联调环境**：发布含有该能力的 GraphHarbor 测试镜像/环境，提供示例验证；
3. **平台端承诺**：平台团队已准备好前端与网关承接逻辑，一旦 GraphHarbor 接口发布，平台可在 1 个工作日内完成端到端联调上线。
