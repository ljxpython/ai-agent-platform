# 整体方案：智能体上下文防爆治理与工业级工具截断/子任务架构升级

## 1. 背景与现状病灶

平台在处理深度行业调研（如灵巧手行业调研 `6f09c502`）与全仓库架构代码剖析（`e5492054`）时，出现了严重的多轮连续触发“整理上下文”现象，甚至单轮任务触发了整整 6 次压缩。

通过直接反序列化底层 PostgreSQL Checkpoint Blobs，挖掘出的事实数据如下：
- **灵巧手调研会话**：总消息 109 条，总字符数 311,249 字符（约 10 万 ~ 15 万 Tokens），`search_web` 独占 73KB，`read_file` 46KB，AI 长篇草稿 40KB，触发 3 次压缩。
- **全仓库剖析会话**：总消息 83 条，总字符数 386,861 字符（约 13 万 ~ 19 万 Tokens），`github_query` 独占 188KB（约 6.4 万 Tokens，占满半个窗口），`execute` 独占 85KB，触发 6 次压缩。

### 为什么会陷入“压缩 -> 塞满 -> 再压缩”的恶性循环？
1. **模型配置限制**：当前主要模型 `deepseek-v4.1-flash` 的物理窗口为 128K（131,072 Tokens）。
2. **触发与保留剪刀差**：`AGENT_CONTEXT_TRIGGER_POLICY=0.85`（约 9.8 万 Tokens 触发），压缩后保留 40%（约 4.6 万 Tokens）。
3. **工具过度倾倒（Dump-All Anti-Pattern）**：单次 `github_query` 或 `execute` 一口气倒出 10KB ~ 26KB 原始文本。在 Agent 连续调用的重度循环中，只需调用 5~6 次大工具，留存的 4.6 万预算立刻再次被灌满，迅速触发第二次、第三次压缩，直到任务结束。

---

## 2. 工业级产品与 Antigravity 架构对标剖析

为什么类似 Antigravity、Claude Computer Use / Artifacts、Cursor、Windsurf、Manus、OpenAI Deep Research 等工业级系统在进行全库扫描、代码分析与深度调研时，响应极其迅猛，且极少出现频繁打爆上下文？核心设计思想拆解如下：

### 核心设计 1：外部化产物与溢出落盘引用（Spill-to-Disk & Pointer Reference）
- **反模式（当前平台现状）**：工具抓取到什么内容，就原封不动、完整无缺地作为 `ToolMessage.content` 塞进 LLM 的提示词历史中。
- **工业级标准（Antigravity / Claude Artifacts）**：
  - 工具只返回“足以让 Agent 做出下一步决策”的元数据摘要或精简预览。
  - 大于设定阈值（例如 3KB~4KB）的巨型结果（如完整的 `git trees`、大段终端日志、网页完整 DOM），在底层沙箱中直接写入工作区文件（例如 `/tmp/workspace/scratch/tool_output_xxx.json`）。
  - 返回给大模型的 `ToolMessage` 仅包含指针：“*输出过大（26.8KB），已自动保存至 `/tmp/workspace/scratch/tool_output_xxx.json`。前 50 行预览如下... 如需深度过滤请使用 grep/read_file。*”
  - **效果**：工具输出对上下文的消耗从几万 Tokens 瞬间降为几十 Tokens，且完全不丢失原始数据。

### 核心设计 2：外科手术式渐进探测工具（Surgical & Progressive Tool Design）
- **反模式**：提供“无界贪婪工具”，一次请求把 100 个 commit 或几万行代码直接全量拉回。
- **工业级标准（Cursor / Windsurf / Antigravity）**：
  - 严格限制单次工具读取的行数和字节窗口（例如 Antigravity 的 `read_file` 强制限制每次最多 800 行或 46KB，且显式要求通过 `StartLine` 和 `EndLine` 分页）。
  - `grep`/`ripgrep` 仅返回匹配行及其行号，绝不把整个命中文件的完整内容吐给大模型。
  - 强制工具入参具备细粒度约束，倒逼 Agent 采用“查概要 -> 定位关键点 -> 精准单点深入”的专业排查链路。

### 核心设计 3：分层多智能体与隔离上下文（Subagent Delegation / Hierarchical Map-Reduce）
- **反模式**：把一个长达 60 步、涉及海量信息检索的重度任务，塞在单一的主会话线程里串行执行，导致历史消息雪球越滚越大。
- **工业级标准（Manus / OpenAI Deep Research / Antigravity Subagents）**：
  - 主智能体（Parent Agent）不亲自下场读那几十篇论文或 50 个代码文件。
  - 主智能体通过 `invoke_subagent` 委派专项任务给独立的 Research Subagent。
  - **关键点在于：子智能体运行在完全隔离的上下文环境（Isolated Context / Branched Workspace）中！**
  - 子智能体可以在它自己的独立线程里调用 50 次搜索，吃完它的上下文无所谓；执行完毕后，子智能体只向主智能体回复一份 2000 字的精华总结与结论。
  - 主智能体的上下文自始至终干净清爽，永远不会发生多轮恶性压缩。

