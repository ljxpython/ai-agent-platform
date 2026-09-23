# 验证计划和记录

## Phase 验证

- [x] Dear Agent 本地后端：工作区文件、密钥环境隔离、退出码、超时，数据分析和 PPT 脚本实跑。
- [x] Showcase 和终端遵循同一个 `RUNTIME_BACKEND`，非法值拒绝。
- [x] 本地栈配置：默认 local、显式 docker、非法值拒绝，API/Worker 一致；常规 Runtime 环境具备本地脚本依赖。

## Final 验证

- [x] Dear Agent 审批后 execute 到文件发布的图链路；Platform API 到 Runtime 工作区 HTTP 合约。
- [x] Runtime 定向回归、编译检查、文档检查、锁文件检查与 `git diff --check`。
- [x] 本机 Runtime API/Worker 已按最终配置重启，常规依赖已安装，服务健康。
- [ ] Docker 实跑回归：本机 Docker daemon 未运行。
- [ ] 浏览器手工验收：未执行。

## 2026-09-23 Phase 验证

- `uv run --frozen pytest`（Dear Agent execute/agent、Showcase backend、Terminal/HTTP）：34 passed、4 skipped。跳过项为 Docker 实跑。
- `python3 -m unittest` 启动脚本两个定向用例：2 passed。
- 同文件完整 5 用例曾执行为 4 passed、1 failed；失败的是既有 `test_cleanup_preview_preserves_database_and_backups`，在临时目录运行清理预览时返回 `fatal: not a git repository`，与本次执行后端无关。
- `uv run --frozen python -m unittest tests.test_runtime_gateway_workspace -q`：4 passed。

## 2026-09-23 Final 验证

- `uv run --frozen python -m compileall -q`：通过；`uvx --from ruff ruff check` 对改动 Python 文件检查通过。
- `uv lock --check`、`scripts/check_docs.py`、`git diff --check`：通过。
- `local-stack.sh restart-one runtime-worker` 和 `restart-one runtime-api`：成功；`local-stack.sh status` 显示四个服务运行，Runtime `/ready` 与 Platform API 健康检查通过。
- 未通过真实模型和浏览器重新发起 Dear Agent execute；自动化覆盖审批恢复、命令执行和产物发布。

## 结论

**partial。** 本地无 Docker 执行目标已实现并验证；容器回归与浏览器手工验收缺少证据。生产 Runtime 未设置 `RUNTIME_BACKEND` 时仍默认 Docker；local 模式不具备容器隔离，只允许受信任开发机使用。
