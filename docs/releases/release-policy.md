# 仓库发版规范

## 1. 目标

这份文档用于固定当前仓库的正式 `release` 规则，避免每次发版时再临时讨论：

- 发版对象是谁
- 从哪条分支发
- 版本号怎么定
- Git tag 和 GitHub Release 怎么做
- 发版前后要验证什么

当前仓库的正式口径已经收敛为：

- 发版对象：整个仓库
- 发版基线分支：`main`
- 当前版本口径：`agent 工作台可演示版`

## 2. 发版范围

每次 `release` 都代表整个仓库的一个稳定快照，而不是单个 app 的私有版本。

这意味着：

- `release` 标签打在仓库级别
- GitHub Release 也以仓库为单位创建
- 某次 release 中可以突出某个主应用，例如 `apps/platform-web-vue`
- 但版本本身不单独归属某个子目录

## 3. 正式发版分支

所有正式 release 只能从 `main` 发出。

禁止做法：

- 从功能分支直接打 tag
- 从本地未合并代码直接创建 GitHub Release
- 先打 tag 再补验收

正确顺序：

1. 功能分支完成开发
2. 合并进 `main`
3. 在 `main` 上完成最终校验
4. 打版本 tag
5. 推送 `main` 和 tag
6. 创建 GitHub Release

## 4. 版本号规则

采用语义化版本：

- `vX.Y.Z`

解释：

- `X`：主版本，存在重大变化或阶段性正式发布
- `Y`：次版本，新增可感知能力或大块功能升级
- `Z`：修订版本，主要用于 bug fix 或小范围优化

当前阶段建议：

- 首个对外可演示版本：`v0.1.0`
- 继续补强能力：`v0.2.0`、`v0.3.0`
- 小修复：`v0.1.1`、`v0.2.1`

在进入稳定商用或正式交付阶段前，不建议急着打 `v1.0.0`。

## 5. Release 标题规则

Git tag 与 GitHub Release 标题分开处理：

- Git tag：只用版本号
  - 例如：`v0.1.0`
- GitHub Release 标题：版本号 + 版本口径
  - 例如：`v0.1.0 - Agent 工作台可演示版`

## 6. 当前版本口径

当前这条迁移主线对外统一口径是：

> `apps/platform-web-vue` 已承接新的前端工作台宿主，当前仓库已经具备 agent 工作台可演示能力，能够完成登录、项目上下文切换、chat/sql-agent/testcase/threads 以及平台基础管理页展示。

注意：

- 这不是“最终正式版”
- 这是一条可以对老板、测试、团队复述清楚的里程碑版本

## 7. 发版前必须满足的条件

至少满足下面这些条件，才能进入打 tag 阶段：

- 目标功能已经合并到 `main`
- `main` 工作树干净
- 关键应用构建通过
- 关键演示链路通过
- 演示账号可登录
- 已知问题已归档
- Release Note 草案已经准备好

最低要求校验：

- `pnpm --dir apps/platform-web-vue lint`
- `pnpm --dir apps/platform-web-vue build`

推荐补充：

- 按 `docs/platform-web-sub2api-migration/16-smoke-test-and-acceptance-checklist.md` 走一遍关键路由烟测

## 8. Tag 规则

Tag 一律使用注释 tag：

```bash
git tag -a v0.1.0 -m "release: v0.1.0"
```

禁止：

- `release-v0.1.0`
- `platform-web-v0.1.0`
- `v0.1`
- 无说明的轻量 tag

## 9. GitHub Release 内容结构

GitHub Release 建议固定为以下结构：

### Summary

- 这版的定位是什么

### Highlights

- 最值得展示的 3 到 5 个点

### Added

- 新增能力

### Changed

- 体验、交互、结构优化

### Fixed

- 修复的问题

### Verification

- 跑了哪些校验

### Known Issues

- 已知问题和暂缓项

## 10. CHANGELOG 规则

仓库的对外变更记录遵循：

- [docs/commit-and-changelog-guidelines.md](/Users/bytedance/PycharmProjects/my_best/AITestLab/docs/commit-and-changelog-guidelines.md)
- [docs/CHANGELOG.md](/Users/bytedance/PycharmProjects/my_best/AITestLab/docs/CHANGELOG.md)

在正式 release 时，需要把当前版本的摘要同步整理进 `docs/CHANGELOG.md`。

建议做法：

- 先写好 GitHub Release 文案
- 再提炼为 `docs/CHANGELOG.md` 中对应版本条目

## 11. 当前仓库的推荐发版节奏

当前阶段建议按“里程碑发版”，不要按“每天一发”这种折腾玩法。

适合触发 release 的时机：

- 完成一个清晰的演示口径
- 完成一个明确的验收节点
- 完成一批对外可展示的主线能力

不适合触发 release 的时机：

- 只是修了几个零碎 UI
- 只是本地分支刚跑通
- 还没进 `main`
- 还没过验收清单

## 12. 当前建议

当前仓库的首个正式 release 建议直接做成：

- 版本号：`v0.1.0`
- 标题：`v0.1.0 - Agent 工作台可演示版`
- 基线分支：`main`
- 核心亮点：`platform-web-vue` 迁移工作台 + agent 演示主线