### 核心设计 4：历史工具消息动态虚拟折叠（Ephemeral Tool Pruning / Context Folding）
- **反模式**：会话进行到第 50 步时，第 5 步调用的 `ls`、第 8 步调用的 `git tree` 依然以原始长文本驻留在每一次向大模型发送的 Prompt 里。
- **工业级标准（工业级 IDE Agent）**：
  - 大模型在做出当前动作后，之前的中间执行结果在后续轮次中的信息熵急剧衰减。
  - 在下发给 LLM 组装请求前，中间件会将已过时的旧 ToolMessage 内容替换为轻量占位符（如 `[Tool Output Pruned: 15KB execution results retained on disk]`），仅保留最近 3~5 次工具调用的完整结果。
  - 这种机制在运行时自动将旧工具输出剥离出活跃上下文，实现无感平滑抗爆。

---

## 3. 总体架构与改造方案设计

基于上述对标与平台现有代码架构（LangGraph + Middleware 架构），我们制定三阶段递进落地路线：

```
┌────────────────────────────────────────────────────────────────────────┐
│                        用户输入 / 调度层                               │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                        ┌───────────▼───────────┐
                        │   运行时调度与中间件   │
                        └───────────┬───────────┘
                                    │
    ┌───────────────────────────────┴──────────────────────────────┐
    ▼                                                              ▼
【第一防线：工具结果溢出落盘】                 【第二防线：上下文动态虚拟折叠】
Tool Spill-to-Disk Middleware                  Ephemeral Tool Pruning
- 拦截 github_query / execute / web            - 识别陈旧轮次的中间 ToolMessage
- 单次输出 > 4KB 自动存入 Workspace            - 发起大模型推理前虚拟置换为摘要占位符
- ToolMessage 仅返回预览与文件引用             - 数据库完整持久化，仅在大模型视口折叠
    │                                                              │
    └───────────────────────────────┬──────────────────────────────┘
                                    │
                        ┌───────────▼───────────┐
                        │  第三防线：子任务隔离  │
                        │  Subagent Delegation  │
                        └───────────────────────┘
                        - 深度调研/代码大扫描按需
                          分发到独立会话运行
                        - 仅向主线程汇聚最终结论
```

### 阶段一：工具层结果溢出落盘与有界约束（Spill-to-Disk Interceptor）
1. 在 `runtime-service` 的工具执行拦截管道中引入 `ToolOutputSpillMiddleware`；
2. 设定单次工具输出安全阈值（如 `MAX_TOOL_OUTPUT_CHARS = 4000`）；
3. 针对 `github_query`、`execute`、`search_web`、`fetch_page`：
   - 当输出体积小于阈值时，保持原样透出；
   - 当输出体积超过阈值时，自动将全量数据写入沙箱当前工作目录下的 `.context_spill/tool_{tool_name}_{uuid}.json`；
   - 替换 `ToolMessage.content` 为结构化提示卡片（包含前 20 行 / 1500 字符预览、数据总大小、文件绝对路径、以及指导 Agent 按需读取的引导词）。

### 阶段二：运行时上下文动态虚拟折叠（Ephemeral Tool Pruning）
1. 在 `conversation_offloading.py` 或请求构造拦截器中，实现只对大模型视口生效的“虚拟折叠”：
   - 区分活跃工作区（最近 N 轮工具调用）与历史事实区（较早轮次的工具调用）；
   - 对历史轮次中已被 AI 消费并形成阶段总结的 ToolMessage，将其长内容动态替换为 `[Tool Output Collapsed: {tool_name} returned {bytes} bytes]`；
   - 保证数据库中的持久化 Checkpoint 完整无损（方便前端还原排障），但发往 LLM 的实时 Prompt 体积大幅削减 70%~90%。

### 阶段三：长任务 Subagent 隔离执行规范与指引
1. 梳理 `deep-research`、`codebase-analysis` 等重度技能的执行模式；
2. 确立“重型扫描由子图/独立子会话消化，主图只承载阶段报告与人机交互”的架构边界；
3. 为后续大模型多 Agent 协作提供上下文物理隔离的通信通道。

---

## 4. 关键指标与收益预估

1. **单次 ToolMessage 占用压降**：
   - `github_query` 从 188KB（~64K Tokens）压降至 $\le 20\text{KB}$（~6K Tokens），降低 **90%**；
   - `execute` 从 85KB（~29K Tokens）压降至 $\le 15\text{KB}$，降低 **82%**。
2. **长任务压缩触发频次**：
   - 灵巧手调研会话：从 3 次压缩降至 **0~1 次**；
   - 全库代码剖析会话：从 6 次严重恶性循环压缩降至 **0~1 次**。
3. **模型响应速度与成本**：
   - 避免向大模型反复喂送几十万冗余历史字符，首字响应时间（TTFT）预期提速 40%~60%，单任务 Token 消耗压降 50% 以上。
