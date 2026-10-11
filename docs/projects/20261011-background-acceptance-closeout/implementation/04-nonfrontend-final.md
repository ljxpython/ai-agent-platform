# 非前端 Final 与前端交付

## 日期、范围和工作区

2026-10-11；K06/K08 与原 T01/T05/T08 收口。唯一目录为 `~/.codex/worktrees/b01-closeout/ai-agent-platform`，基线 `2b94585b544f055be3f1a0098a1563fa8a0e5ea3`，环境 `wt_43727db9404e`。用户批准的非前端范围 `done`，没有 Block；整体 `partial`，K09/K10 与后续 K11 交同事。未提交、推送或部署现役。

## 交付补丁

业务补丁见 [完成续接记录](02-completion-context-and-merge-repairs.md)和[迁移/本地栈记录](03-schema-and-local-stack-isolation.md)：

- Platform `background_completion.py::deliver()` 和 `service.py::launch_runtime_run()` 创建完成 Run 的新执行 Context，在最终 Context 确定后重签 completion marker、再落盘最终字节；原 origin/callback 与固定接受回执共存。
- Runtime `runtime/auth.py` 恢复 credential claim，以关键字同时保留 credential/callback/acceptance；`background_tasks/repository.py::list_tasks()` 只投影 accepted 且无 Stop 的自动候选，suppressed 详情保留原 Run。
- 两应用新增 merge head，Platform 再修历史 SQLite UUID 一致性。实际 head 为 Platform `20261011_0009`、Runtime `0004_background_token_budget`、引擎 `013_run_acceptance_receipts`；旧接受事实保留。
- 本地栈新启动默认关闭，API/Worker host 和私有日志由登记环境派生；Redis 归属排除验收 PG。运行手册写明排空及匹配源码回退，生产默认不扩大。

没有新增公开 DTO、回执页面或故障注入 API；不开发 GraphHarbor 或 LocalBackgroundRunner。故障挂点、文件屏障、进程/迁移检查均复用测试夹具。

## 实际验证

独立 Final 的计数、范围、耗时和限制在 [verification.md 第 7 节](../verification.md#7-final记录独立)，报告 SHA256 与实际 task/event/run/副作用摘要在 [final-evidence.json](final-evidence.json)。原始 JUnit、失败轮、日志和 fixture 在本 Worktree 忽略目录 `.local-stack/verification/`；产物来源见 [artifacts.json](artifacts.json)。

系统 Final 从 `apps/runtime-service` 执行，下列参数与实际命令等价（绝对路径以 `CLOSEOUT_ROOT` 表达），`PLATFORM_API_TEST_PYTHON` 指向本 Worktree API `.venv`，未设置 `TOOL_ERROR_PLATFORM_NATIVE`：

```bash
CLOSEOUT_ROOT="$PWD/../.."
TOOL_ERROR_PLATFORM_TEST=1 \
PLATFORM_API_TEST_PYTHON="$CLOSEOUT_ROOT/apps/platform-api/.venv/bin/python" \
BACKGROUND_RUNTIME_IMAGE="sha256:3b7a07136c46d7d151218571f45a40016dbd1044938ae976aff2aadc7a992601" \
.venv/bin/python -m pytest tests/e2e/test_background_tasks.py -q \
  -k 'test_source_native_timeout_and_cancel_suppress_completion or test_disabled_drain_preserves_receipts_and_matching_source_rollback or test_release_linux_api_worker_completion_and_shared_storage or (test_lost_native_ack_reconciles_queued_run_without_resubmission and linux-release)' \
  --basetemp="$CLOSEOUT_ROOT/.local-stack/verification/final-system-complete" \
  --junitxml="$CLOSEOUT_ROOT/.local-stack/verification/final-system-complete.xml"
```

结果 **6 passed、9 deselected、2285.02s，failures/errors/skipped=0**。Linux notify/Stop/撤权每条 POST=1、重复 GET=20、2 Runs、1 ledger，完成模型 1/0/0；源超时/取消实际清理并抑制通知；正常 Linux 完成 Run 成功、有界日志和共享挂载通过。

回退先关闭新提交并排空，使用同一事务/锁 downgrade 到共同父节点 `0002_run_control`，再 stamp `0003_token_budget`。旧提交 `bd476ae62a61acb7c55bc0f08eba3645ce50daf0` 的 API/Worker 正常启动、普通 Run 成功，单一版本标记与 task/event/submission/status/cleanup/delivery/run/Stop 事实逐字段保留；引擎接受事实不降级。直接降到 Token 分支的失败轮仍保留，不能计通过。

两根受管 `gpt-5.6-terra` 完整链与独立 Usage 引用已经通过的 Phase；生产源码 12 个摘要在 Final 期间不变，不重复收费验收。审批/HITL/固定 Stop/模型撤销引用通过的具体 case，失败组未整体计通过。真实 Docker/PG 对原 opt-in skip 单独补验；local-stack 三环境旧 opt-in 的 1 个 skip 保留。

## 交接环境与资源

系统 fixture 结束后盘点：进程 0、已取证的 18 个任务对应容器 0、最终镜像 API/Worker 控制容器 0。长期交接栈随后从本目录启动，保留专属 DB/Redis/Workspace/日志；没有清空历史或停止其他 Worktree。

实际执行：

```bash
RUNTIME_BACKEND=docker bash "scripts/local-stack.sh" start
bash "scripts/local-stack.sh" status
```

Runtime API/Worker、Platform API/Web、Redis 均运行，Runtime `/ready`、Platform `/_system/health` 和 Web `/` 均 HTTP 200。Web `http://127.0.0.1:29286`，API `http://127.0.0.1:23818`，Runtime `http://127.0.0.1:24548`，本地管理员 `admin / admin123`。本环境显式开启后台启动，仓库默认仍关闭；每次 Docker 重启显式带 `RUNTIME_BACKEND=docker`，使用登记 host 和私有日志。

质量与文档检查原始摘要为 `final-quality.json`、`final-script-quality.json`、`final-docs.json`。状态更新后的文档复验为 **24 份 Markdown、425 个链接、新增错误 0**；首次 7 处 macOS 固定路径告警保留在 `final-docs-paths-failed.json`，正文改为可迁移引用，准确展开路径及实际系统命令保留在 JSON。Ruff/格式仅覆盖改动，两服务、27 个 AST、shell 语法及差异空白通过；4 条既有脚本告警、FEATURES 的 4 个旧失效链接单列，未修范围外内容。不声称整仓 lint/全仓回归无误。

## 同事接手与剩余事项

前端源码/测试改动数为 0。请按 [frontend-handoff.md](../frontend-handoff.md) 的三处修补、准确文件、K09/K10 验收、环境和故障协作执行；原 F01–F11/A-B 保留，原 T10/F12 尚未联合 Final。未提交的补丁、迁移和专项文档须完整带入接手环境，仅从 HEAD 新建目录会遗漏本轮修复。

经验建议：迁移多 head 的回退要核对旧源码识别的唯一 head；故障边界用文件屏障而非短命令/固定 sleep；macOS 多进程夹具需区分标准 asyncio 与 uvloop 的原生 abort。建议经用户确认后沉淀到 `docs/lessons/runtime-service.md`/`ai-workflow.md`，本轮未写入，且不阻塞交付。

JWT/SSE 草案仍有独立门禁，不整体毕业。接受回执不等于命令、续接 Run、资源清理或用户通知完成；单样本 ACK 与本机索引查询不是生产 SLO。
