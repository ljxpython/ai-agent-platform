# DeerFlow 能力差距分析与实现指南

> 分析日期：2026-10-05
> 参考项目：`deer-flow`（字节跳动开源 Agent 平台）
> 当前平台：`ai-agent-platform`
> 文档性质：技术调研知识文档，不是具体项目计划

> 2026-10-09复核：总体统计与“未实现”表保留10-05调研判断，不能直接用于当前排期。F07已获批准并完成非前端源码/候选，剩前端与正式CAS发布，见[F07实施](../projects/20261009-agent-thread-auto-title/README.md)；其余能力须逐项核对代码，不以旧表判未实现。

---

## 一、总体概况

扫描 DeerFlow 源码结构（`backend/packages/harness/deerflow/` + `backend/app/gateway/` + `frontend/src/`），
与当前平台能力对比，共整理 **17 个维度约 135 项能力**。

| 状态 | 数量 | 占比 |
|---|---|---|
| 🟢 已实现 | ~55 | ~41% |
| 🟡 部分实现 | ~10 | ~7% |
| 🔴 未实现 | ~70 | ~52% |

**核心结论**：我们的执行链底座（GraphHarbor + HITL + SSE + Checkpoint + 子智能体 + 记忆 + MCP + 定时调度）都有，不差。差距主要在**执行引擎中间件体系**（安全护栏）、**工具生态**（搜索/抓取）、**前端交互体验**（润色/建议/语音）、**IM 渠道**（飞书/Slack）。

---

## 二、能力对比总表

### 2.1 执行引擎

| 能力 | 状态 | DeerFlow 源码位置 |
|---|---|---|
| LangGraph 图执行 | 🟢 已实现 | `langgraph>=1.2.9` |
| 流式 SSE 输出 | 🟢 已实现 | SSE 专项治理完成 |
| HITL 人工介入审批 | 🟢 已实现 | 含超时/续期/重放 |
| Checkpoint / 对话恢复 | 🟢 已实现 | GraphHarbor 原生 |
| **上下文压缩（Summarization）** | 🔴 未实现 | `agents/middlewares/summarization_middleware.py` |
| **Token 预算限制** | 🔴 未实现 | `agents/middlewares/token_budget_middleware.py` |
| **工具输出预算裁剪** | 🔴 未实现 | `agents/middlewares/tool_output_budget_middleware.py` |
| **循环检测** | 🔴 未实现 | `agents/middlewares/loop_detection_middleware.py` |
| **安全终止检测** | 🔴 未实现 | `agents/middlewares/safety_finish_reason_middleware.py` |
| **模型长度终止检测** | 🔴 未实现 | `agents/middlewares/model_length_finish_reason_middleware.py` |
| LLM 错误处理中间件 | 🟡 部分 | `agents/middlewares/llm_error_handling_middleware.py` |
| **PII 脱敏** | 🔴 未实现 | `agents/middlewares/pii_redaction_middleware.py` |
| **澄清请求多字段表单** | 🟡 部分 | `tools/builtins/clarification_tool.py` |

### 2.2 沙箱系统

| 能力 | 状态 | 备注 |
|---|---|---|
| 本地文件系统沙箱 | 🟢 已实现 | |
| Docker 容器沙箱 | 🟡 部分 | DeerFlow Agent 已接，但非默认主路径 |
| Kubernetes 沙箱 | 🔴 未实现 | |
| **str_replace 并发串行化** | 🔴 未实现 | 按 `(sandbox.id, path)` 串行化 |
| **沙箱健康检查 + 预热池** | 🔴 未实现 | 容器意外退出后自动重建 |

### 2.3 记忆系统

| 能力 | 状态 | 备注 |
|---|---|---|
| 对话记忆自动提取 | 🟢 已实现 | |
| 跨会话记忆持久化 | 🟢 已实现 | |
| 记忆注入 System Prompt | 🟢 已实现 | |
| 作用域安全写入 | 🟢 已实现 | |
| **矛盾事实原子替换** | 🔴 未实现 | 新事实替换旧矛盾的原子操作 |
| **记忆 SHA-256 事件标识** | 🔴 未实现 | 避免记忆内容进入事件存储 |

### 2.4 MCP

| 能力 | 状态 | 备注 |
|---|---|---|
| stdio/SSE/HTTP MCP Server | 🟢 已实现 | |
| 个人 MCP | 🟢 已实现 | |
| MCP 任务追踪 | 🟢 已实现 | |
| **MCP 工具缓存热重置** | 🔴 未实现 | `POST /api/mcp/cache/reset` |
| **MCP OAuth 认证** | 🔴 未实现 | `mcp/oauth.py`，Client Credentials flow |
| **MCP 路由中间件** | 🔴 未实现 | 动态路由到指定 MCP Server |

