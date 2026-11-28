# 08-02 并发执行引擎、中文动态多轮仿真与白盒取证管线

> **三承三启导航**
> - **承前**：`eval-runner` Worker 从 PostgreSQL `eval_runs` 认领任务，并已通过 `platform-api` 内部桥完成模型解析和项目权限校验。
> - **居中**：本篇深潜 [concurrent_runner.py](../../apps/eval-runner/src/eval_runner/engine/concurrent_runner.py)、[worker.py](../../apps/eval-runner/src/eval_runner/worker.py)、[simulation.py](../../apps/eval-runner/src/eval_runner/engine/simulation.py)、[sse_probe.py](../../apps/eval-runner/src/eval_runner/targets/sse_probe.py) 与 `evidence/` 三模块如何实现 1~5 并发调度、流式 TTFT 实测、中文动态博弈、三类中断自动协商及全量白盒取证。
> - **启后**：固化好的 `Evidence` 对象与四段耗时/Token 账单将交由 [03-metrics-gates-and-usage-guide.md](03-metrics-gates-and-usage-guide.md) 执行 L1/L2 裁决与门禁判定。

---

## 一、 并发调度池与故障隔离（[concurrent_runner.py](../../apps/eval-runner/src/eval_runner/engine/concurrent_runner.py)）

### 1.1 双信号量隔离设计
- **执行并发控制**：`ThreadPoolExecutor(max_workers=concurrency)`，`concurrency` 严格限制在 **`1 ~ 5`**（默认 `3`），避免单机并发打爆被测 Agent 沙箱和模型限流。
- **裁判限流隔离**：内部另设独立的 `self.judge_semaphore = threading.Semaphore(max_judge_concurrency)`，保证即使执行阶段放开 5 并发，L2 DeepEval 裁判打分也能平滑错峰请求模型网关。
- **单题检查点落盘（Checkpoint Isolation）**：每道题一旦执行和打分完成，立即通过 `on_checkpoint` 回调把单题结果与 `evidence.json` 落盘并更新 PostgreSQL `eval_run_cases`；支持**暂停（`paused`）**、**断点续跑**与**仅重跑失败题**。

### 1.2 四段精密耗时拆解
`ConcurrentEvalRunner` 为每道题记录四段互不重叠的毫秒级耗时：
```text
total_ms = agent_duration_ms + judge_ms
  ├── agent_duration_ms = ttft_ms + generation_ms
  │     ├── ttft_ms        : SSE 连接建立到首个有效助手机器人文本 chunk 到达时间
  │     └── generation_ms  : 首字到达后，模型续吐、工具执行与多轮交互的总耗时
  └── judge_ms             : L2 DeepEval 裁判思考与打分耗时（受 judge_semaphore 计时）
```

---

## 二、 中文动态多轮仿真与中断协商（[simulation.py](../../apps/eval-runner/src/eval_runner/engine/simulation.py)）

### 2.1 完整主循环与中断协商时序

```mermaid
sequenceDiagram
    autonumber
    participant W as worker.py (_execute)
    participant Sim as DynamicSimulationSession
    participant Probe as sse_probe.py
    participant API as platform-api Internal Bridge
    participant RT as runtime-service

    W->>API: thread_setup (上传 case.fixture)
    API-->>W: thread_id, fixture_paths, initial_artifacts
    loop turn_idx in range(max_turns)
        opt pending_fixtures 非空 (上轮决定触发延迟夹具)
            W->>API: thread_setup (上传 pending_fixtures)
        end
        W->>API: execute_turn(content=resolved_prompt)
        API->>RT: stream_thread_run
        RT-->>Probe: SSE frames (values / updates / messages)
        Probe-->>W: terminal_status, final_text, ttft_ms, interrupts
        W->>W: _sync_interrupts_from_state() (状态兜底校验中断)
        while terminal_status == "interrupted" and interrupt_loops < 6
            W->>Sim: resolve_interrupt(interrupts, turn_idx)
            alt 含 action_requests
                Sim-->>W: _handle_tool_approval() -> approve / reject
            else kind == "agent_plan_review"
                Sim-->>W: _handle_plan_review() -> approve / request_changes
            else 其他 (request_information)
                Sim-->>W: _handle_clarification() -> 7类字段强校验填表
            end
            W->>API: execute_turn(command={"resume": resumes})
            API->>RT: input.respond + join_thread_run_stream
            RT-->>Probe: 续跑 SSE 流
        end
        W->>Sim: decide_next_turn(transcript_history)
        Sim-->>W: action (continue/stop), next_message, upload_fixture_ids
    end
```

