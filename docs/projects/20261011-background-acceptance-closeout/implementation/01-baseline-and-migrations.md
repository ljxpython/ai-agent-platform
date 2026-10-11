# 合并基线与迁移汇合

- 日期：2026-10-11；关联 K01/K02。
- 用户已批准实施；99f7 最终增量提交 `d412d54c` 已经由 `74ac8c83` 合并，当前集成基线为 `2b94585b`（含后续隐私保护）。主工作区干净，只读核验。
- 实施 Worktree：`~/.codex/worktrees/b01-closeout/ai-agent-platform`，detached HEAD `2b94585b`，未提交/推送。
- 规划从 f5a8 复制；没有复制旧安装或私有状态。独立环境 `wt_43727db9404e`，Web/API/Runtime/Redis 端口分别 29286/23818/24548/28816。
- `scripts/local-stack.sh init/deps/doctor/migrate` 已执行；正式双包 post45，Runtime SDK 0.4.3、API SDK 0.4.2；两个 editable app 均解析至本 Worktree。
- Runtime lock SHA256 `ae87e773572242b29347d4679a55d6b75b879f120a799a2c31db5243282b86b6`；API lock `bf6649fa696f6c84cceeee03b352929b500d69f3ccd55dcf7273d311d5d545aa`。

## 改动与原因

- `apps/platform-api/migrations/versions/20261011_0008_merge_completion_acceptance.py`：父为 completion/acceptance 两个旧 head，upgrade 无数据操作；downgrade 立即拒绝，避免 SQLite 在另一个分支先删除 completion 后才触发 acceptance 拒绝。
- `apps/runtime-service/src/runtime_service/db/migrations/versions/0004_merge_background_token_budget.py`：父为后台/Token 两个旧 head，upgrade/downgrade 无数据操作。
- 两应用现在唯一 head 为 `20261011_0008` / `0004_background_token_budget`；引擎独立 `013_run_acceptance_receipts`。
- Platform 迁移测试扩展至 SQLite/PG × 四个起点并隔离 schema；Runtime 新增五个起点的真实 PG 测试，保存 Usage/Token/Stop/task 原事实；旧 repository 迁移断言指向新 head。

## Phase 证据

- Platform 8 passed，31.30s：`phase-platform-migration.xml`。
- Runtime PG repository+迁移 29 passed、5 Docker 场景未启用而 skipped，197.24s：`phase-runtime.xml`。其中新迁移5项均通过，Docker skipped 后续补验，不计完成。
- 本环境实际迁移到双应用 head 与引擎 013；空库不包含主历史。
- 新增测试首次字符串语法错误已修，格式检查后测试通过；保留验证记录。

原始报告在本 Worktree `.local-stack/verification/`，不含提交的私有配置。