### 2.5 技能系统

| 能力 | 状态 | 备注 |
|---|---|---|
| SKILL.md 技能定义 | 🟢 已实现 | |
| **技能扫描（SkillScan）** | 🔴 未实现 | 静态安全扫描，CRITICAL 阻止安装 |
| **技能导出（.skill 归档）** | 🔴 未实现 | ZIP 打包，可跨实例分发 |
| **技能安装（.skill 归档）** | 🔴 未实现 | 解压 + 安全扫描 |
| **技能权限控制（Tool Policy）** | 🔴 未实现 | Skill 声明可用工具白名单 |
| **技能激活中间件** | 🔴 未实现 | 动态激活/停用 |
| **斜杠命令面板** | 🔴 未实现 | `/skill-name` 快捷触发 |

### 2.6 子智能体

| 能力 | 状态 | 备注 |
|---|---|---|
| 子智能体并发执行 | 🟢 已实现 | |
| 工具调用历史持久化 | 🟢 已实现 | |
| 批量子智能体 | 🟢 已实现 | |
| 内置 general-purpose | 🟢 已实现 | |
| **内置 bash 子智能体** | 🔴 未实现 | Shell 专家子智能体 |
| **子智能体容量限制** | 🔴 未实现 | `subagent_limit_middleware.py` |

### 2.7 工具生态

| 能力 | 状态 | 备注 |
|---|---|---|
| 浏览器工具 | 🟢 已实现 | |
| 图片生成/编辑/分析 | 🟢 已实现 | |
| 图表生成 | 🟢 已实现 | |
| **网页搜索（Tavily）** | 🔴 未实现 | 需 API Key |
| **网页搜索（DuckDuckGo）** | 🔴 未实现 | 免费备选 |
| **网页抓取（Jina AI）** | 🔴 未实现 | 免费，`r.jina.ai` 代理 |
| **网页抓取（Firecrawl）** | 🔴 未实现 | 付费，支持 JS 渲染 |
| **DuckDB 结构化查询** | 🔴 未实现 | 对上传文件执行 SQL |

### 2.8 文件上传与工件

| 能力 | 状态 | 备注 |
|---|---|---|
| 文件上传（基础） | 🟢 已实现 | |
| 工件访问 API | 🟢 已实现 | |
| HTML 沙箱预览 | 🟢 已实现 | |
| **文件上传自动转换（PDF/PPT/Word→MD）** | 🔴 未实现 | `markitdown` 库 |
| **工件归档** | 🔴 未实现 | |
| **工具产物自动捕获** | 🔴 未实现 | `artifact_capture_middleware.py` |

### 2.9 定时调度

| 能力 | 状态 | 备注 |
|---|---|---|
| Cron 定时任务 | 🟢 已实现 | |
| Cron 时间预览 API | 🟢 已实现 | |
| **多实例调度（multi-instance）** | 🔴 未实现 | 多 Pod 防重复执行 |
| **执行所有权心跳** | 🔴 未实现 | 配合多实例调度 |

### 2.10 IM 渠道

| 能力 | 状态 | 备注 |
|---|---|---|
| **飞书（Lark）集成** | 🔴 未实现 | WebSocket 长连接，流式卡片更新 |
| **Slack 集成** | 🔴 未实现 | |
| **Telegram 集成** | 🔴 未实现 | |
| **钉钉集成** | 🔴 未实现 | DeerFlow 有 `dingtalk.py` |

### 2.11 前端交互体验

| 能力 | 状态 | 备注 |
|---|---|---|
| 会话回收站 | 🟢 已实现 | |
| 特性开关 | 🟢 已实现 | |
| SSE 心跳保活 | 🟢 已实现 | |
| 国际化 i18n | 🟢 已实现 | |
| **自动对话标题生成** | 🟡 非前端源码/候选已完成；前端/正式CAS发布待完成，自动默认关闭 | metadata+同一受管HTTP生成器，见[F07实施](../projects/20261009-agent-thread-auto-title/README.md) |
| **输入润色（Input Polish）** | 🔴 未实现 | AI 优化用户草稿 |
| **AI 跟进建议（Suggestions）** | 🔴 未实现 | 对话后自动生成 3 条建议 |
| **Todo 列表（多步任务）** | 🔴 未实现 | `write_todos` 工具 + `TodoMiddleware` |
| **语音输入** | 🔴 未实现 | 浏览器原生 SpeechRecognition |
| **用户偏好设置** | 🔴 未实现 | 跨设备同步个性化配置 |

