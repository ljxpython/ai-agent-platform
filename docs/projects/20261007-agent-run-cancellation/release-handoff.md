# GraphHarbor post43 发布与 Runtime 接入

2026-10-07，状态：发布准备完成，正式 PyPI 上传等待明确发布指令。开发源码、唯一版本、四产物和隔离验收均已准备，不以未发布候选替代正式依赖。

## 本次改动

GraphHarbor 双包锁步 `0.13.0.post43`，CLI 精确依赖同版本 runtime。SDK 保持 `0.4.3`，LangGraph 保持 `1.2.11`，不升级其他依赖。

与从 PyPI 下载且哈希核实的正式 post42 wheel 对照，新增 `langhost/cancellation.py`、`langgraph_runtime_pg/migrations/versions/011_run_cancellations.py`；修改 `langhost/server.py`、`langgraph_runtime_pg/graph_executor.py`、`langgraph_runtime_pg/models.py`。这些分别提供固定目标取消/回执路由、迁移和 LangGraph 重建时的服务端图身份。业务 JWT、授权回查、inbox、报告均留在平台上层。

## 待上传的四产物

产物由双包源码构建到独立临时 dist，不清理既有发布文件。以下哈希对应已验 wheel 和最新包含测试修正的 sdist，详见[evidence/packages.json](evidence/packages.json)。

| 文件 | SHA256 |
|---|---|
| graphharbor_runtime-0.13.0.post43-py3-none-any.whl | 96c16ccff6314855d5d65a38b8c8633ee3791deeb907f841810c87e334659b65 |
| graphharbor_runtime-0.13.0.post43.tar.gz | 2455bb803dbbdf8ab6688a07f932341ab85b1c86588a66cdad29112519606bb7 |
| graphharbor-0.13.0.post43-py3-none-any.whl | 8fcb0910829355df2582e5e88881c527e442ff5dc94a92de85b760d9e2911670 |
| graphharbor-0.13.0.post43.tar.gz | 53a87a10d3edbead97e8ffbd50d350ab38ba6fc37afd71a13b64b4070dfc7fdd |

## 已完成门禁

- 双包 `uv lock --check`、`scripts/check_versions.py`、全包 Ruff check/format、mypy 与四产物 `twine check` 通过；四文件SHA256复核与表中一致。PyPI最新双包仍post42，post43尚无文件。
- 引擎主回归 Python3.11：297 passed/8 skipped；Cron 独立库：3 passed。Python3.12 生产契约集124 passed/4 skipped；Python3.13 冷安装wheel契约与固定取消集150 passed/4 skipped。skip是既有可选验收，不记为通过。
- wheel独立导入、CLI与迁移head011通过；sdist独立构建安装及导入验证。Python3.11独立wheel导入通过。
- Runtime临时复制manifest/lock接入post43，原有依赖版本保留，仅双包来源/版本变化；冷安装140包，Stop/inbox47 passed/1 skipped。
- 16条包版真实API→Runtime→Worker/PG/Redis链路，以及Showcase/DearFlow真实Docker开始后取消、移除、持久回执和8秒后无延迟写入通过。另有3项真实Docker/PPTX测试通过。
- 7条迁移/备份/恢复/正式旧post41回退通过。API回归66 passed/376 subtests passed，1条已在HEAD复现的无关fatal文案断言失败保留。

具体失败、修复和复跑来源见[verification.md](verification.md)。以上证明候选，不证明PyPI已发布，也不是前端联合Final。

## 明确发布指令之后

1. 上传前再读PyPI，确认post43没有被其他发布占用；重新核验四文件SHA256。若版本已存在且哈希不同，停止上传，重新选择唯一版本并验证。
2. 按GraphHarbor `AGENTS.md` 和 `docs/standards/release-process.md`，凭据只注入临时进程，依次上传runtime、CLI的wheel与sdist；不输出令牌，不提交源码、不打tag。
3. 从正式PyPI JSON/simple读取版本、四产物URL/哈希，独立安装并核验双包版本、CLI、接口及head011。若有部分上传失败，按发布流程记录并处理，不盲目重传。
4. 将本worktree `apps/runtime-service/pyproject.toml` 中graphharbor精确依赖改为post43，执行 `uv lock --upgrade-package graphharbor --upgrade-package graphharbor-runtime`、`uv lock --check`。锁必须指向PyPI URL/哈希，不提交临时find-links路径。
5. 在新隔离环境按正式锁安装，复跑16条HTTP/Docker和7条迁移/回退，更新正式来源证据、tasks/verification/CONTEXT/FEATURES与前端handoff。

## 部署与回退

正式包接入开发仓库不等于现役部署。现役升级需要指定环境和维护窗口，配套Platform API/Runtime/GraphHarbor API/Worker同步，备份PG并迁移引擎011、Runtime0002，再做真实授权/审计/停止冒烟。前端同事依此指定环境联调；不得与旧Runtime混用新会话接口。

回退先停止受管执行，保留加性控制表与证据、取消意图；不得恢复已取消Run为pending。隔离验证已覆盖Runtime downgrade/forward保持事实、pg_dump/pg_restore、引擎downgrade010与旧正式post41单Run cancel。删取消回执表会损失报告，因此现役优先保留表；需要回退schema时使用备份和明确恢复方案。
