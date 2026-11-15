# 新授权批次前端验收与两处接口修复

日期：2026-11-14。关联 Task 1.1、2.1–2.4、3.1–3.3、4.1、4.5；仅 Phase，不是项目 Final。

## 范围与身份

在 `344c/ai-agent-platform` 与同级 `mlflow-eval-platform` Worktree，使用 browser-skill 和用户交还的源标签页继续验收。源 Web/API/Runtime 为 28808/25087/26645，EvalFlow Web/API 为 9138/5011。源用户为 admin，原生评测用户为非管理员 flywheel-reviewer，批次服务所有者为 flywheel-worker。未使用生产资料、未提交或推送代码、未部署生产。

原会话的 held 阻塞已解除。31+16 草稿只发送一次，实际回答47；反馈、授权、原生审核、冻结发布、创建回归、查看结果和源侧撤权均通过页面操作。审核说明明确标记为自动化合成流程验收，不能算独立人工审核或盲测。权限负例除页面外，补充了同一浏览器身份的同源请求；没有提取浏览器凭据。

## 可对账对象

| 对象 | ID / 结果 |
| --- | --- |
| 源会话 | `0275fd48-7b3d-4d2f-916b-026cc5ed63fd` |
| 源授权批次 | `59eb6f44-fbbc-4b72-999f-8120f5501a26`；已撤权 |
| 独立实验 | `4`，`evalflow-grant-59eb6f44-fbbc-4b72-999f-8120f5501a26` |
| 授权候选 Trace | `tr-520c8421bad0b1a85664df0317a99356` |
| 冻结 Dataset | `d-74eeb8f13154490b9e9d6e6cd87256ee`，版本1 |
| 内容 hash | `1dbbf8d7f6f1a700fb3b5ec3ddcceab4be3fb7160b0ef2551e48fd6d8d353ab9` |
| 用例 | `curated.59eb6f44`，Schema v2，dev，审核人由服务端绑定为 flywheel-reviewer |
| 幂等请求 / 任务 | `fcb4f8c2-9df5-4cc2-9fa6-4f57746d3ede` |
| 结果 Run | `65e4199d2a6f44a18621a66a4a397b4b`，归属实验4，passed，1/1题 |

结果页三个确定性断言 `completion`、`answer_contains`、`tool_budget` 均为1，预期47、最大工具调用0。约67秒完成本次任务，未把一题三项断言写成三题。门禁有 `budget_policy_not_configured` 警告，本轮不是预算策略验收。审核和发布后的源反馈页面显示已关联1条原生Trace。

## 前端发现的实际缺陷

### 创建请求超时

`EvalFlow: eval_platform/app.py::task_router.create` 在 async 路由内直接执行同步 Dataset/权限查询，包含对同一后端的同步HTTP请求，阻塞事件循环。扩展 `tests/eval_platform/test_tasks.py::test_api_create_refresh_cancel` 检查 Dataset 查询不在事件循环线程执行，原实现先失败（DID NOT RAISE RuntimeError）。修复将权限查询和 `store.create` 一起放入现有 `run_in_threadpool`，保留参数校验、403、409及幂等。

修复前只读核对未出现新任务；修复后通过弹窗“重试原请求”恢复，沿用原 request_id。最终新批次仅有一个任务；撤权后再次提交同一请求返回403，没有再次调用Agent。46项任务/批次测试通过。

### 原生撤权卡在 revoking

`EvalFlow: eval_platform/authorization_batches.py::AuthorizationBatches.close` 原调用 `grant_user_permission(..., "DENY")` 覆盖已有EDIT。当前上游该便利接口是 insert-only，已存在授权会返回400，而非upsert。现场保持503关闭读取，未发生资料放行，但会卡住撤权。

修复先持久化revoking，再经原生 `revoke_user_permission` 移除旧授权、`grant_user_permission` 写入DENY；只忽略明确的 `RESOURCE_DOES_NOT_EXIST`，其它错误保持revoking并重试。期间源授权校验和default deny保持有效，不提高后台身份权限、不改 `mlflow/`。新增 `test_close_replaces_insert_only_native_grant_and_retries_missing_row`，覆盖insert-only冲突、重复关闭、旧行已删除后的重试。测试先失败；首次修复复验还暴露了测试fixture错误地用字符串代替protobuf错误码，改正fixture后56项相关测试通过。真实后端重启后自动接续revoke/grant均200，持久状态变为revoked。

## 权限与重启结果

| 场景 | 实际结果 |
| --- | --- |
| 撤权前原生Trace、Trace artifact、Dataset/记录、Run/结果artifact | 页面及浏览器网络200，可读 |
| 源服务不可达 | 仅停止所属Agent Worktree栈；Trace、artifact及搜索503，响应“无法核实源授权”；恢复后原Trace重新200 |
| 源前端撤权 | 页面明确已撤销；批次最终revoked |
| 非管理员直读Trace / Trace artifact / Dataset / records / Run / Run artifact | 全部403，未返回批次内容 |
| 非管理员直读源实验2 | 403 |
| 扩展任务详情 | 404 |
| 扩展catalog / tasks | 200，但不再包含本批次 |
| 批次Trace / Dataset搜索 | 403 |
| 批次Run搜索 | 200空对象，无结果 |
| 集中实验1的Run搜索 | 200，不含本批次结果副本 |
| revoked持久化后再次重启EvalFlow | 上述直读拒绝和目录过滤保持，原请求重试403 |

撤权限制的是后续服务读取；不会撤回用户在授权有效时已读到或自行保存的内容。页面刷新前已加载的内容不是新增服务授权。此次没有把旧c47b6bf7批次搬迁或重放，也没有用管理员可读冒充审核用户可读。

## 验证与证据

- 后端全套：242 passed / 2 warnings；Ruff全套通过；上游 `mlflow/` 无修改。
- 命令：`.venv/bin/python -m pytest tests/eval_platform -q --tb=short --color=no`；`.venv/bin/ruff check eval_platform tests/eval_platform`。
- EvalFlow本地日志：`.local-stack/phase-create-threadpool.log`、`phase-native-grant-before.log`、`phase-native-grant-after.log`、`phase-browser-fixes-all.log`。
- 浏览器调试原始证据仅保留于EvalFlow `.local-stack/batch-browser-debug-before-fix.json` 与 `.local-stack/batch-browser-debug-after-fix.json`，不提交大体积原始页面内容。后者已停止捕获并成功导出（2,557,902字节）。
- 脱敏负例：[首次恢复后读取](26-batch-revoked-access.json)、[搜索及再次重启](27-batch-restart-and-search.json)。
- 截图均实际打开检查：17源提交、18审核发布、19首次超时、20回归通过、21撤权前Trace、22源失联关闭、23源撤权、24原生冲突关闭、25结果访问拒绝、28重启后Trace拒绝。
- 验收收尾已归还借用的源标签页794183476（工具回执为fallback window 794182680），并关闭自动化会话nazm。所属两套Worktree服务保留运行。此次只修复后端，未重跑前端构建。

## 状态与剩余范围

本合成批次的前端生命周期和读取撤权 Phase 已通过，浏览器不再blocked；Task 2.0–2.4、4.1/4.5仍按完整范围保留partial，不因此勾选整个生产资料政策、fixture覆盖、真实CI或联合验收。真实CI runner/secrets、独立评审/新盲测暂无；巡检 `quality_inspection` 授权边界仍待人工决定。采样告警、完整部署身份及恢复、其它安全场景仍以四专题待办为准。未启用生产采样或循环干预。
