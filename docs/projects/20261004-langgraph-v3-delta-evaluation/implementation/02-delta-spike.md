# DeltaChannel 隔离 Spike

## 改动时间

2026-10-04

## 相关任务

- Task 3.1：实现隔离 Delta reducer Spike
- Task 3.2：对比 checkpoint 写入与恢复成本

## 改动文件

- `apps/runtime-service/tests/test_delta_channel_spike.py`
- `apps/runtime-service/scripts/measure_delta_channel.py`
- `apps/runtime-service/scripts/measure_delta_channel_postgres.py`

## 实现

- 使用显式 `StateGraph` 和 `InMemorySaver`，将 append-only 字符串列表分别建模为普通 reducer 与 `DeltaChannel`。
- 测试 reducer 的批处理不变性，并通过多次 invoke 后的状态读取验证 Delta checkpoint 重建。
- 测量脚本对相同 200 轮输入序列统计 checkpoint tuple 的 pickle 字节数和运行时间；脚本不连接生产数据库。
- PostgreSQL 脚本使用本地 `.env` 的 `DATABASE_URI`，创建两个唯一测量线程，统计 `checkpoints`、`checkpoint_blobs`、`checkpoint_writes` 的实际行数和 `pg_column_size`，完成后只删除这两个测量线程。

## 离线结果

执行：`uv run python scripts/measure_delta_channel.py --rounds 200`

```text
full_snapshot_bytes: 1838196
delta_channel_bytes: 581427
byte_ratio: 0.3163
full_run_seconds: 1.0885
delta_run_seconds: 1.3738
final_items: 400
```

离线夹具显示 Delta 序列化体积约为完整快照的 31.6%，但运行时间略高。该结果不能替代真实 PostgreSQL checkpoint 体积、恢复和查询测量。

## 本地 PostgreSQL 结果

执行：`uv run python scripts/measure_delta_channel_postgres.py --rounds 200`

```text
full_total_bytes: 1091325
delta_total_bytes: 724790
byte_ratio: 0.6641
full_run_seconds: 1.8763
delta_run_seconds: 3.8661
```

真实本地 PG 结果显示总存储下降约 33.59%，但写入与恢复夹具耗时约增加 2.06 倍。只读汇总现有业务 checkpoint 表时，最大线程约 270 个 checkpoint、1,023,224 bytes checkpoint JSON、300,425 bytes blob、652,401 bytes writes；该汇总未修改任何业务数据。

## 风险和结论

- 生产 AgentState 未改动，`add_messages` 未替换为 DeltaChannel。
- 已完成本地 PostgreSQL 体积基线；worker 重启和 `delta-channel-dump` 回滚演练仍未执行。
- 在真实 PG 和回滚门禁完成前，DeltaChannel 结论为 Defer。
