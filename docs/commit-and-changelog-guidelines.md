# Git Commit & Changelog Guidelines

目标：让**每一次 Git 提交**都能明确回答三件事，并且能稳定聚合为 `docs/CHANGELOG.md`。

- 做了什么（用户可感知的变化）
- 影响什么（范围/模块）
- 如何验证（跑了什么测试）

本仓库采用方案 **B**：

- **每次提交**必须写清楚变更（通过 commit message 的 `Log/Test`）
- `docs/CHANGELOG.md` **按发布/周期**从提交记录聚合生成（不要求每个 commit 都改同一个 changelog 文件）

---

## 1. Commit Message 格式（强制）

遵循 Conventional Commits，并要求正文包含 `Log` 和 `Test`。

```text
type(scope)!: summary

Log:
- ...
- ...

Test:
- ...

Refs:
- ... (optional)
```

说明：

- `type(scope)!: summary` 必填
- `!` 仅在 **Breaking Change** 时使用
- `Log:` 必填：1-5 条，写用户可感知的变化（不要写“重构/调整结构”这种内部细节）
- `Test:` 必填：写本次验证手段（例如 `pnpm lint (platform-web, runtime-web)`）
- `Refs:` 可选：关联 threadId、issue、需求文档等

---

## 2. type 约定（建议固定）

- `feat`：新增能力（Added）
- `fix`：修复问题（Fixed）
- `perf`：性能/体验改进（Changed/Performance）
- `refactor`：仅内部重构（默认不进入 changelog，除非影响行为）
- `docs`：文档更新
- `test`：测试相关
- `chore`：杂项（依赖/脚手架/格式化等）
- `build`：构建相关
- `ci`：CI 相关
- `revert`：回滚

> 规则：对外日志只收敛 `feat/fix/perf`，其他类型默认不进入对外 changelog。

---

## 3. scope 约定（建议枚举）

优先使用以下 scope（按改动归属选择一个主 scope）：

- 应用/服务：`platform-web` `platform-web` `runtime-web` `platform-api` `runtime-service` `interaction-data-service`
- UI 领域：`ui` `thread` `tool-calls` `markdown` `tasks` `history`
- 文档：`docs`
- 其他：`deps` `infra`

当一次提交横跨多个模块时：

- 优先选“主要影响面”的 scope（例如 UI 变更较大就用 `ui`）
- 其余细节写进 `Log:` 的条目里

---

## 4. Log 编写标准（强制）

`Log:` 下面每条都必须满足：

- 面向用户/产品结果：能从 UI 或接口行为上直接观察
- 一条一事：不要把多个变化揉成一条
- 避免实现细节：不写“重构组件/调整函数”，要写“默认折叠工具卡片”等

示例（参考你们这次前端优化的表达方式）：

```text
feat(ui): improve tool and sub-agent cards rendering

Log:
- Sub-agent (task/general-purpose) Output 按 Markdown 渲染，支持标题/列表/代码块
- 工具卡片支持默认折叠（历史回放场景），运行中默认展开便于观察
- 修复折叠态卡片居中问题，统一左对齐布局
- 取消工具卡片内部限高滚动，展开后完整展示内容

Test:
- pnpm lint (platform-web, runtime-web)

Refs:
- threadId=e2a2f86b-eeb3-4b54-a8fd-1bab83da1e87
```

---

## 5. Test 编写标准（强制）

`Test:` 至少写一种验证方式：

- `pnpm lint (platform-web, runtime-web)`
- `pnpm build (platform-web)`
- 手动验证：写清楚页面/路径/关键操作

如果确实无法验证，也必须显式写出来（避免默默跳过）：

```text
Test:
- not-run (reason: only docs change)
```

---

## 6. docs/CHANGELOG.md 规范（Keep a Changelog）

`docs/CHANGELOG.md` 采用 Keep a Changelog 的分组方式：

- `Added`：对应 `feat`
- `Fixed`：对应 `fix`
- `Changed`：对应 `perf`（以及必要的行为变更）

### 什么时候更新 CHANGELOG（方案 B）

- 按发布/周期（例如每周、每次打 tag）由发布者/Owner 聚合更新
- 聚合来源：`feat/fix/perf` 的 commit message 中 `Log:` 条目

### 聚合范围

- 从上一个 tag（例如 `v0.1.0`）到当前 tag 的提交区间
- 若暂未打 tag，可先按日期区间聚合（后续补 tag 再规范化）

---

## 7. 执行建议（团队约束）

建议把以下规则作为 code review 的 gate：

- `feat/fix/perf` 必须包含 `Log:` 和 `Test:`
- scope 必须出现且合理
- `Log:` 只写用户可感知变化
