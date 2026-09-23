# GraphHarbor (`0.13.0.post30` $\rightarrow$ `0.13.0.post32`) Worker 并发参数失效与高频流式事件刷盘阻塞排查及修复验证报告

- **创建日期**：2026-09-23
- **影响版本**：`graphharbor == 0.13.0.post30`（含 `langhost` CLI 与 `langgraph_runtime_pg` 运行时组件）
- **修复版本**：`graphharbor == 0.13.0.post32` / `graphharbor-runtime == 0.13.0.post32`（✅ 已升级并实测验证通过）
- **问题级别**：
  - **Issue 1 (P0，已由 `0.13.0.post32` 修复)**：`graphharbor worker --n-jobs-per-worker N` 并发参数完全未生效，`ProductionWorker` 硬编码单协程串行消费，导致多会话/子智能体全局串行排队。
  - **Issue 2 (P1，已由 `0.13.0.post32` 修复)**：`ProductionWorker._publish_event()` 对每个流式 Token（`block-delta`）逐条开启独立 PostgreSQL 事务写库，导致长文本输出时数据库事件刷盘延迟高达 LLM 真实生成耗时的 **4.6 倍**（66 秒吐完 2.3 万字，却阻塞 Worker 达 307 秒）。

---

## Issue 1 (P0)：`graphharbor worker --n-jobs-per-worker N` 并发参数未生效

### 1. 现象与数据库实测证据

在启动命令中显式指定 `--n-jobs-per-worker 4`：

```bash
uv run --frozen graphharbor worker --config langgraph.json --n-jobs-per-worker 4
```

随后在两个浏览器窗口中同时发起两条独立会话（`thread_id` 不同），相差仅 `1.8s` 提交。第二个浏览器窗口完全无流式输出，直到第一个浏览器窗口完整输出结束后才开始输出。

查询 PostgreSQL `runs` 与 `runtime_events` 表的真实时间戳证据如下：

| 会话 | `run_id` | `thread_id` | Run 创建时间 (`created_at`) | **Worker 首帧事件时间 (`first_event`)** | **Run 结束时间 (`last_event`)** | 现象 |
|---|---|---|---|---|---|---|
| **浏览器 1** | `da184204-286c-43e1-a601-df5f1d062e79` | `643b148f-bda2...` | `17:18:15.148` | **`17:18:15.246`**（创建后 `98ms` 立即执行） | **`17:18:48.045`** | 正常执行 `32.8s` |
| **浏览器 2** | `f9f45532-ed35-424a-89a6-0f8e35656191` | `e481e585-0f0e...` | `17:18:16.945`（仅晚 `1.8s` 创建） | **`17:18:48.134`**（**恰在浏览器 1 结束后的第 `89ms` 才开始！**） | `17:19:12.010` | **白白排队等待 `31.2s`** |

### 2. 源码级根因定位

在 `graphharbor 0.13.0.post30` 中，`langhost/cli.py` 与 `langgraph_runtime_pg/production_worker.py` 之间存在参数断链：

1. **CLI 层（`langhost/cli.py:165-204`）**：
   - `worker_command` 接收了 `n_jobs_per_worker: int` 参数；
   - 调用 `_prepare_serve_env(env_file, database_uri, redis_uri, n_jobs_per_worker)`，将并发数写入环境变量 `os.environ["N_JOBS_PER_WORKER"] = str(n_jobs_per_worker)`；
   - 随后在默认生产模式下调用：
     ```python
     async def _run() -> None:
         from langgraph_runtime_pg.production_worker import run_worker

         await run_worker(config_path)
     ```
     既未将 `n_jobs_per_worker` 作为参数传给 `run_worker`，`run_worker` 内部也未读取 `os.environ["N_JOBS_PER_WORKER"]`。

2. **执行器层（`langgraph_runtime_pg/production_worker.py:426-481`）**：
   - `run_worker(config_path)` 仅实例化了 **1 个 `ProductionWorker` 对象**：
     ```python
     async def run_worker(config_path: Path) -> None:
         ...
         await start_pool()
         worker = ProductionWorker(registry)
         registry.attach_checkpointer(get_checkpointer())
         ...
         await worker.run_forever()
     ```
   - 而在 `ProductionWorker.run_forever()` 中，仅运行了 **单个 `while` 串行循环**：
     ```python
     async def run_forever(self) -> None:
         reaper = asyncio.create_task(self._reaper_loop(), name=f"reaper-{self.owner}")
         while not self.stop_event.is_set():
             did_work = await self.run_once()
             if not did_work:
                 await wait_for_queue_wake(timeout=0.5)
     ```
   - 因为 `await self.run_once()` 内部会调用 `await invoke_graph(...)` 并一直阻塞等待当前 Run 的完整 Graph 推理结束才返回 `True`，导致单个 `ProductionWorker` 实例在任何时刻都只能执行 **1 个 Run**。
   - 此外，`ProductionWorker` 持有的 `self.repository = RunRepository(...)` 在实例属性 `self.repository.last_transition_events` 上缓存了最近一次状态变更事件，因此不能在同一个 `ProductionWorker` 实例上直接并发调用 `self.run_once()`，而应当按并发槽位实例化独立的 `ProductionWorker(registry, owner=f"{base_owner}:{slot_idx}")`。

### 3. `graphharbor` 修复方案建议（`production_worker.py` & `cli.py`）

底层基础设施（`database.start_pool` 的 `pool_size=20`、`checkpoint.setup_checkpointer` 的 `AsyncConnectionPool(max_size=10)`、以及 `RunRepository.claim_next` 的 `FOR UPDATE SKIP LOCKED`）均已支持并发。只需在 `langgraph_runtime_pg/production_worker.py` 中補齐多槽位协程池调度：

