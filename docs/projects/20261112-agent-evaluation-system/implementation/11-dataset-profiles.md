# 多评测集与具名配置实施

实际代码全部位于EvalFlow worktree，业务Agent服务未修改。

详细实现、测试、截图、真实Run、恢复与局限见：
`/Users/lijiaxin/.codex/worktrees/agent-evaluation/mlflow-eval-platform/docs/projects/20261113-evaluation-task-ui/implementation/27-dataset-profiles.md`。

用户确认范围修订：同一项目+graph只有一个Agent，因此采用同一Agent多份具名评测参数配置；不迁移业务身份/权限模型。

进度只看本项目tasks.md的D01–D06；首期T任务的已完成状态不覆盖本扩展。