### 2.12 其他

| 能力 | 状态 | 备注 |
|---|---|---|
| **CSRF 防护** | 🔴 未实现 | `csrf_middleware.py` |
| **知识库（RAG）** | 🔴 未实现 | 项目级文档检索 |
| **Langfuse 用户反馈** | 🔴 未实现 | 用户反馈直传 Langfuse |
| **Checkpoint 保留策略** | 🔴 未实现 | 自动清理旧 Checkpoint |
| **上下文用量统计** | 🔴 未实现 | Token 用量分析 API |
| **TUI（终端工作台）** | 🔴 未实现 | Textual TUI，无需启动 Web |

---

## 三、未实现功能详细说明

> 每个功能点说明：是什么、DeerFlow 怎么做的、我们要做什么、关键代码/配置。

---

### F01 — Token 预算中间件

**是什么**：每次模型调用后累计 Token 用量，达到警告阈值注入预警，达到强制停止阈值终止 Agent。防止失控费用。

**DeerFlow 怎么做**
- 文件：`agents/middlewares/token_budget_middleware.py`
- 挂载点：`after_model` 钩子
- 核心数据结构：`BoundedDict[run_id, TokenUsage]`（有容量上限，防内存泄漏）；`_seen_messages[run_id][msg.id]` 做增量计算，防止 SubAgent 回溯时重复叠加
- 触发警告：队列 `HumanMessage(name="budget_warning")` 到 `_pending_warnings`，在 `wrap_model_call` 注入到请求消息末尾
- 触发强制停止：调 `clone_ai_message_with_tool_calls(last_msg, [], content=stop_text)` 剥离所有工具调用（不能 raise 异常），写 `stop_reason="token_capped"` 到 `runtime.context`

**我们需要做什么**
1. 确认 GraphHarbor 是否支持 `AgentMiddleware` 接口（`before_agent/after_model/wrap_model_call` 等钩子）
2. 实现 `TokenBudgetMiddleware`
3. 实现 `BoundedDict` 工具类（或复用现有有界字典）
4. 在 Agent 工厂注册
5. 在 platform-api agent 配置中增加 `token_budget` 字段

**配置**
```yaml
token_budget:
  enabled: true
  max_tokens: 100000
  max_input_tokens: 0        # 0 = 无上限
  max_output_tokens: 0
  warn_threshold: 0.8
  hard_stop_threshold: 0.95
```

---

### F02 — 循环检测中间件

**是什么**：检测 Agent 是否在重复调用相同工具（死循环）或重复生成相同输出（震荡）。分警告和强制停止两级。

**DeerFlow 怎么做**
- 文件：`agents/middlewares/loop_detection_middleware.py`
- 挂载点：`after_model` 钩子
- **双层检测**：
  - Layer1：对 `tool_calls` 集合做 MD5 hash，滑动窗口（默认 20）内同 hash 超阈值（warn=3, hard=5）
  - Layer2：`deque + Counter` 跟踪单工具调用频率（warn=30, hard=50，可按工具名覆盖）
- **工具 Key 归一化**：
  - `read_file`：精确行号（防止合法循环读不同行被误判）
  - `write_file` / `str_replace`：全参数 hash（文件名 + 内容 hash）
  - 其他：工具名 + 参数组合 hash
- 强制停止：`clone_ai_message_with_tool_calls(last_msg, [], ...)` + 写 `stop_reason="loop_capped"`

**我们需要做什么**
1. 实现 `clone_ai_message_with_tool_calls` 工具函数（剥离 tool_calls 的所有 provider 表面）
2. 实现 `LoopDetectionMiddleware`：维护 per-(thread_id, run_id) 历史
3. 工具 key 归一化策略按需实现（至少要有 read_file 特殊处理）
4. 在 Agent 工厂注册

**配置**
```yaml
loop_detection:
  enabled: true
  warn_threshold: 3
  hard_limit: 5
  window_size: 20
  tool_freq_warn: 30
  tool_freq_hard_limit: 50
```

---

### F03 — 上下文压缩（SummarizationMiddleware）

**是什么**：对话历史接近 context window 上限时，自动用 LLM 将历史消息压缩成摘要，保留最近 N 条 + 摘要，使对话可以无限延续。