### 2.2 核心高保真逻辑剖析

1. **`delayed_fixtures`（延迟夹具）是由 LLM 动态判断触发的**：
   - 很多人误以为 `delayed_fixtures` 是写死关键词正则匹配，实际上在 `decide_next_turn` 中，代码通过 `_fixtures_block()` 把每份夹具的 `id`、自然语言 `condition`、文件名与 `already_uploaded` 标记塞给扮演模拟用户的 LLM。
   - 当模拟用户模型认为对话满足 `condition` 时，在 `UserTurnDecision.upload_fixture_ids` 返回对应 `id`；随后 `self.uploaded_fixture_ids` 幂等去重，把文件放进 `pending_fixtures` 并在下一轮请求前调用 `thread_setup` 真正传进沙箱，同时把 `message_hint` 拼入下一句发言。

2. **三类 `__interrupt__` 中断自动协商（`resolve_interrupt`）**：
   - **澄清表单（`_handle_clarification`）**：先检查 `interrupt_strategy.get("clarification_mode") == "reject"`（用于测试拒答降级）；正常情况下将 `persona`、`user_mode`（`cooperative` / `skeptical_challenger` / `ambiguous_changer` / `terse` / `impatient_reversal`）、`hidden_facts` 与表单 `fields` 喂给模型生成 `ClarificationAnswer`，再经 **`normalize_clarification_values`** 针对 `text`/`textarea`/`number`/`checkbox`/`date`/`select`/`multi_select` 7 类字段做强类型与选项合法性校验，最后拼装 `{"schema_version": 1, "status": "answered", "values": values}` 续跑。
   - **计划审阅（`_handle_plan_review`）**：当 `interrupt_strategy.plan_review_policy == "critique_then_approve"` 时，`worker.py` 在发起会话前会自动给 Agent 注入 `context_overrides={"plan_mode": True}`；收到计划后，模型依据 `hidden_facts` 核对遗漏并打回 `request_changes`（附具体中文 `feedback`），达到 `max_plan_rejections`（默认 `1`）上限后强制 `approve`。
   - **工具审批（`_handle_tool_approval`）**：支持三种 `tool_approval_policy`：
     - `allow_whitelisted`（默认）：只放行 `expectations.approval_allow` 或由 `_default_write_whitelist()` 从 `expectations.artifacts` 自动推导的目标写入路径，其余越权写入一律拒绝；
     - `approve`：全部放行；
     - `reject`：一律拦截并将载荷记入 `self.rejected_interrupts`（供后续取证标为 `blocked`）。

---

## 三、 白盒取证管线与真跑排障复盘

对话结束后，`worker.py` 调用 `exec_client.thread_evidence(...)` 拉回线程终态与工作区快照，经三个专门模块提炼结构化 `Evidence`：

1. **工具调用链取证（[tool_evidence.py](../../apps/eval-runner/src/eval_runner/evidence/tool_evidence.py)）**：
   - 遍历 `state.messages`：从 `AIMessage.tool_calls`（或 `content` 中的 `tool_call` 块）收集每条 `requested` 调用；从 `ToolMessage` 按 `tool_call_id` 匹配回填为 `executed` 或 `error` 并截断保留前 500 字符 `output_preview`。
   - **拒批原位回填**：遍历 `sim_session.rejected_interrupts` 中的 `action_requests`，将对应的 `requested` 事件原位更新为 `status="blocked"` 并计入 `settled_ids`，保证 `tool_execution_complete` 准确反映所有工具均有确定结局。