1. **在 `ProductionWorker.__init__` 中增加 `enable_reaper: bool = True`**：
   - 同一进程内启动 $N$ 个槽位时，仅 `slot-0` 启动 `_reaper_loop()` 定时回收过期租约，其余 `slot-1 .. N-1` 仅运行任务认领与执行循环，避免重复执行 `reap_once()`。
2. **在 `run_worker(config_path, *, n_jobs_per_worker: int | None = None)` 中读取 `n_jobs_per_worker` 或 `os.environ.get("N_JOBS_PER_WORKER")`**：
   - 创建 `concurrency = max(n_jobs, 1)` 个拥有独立 `owner`（如 `f"{hostname}:{pid}:slot-{idx}"`）和独立 `RunRepository` 实例的 `ProductionWorker`；
   - 使用 `await asyncio.gather(*(w.run_forever() for w in workers))` 在同一 `asyncio` 事件循环内并发消费队列；
   - 收到 `SIGINT` / `SIGTERM` 时统一置位所有槽位的 `stop_event`。
3. **在 `langhost/cli.py` 的 `worker_command` 中透传参数**：
   - `await run_worker(config_path, n_jobs_per_worker=n_jobs_per_worker)`。

---

## Issue 2 (P1)：`ProductionWorker._publish_event()` 逐 Token 独立事务写库导致长文生成阻塞 5 分钟

### 1. 现象与数据库实测证据

在 `run_id = 077db02e-aa4e-4b08-a06d-2f9db75dbce9`（`thread_id = 331fecda-62b6-472a-8789-2d7feabada99`）的 `step=71` 中，大模型通过 `tool_call_chunks` 流式构造 `write_file` 工具的 `content` 参数（共 `23,140` 字符，`13,871` output tokens，产生 **`11,208` 条 `block-delta` 流式事件**）。

对比 `runtime_events` 表中事件生成时间戳（`payload->'data'->>'timestamp'`）与数据库写入时间戳（`runtime_events.created_at`）：

| 事件序号 (`seq`) | 事件类型 | **Python 内存真实生成时间 (`payload_ts`)** | **PostgreSQL 落盘时间 (`db_created_at`)** | 耗时对比 |
|---|---|---|---|---|
| `seq = 4` | `step=71` 任务开始 (`task`) | `16:22:12.562` | `16:22:12.836` | 延迟 `0.27s` |
| `seq = 5 .. 11211` | **`11,208` 条 `block-delta` 事件** | `16:22:12.600` $\rightarrow$ `16:23:18.560` | `16:22:12.850` $\rightarrow$ `16:27:20.510` | 逐条写库积压 |
| `seq = 11212` | `step=71` 任务结束 (`task_result`) | **`16:23:18.568`（LLM 仅用 `66.0s` 吐完！）** | **`16:27:20.523`（DB 刷盘耗费 `307.7s` / `5分08秒`！）** | **写库比模型生成慢了 `241.7s`（4.6 倍）！** |

### 2. 源码级根因定位

在 `langgraph_runtime_pg/production_worker.py:129-151` 中，每当 `invoke_graph` 的 `astream_events(version="v3")` 吐出 **1 个 token 的 `block-delta`**，就会 `await on_event(...)` 调用一次 `ProductionWorker._publish_event()`：

```python
async def _publish_event(
    self,
    run_id: UUID,
    thread_id: UUID | None,
    event: dict[str, Any],
    *,
    trace_context: dict[str, Any] | None = None,
) -> None:
    ...
    async with connect() as conn:
        ...
        durable = await self.repository.record_event(conn.session, **kwargs)
    await self._fanout_durable_event(durable)
```

这导致：
1. **每个 Token 打开并提交一次独立的 PostgreSQL 事务（`async with connect() as conn:` + `SELECT/INSERT runtime_events` + `COMMIT`）**，随后再串行执行 2 次 Redis Stream 写入（`manager.put` + `manager.put_thread`）。
2. 即使单次「PG 事务提交 + 2 次 Redis 写入」仅耗时 `~27ms`（吞吐上限约 `36.5 events/s`），当大模型以 `210 tokens/s` 高速输出 `11,208` 个 chunk 时，`on_event` 的 `await` 反压会直接把 `astream_events` 消费循环卡在数据库 I/O 上长达 **`11,208 × 27ms ≈ 303 秒（5 分钟）`**，在此期间下一步工具节点（`step=75` `write_file`）完全无法执行。

### 3. `graphharbor` 优化方案建议

在 `ProductionWorker`（或 `RunRepository`）中对高频非终态流式增量事件（`topic == "block-delta"` / `message-chunk`）做 **微批聚合或异步缓冲写库**：
- **方案 A（流式 Delta 聚合 / 节流合并）**：在 `invoke_graph` 或 `_publish_event` 中，对同一 `block_id` / `tool_call_id` 在 `30ms ~ 50ms` 窗口内的连续 `block-delta` 进行文本/参数增量拼接合并后再写入 `runtime_events` 与 Redis。仅 50ms 窗口即可将 `11,208` 条事件压缩至 `~1,300` 条以内，减少 **90%** 的 PostgreSQL 事务数与 Redis 广播风暴，同时前端视觉完全保持丝滑流式（20 FPS）。
- **方案 B（批量写库队列）**：Redis Stream 实时推送保持低延迟，而 PostgreSQL `runtime_events` 持久化采用按 `run_id` 的批量 `INSERT`（每 `50ms` 或每 `50` 条事件合并为单个事务批量写入，遇到 `task_result` / `checkpoint` / `lifecycle` 终态事件时立即 flush 屏障对齐）。