**DeerFlow 怎么做**
- 文件：`agents/middlewares/summarization_middleware.py`
- 挂载点：`before_model`（每次模型调用前检查）
- 流程：
  1. tiktoken 估算当前 messages Token 总量
  2. 超过阈值（默认 context window 的 75%）时，取前面的消息发给 summary model
  3. 摘要前先 `before_summarization` hooks 通知 MemoryMiddleware（压缩前提取记忆）
  4. 摘要文本过 `redact_text(summary, pii_config)` PII 脱敏
  5. 用 `RemoveMessage` / `REMOVE_ALL_MESSAGES` 清空旧消息
  6. 插入摘要 `SystemMessage(name="summary")`
  7. 发 `CompactionEvent`（SSE 事件 `context:compaction`）通知前端
- LLM 调用必须带 `TAG_NOSTREAM`（防用户看到幽灵消息）
- 保留最近 `DEFAULT_KEEP=10` 条消息不压缩
- 内置 canned summaries（无历史/太长）短路 LLM 调用

**我们需要做什么**
1. 引入 `tiktoken` 做 Token 估算
2. 实现 `SummarizationMiddleware`：阈值检测 + LLM 摘要调用（async 优先）
3. LangGraph state 操作：`RemoveMessage` 删旧消息 + 插入摘要 SystemMessage
4. 发出 `context:compaction` SSE 事件
5. 与 TodoMiddleware 联动：压缩后检查 todo 是否还在 context 中
6. 与 MemoryMiddleware 联动：压缩前触发 hooks

**配置**
```yaml
summarization:
  enabled: true
  trigger_at_fraction: 0.75
  keep_recent: 10
  summary_model: gpt-4o-mini   # 可选，默认用主模型
```

---

### F04 — 工具输出预算（ToolOutputBudgetMiddleware）

**是什么**：工具返回结果过大时（如网页抓取返回 100KB），将超出部分写入文件，替换为包含文件引用的摘要，防止单个工具撑爆 context。

**DeerFlow 怎么做**
- 文件：`agents/middlewares/tool_output_budget_middleware.py`
- 挂载点：`wrap_tool_call`（工具执行后立即处理）
- 策略：
  - 超出 `max_chars=50000` → 完整内容写入 `/mnt/user-data/outputs/<uuid>.txt`
  - ToolMessage.content 替换为 synopsis：文件路径引用 + head 2000 字符 + tail 2000 字符预览
- 额外：`wrap_model_call` 时对历史 `write_file` content 做重写（已被后续写入覆盖的 → 替换为占位符，只保留最近 `keep_recent_writes=3` 次）
- **只修改 `request.override(messages=...)`，不修改 graph state**（checkpoint 保留原始）

**我们需要做什么**
1. 实现 `ToolOutputBudgetMiddleware`
2. 沙箱文件写入接口（写到线程专属输出目录）
3. `render_tool_output_preview` 函数（head/tail 摘要格式）
4. `write_file` 历史内容重写逻辑（配对 read/write 历史，找出"已被覆盖"的条目）

---

### F05 — PII 脱敏（PiiRedactionMiddleware）

**是什么**：用户消息和工具结果到达模型前，用正则+校验和检测 PII（邮箱、API Key、身份证、信用卡、手机号），替换为确定性占位符，防止敏感信息进入模型上下文或 Langfuse。

**DeerFlow 怎么做**
- 文件：`agents/middlewares/pii_redaction_middleware.py`
- 占位符格式：`[CATEGORY_<base26_token>]`，token = HMAC-SHA256(token_secret, "category:value") 取前 16 字节转 base26（相同原值 → 相同占位符，跨轮次稳定）
- 检测器顺序（固定）：邮箱 → API Key → 国民身份证（Luhn/mod-11 校验）→ 信用卡（Luhn）→ 手机
- 作用范围：
  - `wrap_model_call`：重写 HumanMessage（用户消息，request-scoped，不改 state）
  - `wrap_tool_call`：重写 web 工具 + MCP 工具返回值
  - 共享函数 `redact_text()`：SummarizationMiddleware 和 TitleMiddleware 也调用

**我们需要做什么**
1. 实现 5 种 PII 检测器（正则 + 校验和函数，参考中国身份证 mod-11 规则）
2. 实现占位符生成（HMAC-SHA256 → base26 编码）
3. 实现 `redact_text(text, config)` 共享函数
4. 实现 `PiiRedactionMiddleware`
5. 配置：`token_secret` 必填

**配置**
```yaml
pii_redaction:
  enabled: false             # 默认关闭，按需开启
  token_secret: $PII_SECRET  # 必填，用于 HMAC 密钥
  detectors:
    - email
    - api_key
    - phone
    - credit_card
    - national_id
```

---

### F06 — Todo 列表中间件

**是什么**：让 Agent 在复杂任务开始时写出多步骤计划（`write_todos` 工具），并强制要求完成所有 todo 才能结束对话。历史被压缩后自动注入 todo 提醒。

