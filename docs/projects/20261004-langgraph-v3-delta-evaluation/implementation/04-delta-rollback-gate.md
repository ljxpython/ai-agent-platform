# DeltaChannel 兼容性与回滚门禁实施记录

## 改动时间
2026-10-04

## 相关任务
- Task 3.3：兼容性和回滚门禁

## 改动文件
- `apps/runtime-service/pyproject.toml`
- `apps/runtime-service/uv.lock`
- `apps/runtime-service/tests/test_delta_channel_spike.py`

## 具体改动

### 1. 核心依赖升级至 GraphHarbor 0.13.0.post38
**位置：** `apps/runtime-service/pyproject.toml:12`
**改动：**
- 将 `graphharbor==0.13.0.post37` 升级锁定为 `graphharbor==0.13.0.post38`
- `uv sync` 同步安装锁定 `graphharbor-runtime==0.13.0.post38`
- 回归验证 `tests/test_r0_baseline.py`（14 passed），确认执行底座无破坏性变更。

### 2. DeltaChannel 兼容性与回滚门禁验证
**位置：** `apps/runtime-service/tests/test_delta_channel_spike.py`
**测试内容：**
1. **Worker 重启与断点续跑验证 (`test_delta_channel_worker_restart_and_resume`)**：
   - 模拟 Worker 进程崩溃后被杀，创建全新 Worker 图实例挂载相同 checkpointer；
   - 验证 DeltaChannel 能够从持久化 Checkpoints 完整恢复历史累积状态，后续 invoke 续跑结果精确对齐。
2. **快照扁平化 Dump 导出与标准图回退验证 (`test_delta_channel_rollback_via_snapshot_dump`)**：
   - 针对 DeltaChannel 与普通快照图底层 channel schema 不兼容的特性，演练回滚方案；
   - 提取 Delta 线程的当前扁平状态 `state.values["items"]`（即 dump 快照），并在回退的标准快照图（`FullState`）中初始化新线程继续正常执行；
   - 证明回退迁移具备完整可行性，且两类图严格线程隔离。

## 门禁结论（Adopt / Defer）
- **结论：明确为 `Defer`（不进入生产）**。
- **依据**：真实本地 PostgreSQL 测量结果显示，DeltaChannel 虽体积下降 33.6%，但写入恢复耗时暴增 2.06 倍，且缺乏无损原地回退机制；保持当前生产 `add_messages` 完整快照，后续新场景需使用独立新线程才可考虑灰度。

## 验证
- `uv run pytest -q tests/test_delta_channel_spike.py`：4 passed in 0.42s
- `uv run pytest -q tests/test_r0_baseline.py`：14 passed in 5.22s