2. **检索上下文与物理工件提取（[context_and_artifacts.py](../../apps/eval-runner/src/eval_runner/evidence/context_and_artifacts.py)）**：
   - 识别知识库检索类工具输出，提取 `retrieved_contexts` 并精确区分 `contexts_state` 为 `"recorded"`（确有内容）、`"recorded_empty"`（调了检索但返回空）或 `"not_recorded"`（未调用检索）。
   - 记录 `initial_artifacts` 与终态 `artifacts`，以及工作区读取错误 `artifact_read_errors`。
3. **死循环信号恢复（[runtime_signals.py](../../apps/eval-runner/src/eval_runner/evidence/runtime_signals.py)）**：
   - 解析诊断流中的 `runtime.loop.observation` 等信号，输出 `loop_signals` 计数与 `loop_observed` 布尔值，向上聚合整批死循环率。

### 真实全栈压测中发现并根治的 5 个典型隐患
1. **模型流式返回空 `tool_call.id` 诱发 30 步死循环**：`qwen-plus` 在部分流式工具调用中返回 `id=""`，导致 `runtime-service` 的 `sanitize_tool_call_messages` 找不到对应 ID 而静默剥离 `ToolMessage`，模型失忆后反复重读文件直到报错。已在 [runtime_config.py](../../apps/runtime-service/src/runtime_service/middlewares/runtime_config.py) 的 `repair_model_tool_calls` 为缺失 ID 的有效工具调用自动分配合成 ID（`call_<uuid>`）并同步文本块 ID。
2. **SSE `__interrupt__` 通道与结构差异**：真实流中 `__interrupt__` 既可能出现在 `updates` 通道也可能是字典而非列表。`sse_probe.py` 新增 `"updates"` 订阅与 `normalize_interrupts` 标准化函数，并辅以 `_sync_interrupts_from_state()` 查单兜底。
3. **非 `success` 终态被覆盖为 `turn_limit`**：`worker.py` 在检测到 `probe.terminal_status != "success"` 时主动同步 `sim_session.stop_reason` 为实际 `error_category`，防止把运行时故障误报成“多轮轮次耗尽”。
4. **预期产物未显式写白名单被误拦**：`simulation.py` 新增 `_default_write_whitelist()`，默认允许写入 `expectations.artifacts` 中非 `absent` 的目标产物，同时保持 `tool_approval_policy="reject"` 安全拦截题严格生效。
5. **非成功终态下的 TTFT 与空白回答保护**：`sse_probe.py` 跳过空内容帧与心跳帧，确保 `ttft_ms` 精确落在首个有效输出字节。

---

## 四、 假想故障推演：如果第 2 轮工具跑完时 SSE 突然断流怎么办？

假设被测 Agent 正在沙箱里执行耗时 90 秒的数据分析并已成功写入 `summary.csv`，但反向代理在结果返回前触发超时（`stream_timeout`）：
1. **错误做法（会引发重复下单）**：直接重试 `execute_turn`，导致 Agent 再跑一遍写入、产生双倍 Token 与文件脏状态。
2. **本引擎处理机制（[worker.py](../../apps/eval-runner/src/eval_runner/worker.py#L254-L277)）**：
   - 捕获 `probe.error_category == "stream_timeout"` 后，Worker **绝不重投请求**，而是立刻调用 `exec_client.thread_evidence(run_id, thread_id, run_ids=trace_ids)` 查单；
   - 若服务端 `runs` 记录显示该次执行已实际达到 `status == "success"` 且 `state.values.messages` 存在末条 AI 回复，则直接提取该回复、`artifacts` 与完整工具链，把 `probe.terminal_status` 置为 `"success"` 并标记 `checks.stream_recovered = True`，实现无副作用断点自愈；
   - 若服务端也确认未完成，才诚实保留 `error_category = "stream_timeout"` 写入异常分层报表。