**DeerFlow 怎么做**
- 文件：`agents/middlewares/todo_middleware.py`
- 依赖：`langchain.agents.middleware.TodoListMiddleware`（上游库基础）+ DeerFlow 扩展
- Todo 数据结构：`{content: str, status: "pending"|"in_progress"|"completed"}`
- 核心扩展：
  - `before_model`：检查 `write_todos` tool call 是否还在 context → 若被压缩出去，注入 `HumanMessage(name="todo_reminder")` 提醒
  - `after_model`：Agent 无 tool_calls（准备结束）但 todos 未全部 completed → 设置 `jump_to="model"` Command 强制继续（最多重试 `_MAX_COMPLETION_REMINDERS=2` 次）
  - 不干预 `model_length_termination` 场景（检查 `runtime.context.get("model_length_terminated")`）

**我们需要做什么**
1. 实现 `write_todos` 工具（持久化到 graph state 的 `todos` 字段）
2. Graph state 增加 `todos: list[Todo]` 字段
3. 实现 `TodoMiddleware`
4. 前端：展示 todo 进度条/列表（可选，Agent 的 `write_todos` 调用本身会在 tool result 中可见）

---

### F07 — 自动对话标题生成（2026-10-09 复核）

**当前已有：** 首消息规则命名、手动改名、Runtime 标题 helper/HTTP、API metadata 落库、双聊天入口 AI 提炼按钮与测试。旧项目明确撤回了 `onCompleted` 自动调用；缺自动触发，不缺整套标题基础能力。

**DeerFlow 的实际设计：** `TitleMiddleware.aafter_model` 检查未命名/一条真实 human/至少一条 AI，返回 Graph `title`；该 hook 可在工具调用前执行，不能等同整轮任务完成。原始用户内容读取自 human.additional_kwargs。附件无正文优先本地命名，模型调用带 nostream；前端还消费 updates 并同步标题缓存。

**已批准取舍与实施：** 保留 `metadata.title` 为唯一事实源，复用受管HTTP生成器，不增加Graph title/Middleware/模型YAML。精确委托、8s一次调用、正文/附件校验、首轮seed和真正数据库CAS已实现并验证；前端同事接浏览器best-effort请求。正式PyPI post43无CAS，新的正式配套发布/锁接入B01未完成，自动默认关闭。

具体源码证据、三层职责、任务、真实模型/HTTP验证与冻结前端交接见[F07项目](../projects/20261009-agent-thread-auto-title/README.md)。R1-R5已获批准，非前端源码/候选完成不等于正式部署或前端完成。

---

### F08 — 网页搜索工具（Tavily / DuckDuckGo）

**是什么**：让 Agent 发起互联网搜索获取实时信息。Tavily 付费质量高，DuckDuckGo 免费备选。

**DeerFlow 怎么做**
- 依赖：`tavily-python>=0.7.17`、`ddgs>=9.10.0`
- 工具接口：`search(query, max_results=5)` → 返回 `[{title, url, content}]`
- 社区工具目录：`deerflow/community/`（Tavily、Jina、Firecrawl、DuckDuckGo）

**我们需要做什么**
1. 实现 `web_search` 工具（优先 Tavily，备选 DuckDuckGo）
2. 速率限制处理 + 超时控制（30s）
3. platform-api 中按项目配置搜索工具启用状态

**配置**
```yaml
search:
  provider: tavily
  tavily_api_key: $TAVILY_API_KEY
  max_results: 5
```

---

### F09 — 网页抓取工具（Jina AI）

**是什么**：Agent 访问指定 URL，提取干净的 Markdown 正文内容。

**DeerFlow 怎么做**
- Jina：HTTP GET `https://r.jina.ai/{url}` 加 `Accept: application/json`（免费，无需 API Key）
- Firecrawl：`firecrawl-py>=1.15.0`，付费，支持 JS 渲染页面
- 内容清洗：`markdownify` 或 `readabilipy` 做 HTML → Markdown

**我们需要做什么**（Jina 最简单，优先实现）
1. 实现 `web_fetch(url)` 工具：HTTP GET `https://r.jina.ai/{url}` → 返回 Markdown
2. 超时 30s + 内容大小限制（与 ToolOutputBudgetMiddleware 配合）
3. Firecrawl 作为可选付费增强

---

### F10 — 文件上传自动转换（PDF/PPT/Excel/Word → Markdown）

**是什么**：用户上传文档后，自动转为 Markdown，注入对话上下文，让 Agent 能直接"读懂"各种文档。

**DeerFlow 怎么做**
- 文件：`app/gateway/upload_ingestion.py` + `routers/uploads.py`
- 依赖：`markitdown[all,xlsx]>=0.0.1a2`
- 支持格式：PDF、PPT、Excel、Word、HTML、CSV
- 流程：上传 → 临时文件 → `convert_file_to_markdown` → 保存原文件 + 转换后 `.md` 文件 → `UploadsMiddleware` 在每次 Agent 执行时注入 `.md` 内容
- 大小限制：单文件 50MB，总计 100MB，最多 10 个文件

**我们需要做什么**
1. 引入 `markitdown` 依赖
2. 在文件上传接口中调用转换（建议在 runtime-service 的上传处理层）
3. 转换后的 `.md` 文件存到线程上传目录
4. 实现/完善 `UploadsMiddleware`（每次 Agent 执行时注入上传文件内容）
5. 前端：上传后显示"已解析为 Markdown"提示

**依赖**
```toml
markitdown = { version = ">=0.0.1a2", extras = ["all", "xlsx"] }
```

---

### F11 — 输入润色（Input Polish）

**是什么**：用户写完草稿后点"润色"，AI 将模糊指令重写为清晰的 Agent 指令（不执行任务，只优化提示词）。

**DeerFlow 怎么做**
- 文件：`app/gateway/routers/input_polish.py`
- API：`POST /api/input-polish`（需要 `runs:create` 权限）
- Request：`{ text: str, locale?: str, thread_id?: str }`
- Response：`{ rewritten_text: str, changed: bool }`
- 实现：`run_oneshot_llm()` 单次调用；系统 prompt 要求"优化指令清晰度，保留用户意图、实体、斜杠命令前缀，180 词内"；去除 `<think>` 标签和 Markdown 代码块

**我们需要做什么**
1. 后端：`POST /api/input-polish` 路由（platform-api）
2. 后端：实现/复用 `run_oneshot_llm()` 工具函数
3. 前端：输入框增加润色按钮（✨），loading 状态，撤销支持
4. 按钮显示条件：`input.length > 20 && features.input_polish.enabled`

**配置**
```yaml
input_polish:
  enabled: true
  model_name: gpt-4o-mini
  max_input_chars: 4000
```

---

### F12 — AI 跟进建议（Suggestions）

**是什么**：对话完成后，AI 自动生成 3 条可能的跟进问题，以按钮形式展示。点击后填入输入框。

**DeerFlow 怎么做**
- 文件：`app/gateway/routers/suggestions.py`
- API：`POST /api/suggestions`
- Request：`{ messages: [{role, content}], n: int = 3, model_name?: str }`
- Response：`{ suggestions: [str] }`
- 实现：将最近 N 条消息格式化，`run_oneshot_llm()` 生成 JSON 数组格式建议列表，解析时 strip `<think>` 块和代码块
- 配置查询：`GET /api/suggestions/config` → `{enabled, max_suggestions}`

**我们需要做什么**
1. 后端：`POST /api/suggestions` 路由
2. 后端：`GET /api/suggestions/config` 路由（返回配置）
3. 前端：Agent 完成后请求建议，展示 3 个 Chip 按钮
4. 前端：点击 Chip → 填入输入框（不自动发送）

---

### F13 — 语音输入（Voice Input）

**是什么**：麦克风按钮语音识别，结果自动填入输入框。纯前端，无需后端。

**DeerFlow 怎么做**
- 前端：`frontend/src/core/voice-input/speech-recognition.ts`
- 封装浏览器原生 `SpeechRecognition` / `webkitSpeechRecognition`
- 错误分类：`cancelled | microphone_unavailable | permission_denied | unsupported_language | network | no_speech | unknown`
- 连续模式 + 实时中间结果展示
- 不支持时隐藏按钮（能力检测：`'SpeechRecognition' in window`）

**我们需要做什么**（纯前端，1 天）
1. `useVoiceInput.ts` composable
2. 语言跟随 i18n locale
3. 识别结果 append 到输入框 modelValue
4. 输入框旁增加麦克风图标按钮

---

### F14 — CSRF 防护

**是什么**：对 POST/PUT/DELETE 请求校验 `X-CSRF-Token` 请求头，防止跨站请求伪造。

**DeerFlow 怎么做**
- 文件：`app/gateway/csrf_middleware.py`
- 双重 Cookie 验证模式：Token 基于 session cookie 生成，请求头和 Cookie 双向校验

**我们需要做什么**
1. platform-api FastAPI 应用中加入 CSRF middleware
2. 前端：所有变更请求携带 CSRF Token（从 cookie 读，放 header）
3. 确认 CORS 配置是否已充分保护

---

### F15 — MCP 工具缓存热重置

**是什么**：修改 MCP Server 配置后，无需重启服务，调用 API 立即使缓存失效，下次使用时重新加载工具列表。

**DeerFlow 怎么做**
- API：`POST /api/mcp/cache/reset`
- 实现：清空内存中的 MCP client 连接池和工具描述缓存

**我们需要做什么**（很小的改动，半天）
1. runtime-service 增加 `POST /api/mcp/cache/reset` 接口
2. 实现 MCP client 连接池失效机制（关闭现有连接，下次按需重建）

---

### F16 — 飞书（Lark）集成

**是什么**：通过飞书 WebSocket 长连接接收消息，Agent 回复以卡片形式流式更新（同一张卡片原地 patch，不发新消息）。

**DeerFlow 怎么做**
- 文件：`app/channels/feishu.py`、`feishu_run_policy.py`
- 架构：`FeishuChannel` → `MessageBus` → `ChannelService` → `run_policy`（查找/创建 Thread → 执行 Agent）
- 关键细节：
  - **WebSocket 长连接**（无需公网 IP）
  - **0.75s 批量窗口**：同一话题连续消息合并，防止多次触发
  - **卡片原地 patch**：每次更新调 `patch_message`，不发新消息
  - 附件下载：最大 20MB，暂存到线程上传目录
  - 串行化：同一 Thread 的后续消息排队，等上一条执行完再处理

**我们需要做什么**
1. 注册飞书应用（App ID/Secret）
2. 实现 WebSocket 连接客户端（`feishu_websocket`）
3. 实现消息接收处理 + Thread 映射（`openID + chatID` → platform thread_id）
4. 实现飞书卡片 JSON 构建 + `patch_message` 流式更新
5. 0.75s 批量窗口合并（`asyncio.sleep(0.75)` 防抖）
6. 获取 delegation token 向 platform-api 鉴权

**配置**
```yaml
channels:
  feishu:
    enabled: true
    app_id: $FEISHU_APP_ID
    app_secret: $FEISHU_APP_SECRET
```

---

### F17 — 知识库（RAG）

**是什么**：项目级文档库，管理员预置文档，Agent 在回答时可检索相关内容（RAG），减少幻觉。

**DeerFlow 怎么做**
- 文件：`app/gateway/routers/knowledge.py`、`deerflow/knowledge_scope.py`
- 工具：`search_knowledge(query)` → 返回 `[(content, source_url, score)]`
- 存储：文档向量化 + 向量数据库（按项目 namespace 隔离）
- 支持格式：PDF/Markdown/URL（通过 markitdown 转换）

**我们需要做什么**（较大功能，约 2-3 周）
1. 选定向量数据库（推荐 PgVector 扩展 PostgreSQL，与现有 PG 共用）
2. 实现文档上传 → 切片 → Embedding → 存储 pipeline
3. 实现 `search_knowledge` 工具（向量相似度检索）
4. 知识库 CRUD API
5. 项目级 namespace 隔离
6. 前端：项目设置 → 知识库 tab

---

## 四、middleware 架构前置依赖

**F01-F06需逐项核对middleware能力；F07已复用HTTP/metadata链路，不依赖新增middleware。实施中间件类功能前确认以下问题：**

### GraphHarbor middleware 支持情况检查

DeerFlow 使用的 middleware 接口定义在 `langchain.agents.middleware` 包：

```python
class AgentMiddleware(ABC):
    # 生命周期钩子
    def before_agent(self, state: AgentState, runtime: Runtime) -> dict | None: ...
    def after_agent(self, state: AgentState, runtime: Runtime) -> dict | None: ...
    def before_model(self, state: AgentState, runtime: Runtime) -> dict | None: ...
    def after_model(self, state: AgentState, runtime: Runtime) -> dict | None: ...

    # 调用包装（拦截器模式）
    def wrap_model_call(self, request: ModelRequest, handler: Callable) -> ModelCallResult: ...
    def wrap_tool_call(self, request: ToolCallRequest, handler: Callable) -> ToolCallResult: ...

    # 异步版本（aafter_model, awrap_model_call 等）
```

**对接方案**：
- **方案 A**：如果 GraphHarbor 新版本原生支持 `AgentMiddleware` 接口 → 升级版本，直接注册
- **方案 B**：在 runtime-service graph 编译阶段，用自定义包装注入中间件链 → 约 3 天工作量

### 中间件执行顺序（重要！顺序错误会有 Bug）

```
LLMErrorHandlingMiddleware      ← 最外层，捕获所有 LLM 错误
  └── TokenBudgetMiddleware
        └── LoopDetectionMiddleware
              └── SummarizationMiddleware
                    └── TodoMiddleware
                          └── TitleMiddleware
                                └── PiiRedactionMiddleware  ← 最内层，贴近 model

工具调用链:
ToolErrorHandlingMiddleware
  └── ToolOutputBudgetMiddleware
        └── ArtifactCaptureMiddleware
              └── SkillToolPolicyMiddleware
```

### 跨中间件依赖关系

```
SummarizationMiddleware → 调用 PiiRedactionMiddleware.redact_text()
TitleMiddleware         → 调用 PiiRedactionMiddleware.redact_texts()
SummarizationMiddleware → 读取 TodoMiddleware.TODO_REMINDER_MESSAGE_NAME（压缩时排除提醒消息）
TokenBudgetMiddleware   → 调用 clone_ai_message_with_tool_calls()
LoopDetectionMiddleware → 调用 clone_ai_message_with_tool_calls()
MemoryMiddleware        ← SummarizationMiddleware.before_summarization hooks（压缩前提取记忆）
```

---

## 五、关键工具函数

这些函数在多个中间件中复用，应作为共享工具提前实现：

| 函数 | 用途 | 所在位置（DeerFlow） |
|---|---|---|
| `clone_ai_message_with_tool_calls(msg, tool_calls, content)` | 克隆 AIMessage 并替换 tool_calls（处理所有 provider 表面） | `agents/middlewares/message_utils.py` |
| `redact_text(text, pii_config)` | 对单段文本做 PII 脱敏 | `agents/middlewares/pii_redaction_middleware.py` |
| `run_oneshot_llm(messages, config)` | 单次 LLM 调用（不走 Agent 流程） | `deerflow/utils/oneshot_llm.py` |
| `BoundedDict` | 有容量上限的字典（防内存泄漏） | `agents/middlewares/_bounded_dict.py` |

---

## 六、前端最小工作量路线

按工作量从小到大（可先做不依赖后端 middleware 架构的功能）：

| 功能 | 工作量 | 类型 |
|---|---|---|
| F13 语音输入 | 1 天 | 纯前端 |
| F07 自动标题（前端联动部分） | 约 1 天，另需联合验证 | 等后端/CAS 门槛；同事按 [交接](../projects/20261009-agent-thread-auto-title/frontend-handoff.md) 实施 |
| F11 输入润色（前端部分） | 1 天 | 前端为主 |
| F12 AI 建议（前端部分） | 1 天 | 前端为主 |

---

## 七、优先级速查表

| 功能 | 优先级 | 工作量 | 前置依赖 |
|---|---|---|---|
| F07 自动对话标题 | **P2已批准，非前端完成** | 前端与正式CAS发布/接入待完成 | 精确授权/受管模型/metadata CAS已有证据，见[实施](../projects/20261009-agent-thread-auto-title/README.md) |
| F14 CSRF 防护 | **P0** | 小（1天） | 无 |
| F01 Token 预算 | **P0** | 中（3天） | middleware 架构 |
| F02 循环检测 | **P0** | 中（3天） | middleware 架构 |
| F10 文件上传转换 | **P0** | 中（3天） | markitdown |
| F13 语音输入 | **P1** | 小（1天） | 纯前端 |
| F11 输入润色 | **P1** | 小（2天） | oneshot LLM |
| F12 AI 建议 | **P1** | 小（2天） | oneshot LLM |
| F15 MCP 缓存重置 | **P1** | 小（半天） | 无 |
| F06 Todo 中间件 | **P1** | 中（3天） | middleware 架构 |
| F03 上下文压缩 | **P1** | 大（5天） | middleware 架构 + tiktoken |
| F04 工具输出预算 | **P1** | 中（3天） | middleware 架构 |
| F08 网页搜索 | **P1** | 小（1天） | Tavily API Key |
| F09 网页抓取 | **P1** | 小（1天） | 无（Jina 免费） |
| F05 PII 脱敏 | **P2** | 中（3天） | middleware 架构 |
| F16 飞书集成 | **P2** | 大（7天） | 飞书应用审核 |
| F17 知识库 | **P3** | 大（2-3周） | 向量数据库 |

---

## 八、参考链接

- DeerFlow 源码：[本机参考 checkout](../../../research/deer-flow/)
- 中间件体系入口：`backend/packages/harness/deerflow/agents/middlewares/`
- Gateway API 路由：`backend/app/gateway/routers/`
- 前端核心模块：`frontend/src/core/`
- IM 渠道：`backend/app/channels/`
- 技能系统：`backend/packages/harness/deerflow/skills/`
