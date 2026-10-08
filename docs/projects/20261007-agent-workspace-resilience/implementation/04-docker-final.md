# Docker 恢复验收与资源关闭

日期：2026-10-07；关联 T32/T33。用户明确要求完成后延 Docker 事项并在用完后关闭 Docker；治理方案已批准，仍在原独立 worktree，不修改前端或部署现役服务。

## 代码与环境

- Docker Server 28.0.4；所需 `python:3.13-slim`、`postgres:16`、`redis:7-alpine` 已存在，不拉取镜像。
- 沿用已有 Runtime/API Python 环境，工作目录和 `PYTHONPATH=src` 指向 worktree；GraphHarbor 0.13.0.post41、LangGraph 1.2.11、pytest 9.0.2。
- 仅修改 `apps/runtime-service/tests/workspace/test_execution.py`：新增 `test_real_parallel_repeated_cancel_reaps_only_owned_resources()`；用挂载 release 文件控制两个真实容器，分别重复取消，检查另一调用未被误取消、计数各一次、原文件保留、CLI退出及专属容器归零。finally只回收本用例已知资源。
- 同文件 `test_real_docker_success_measurement_and_parallel_isolation()`：从 HEAD 加载基线执行器，每版预热一次，随后12次基线/候选交替采样，统计p50/p95、Python CPU和命令/控制进程数。取代按版本连续8次采样，减少冷启动与执行顺序影响；不添加性能SLO。
- 本轮未发现需要修改生产执行器的问题；完整HTTP/Worker用例复用现有独占容器夹具，候选探测失败注入和合成Langfuse transport保持明示。

## 已执行 Phase

1. 共享执行器真实Docker：4 passed、32 deselected，40.71秒；不可达socket、不降级宿主执行、exit7/125、unknown/cancel、并行取消和初次成功测量通过。
2. Dear/Showcase真实容器接入：2 passed、9 deselected，43.70秒；保护挂载、技能只读、超时、输出上限、取消无迟到写入通过，既有SWIG警告保留。
3. 改成交替采样后性能/并行取消：2 passed，89.63秒。两个并行命令各副作用once，重复取消后已知CLI/容器剩余0，工作区保留。

| 交替采样（每版12次，预热不计） | HEAD基线 | 当前候选 |
| --- | --- | --- |
| p50毫秒 | 1467.921 | 2213.191 |
| p95毫秒 | 3492.018 | 3326.125 |
| Python CPU毫秒（12次合计） | 171.521 | 176.614 |
| 命令进程数 | 12 | 12 |
| 额外探测/控制进程数 | 0 | 0 |

首轮每版8次连续采样：基线p50=1193.305/p95=1403.262，候选p50=1129.814/p95=2683.073毫秒。两轮延迟存在宿主/容器调度波动，交替采样候选中位数仍高于基线；如实保留，不能表述为性能提升或已满足生产SLO。CPU/进程和成功路径无额外探测/观测的断言通过。

G1真实副作用证据与执行器非integration回归32 passed、4 deselected，43.00秒。当前公共asyncio异常仍不能区分创建前/管道接线后，EAGAIN可发生在文件写入之后；按批准分支B不自动retry，不为环境可用而重放命令。

## HTTP/Worker 完整链路、安全与回退

`test_workspace_failure_worker_no_requeue_and_safe_replay` 与 `test_http_main_child_errors_and_restart_replay` 串行完成：2 passed，1561.03秒（26:01），退出码0。本轮没有失败用例；运行较慢不替代最终通过结果。

Docker模式独占PG/Redis和实际Runtime API/Worker/Platform API，固定合成模型触发真实Agent execute。已验证Dear普通exit7 Run success；Dear/Showcase主图与Showcase执行子图unknown Run error、PG business_error、retry_count=1仅首次claim，挂载counter均为once。诊断disabled仍可见安全执行错误，live/Run/Thread/state/history/Protocol回放一致。

真实callback记录经合成Langfuse MockTransport进入实际Runtime查询/API DTO，三条失败Run各一条Workspace摘要；不代表公网Langfuse采集/存储。owner/shared-read/撤权/跨项目/错Run矩阵通过，DIAGNOSTIC_CANARY剥离。根符号链接拒绝且原目录保留；实际执行取消为interrupted、副作用once、无迟到输出。

工具主/子图恢复、未知程序错误安全传播及实际approve/edit/reject/clarification/cancel通过。Runtime API、Worker、Platform API三角色实际重启后checkpoint回放与keep文件保留；恢复临时HEAD源码后主/子图新Run成功。Workspace用例保留4个工作区与历史状态后回退续接成功，不删除或替换原工作区，也不修改真实worktree HEAD。

| 场景 | thread_id | run_id |
| --- | --- | --- |
| Dear正常工具结果 | `222b027a-0a47-45a2-ad39-d00ec037f54c` | `f3f25836-e125-4ab4-a4b0-2f172fa581d2` |
| Dear主图unknown | `a44d339a-bab5-4046-a38d-ddb1a335a0ff` | `e2c5f435-3383-4fd4-9941-9fbe1b52e1d3` |
| Showcase主图unknown | `4140f92c-20f8-439c-bcce-fbffb1d638ff` | `92cc7831-8b66-4fa8-a89a-4a0f9732f4ee` |
| Showcase子图unknown | `c4b39441-6e88-49cd-96a1-207a3ea20f52` | `d4f94496-6ed8-45e4-86f5-008aa1c6c91b` |
| Dear执行取消 | `19971216-114b-439a-b3c2-660d737dc984` | `f4217bd8-0372-4080-a755-b35acd75fc85` |
| 工具主图恢复 | `52036af6-b2f2-4185-920b-67f25362a2fa` | `67b74446-f601-4655-be99-3835296beb86` |
| 工具子图恢复 | `fd87f1b7-51ff-43aa-a683-30b3ac6d6c25` | `f00f9254-db00-44ff-a3e7-fe682273036e` |

日志分别在 `/tmp/workspace-docker-final-20261007/test_workspace_failure_worker_0/` 与 `/tmp/workspace-docker-final-20261007/test_http_main_child_errors_an0/`。ready/spec包含测试凭据，不公开整份；运行ID对应已回收的隔离资源，不能在现役服务查询。

## 资源回收与 Docker 关闭

- 两项HTTP测试退出后，本轮夹具进程归零；`docker ps -a --filter name=tool-errors-` 为空。`docker ps` 仅余开始前已有的 `llmops-db`、`llmops-weaviate`、`llmops-redis`，没有删除其数据、容器或镜像。
- 按用户明确授权执行 `docker desktop stop --timeout 45`，退出码0，输出Stopping Docker Desktop。
- 关停后 `docker desktop status` 退出1，无法获取运行状态；`docker info --format '{{.ServerVersion}}'` 不能连接daemon且无ServerVersion。该模板可能返回0，不能单凭退出码判断engine可用。
- 进程检查确认 `com.docker.backend`、`com.docker.virtualization`、Docker Desktop、build/dev-envs后台均已退出。未再启动Docker，未停止同事的原生测试进程。

## 复现入口

以下记录本轮执行入口，工作目录为worktree的 `apps/runtime-service`。`RUNTIME_TEST_PYTHON`/`PLATFORM_API_TEST_PYTHON` 指既有虚拟环境的Python，先确认 `PYTHONPATH=src` 的导入来自worktree；不新增产品配置。HTTP夹具自行创建并回收独占容器，不读取或重建现役数据库。复现时替换成新的 `--basetemp`，保留本轮证据目录；重新执行Docker用例需先启动Desktop，本轮交付不再启动。

```bash
# 共享执行器真实 Docker；包含不可达 socket、单次执行、取消与成功测量
PYTHONPATH=src "$RUNTIME_TEST_PYTHON" -m pytest -q -s -m integration tests/workspace/test_execution.py
# Dear / Showcase 实际容器接入
PYTHONPATH=src "$RUNTIME_TEST_PYTHON" -m pytest -q -s -m integration tests/services/dearflow_agent/test_tool_error_integration.py tests/services/showcase_demo/test_backend.py
# 更新后的交替性能与并行重复取消
PYTHONPATH=src "$RUNTIME_TEST_PYTHON" -m pytest -q -s tests/workspace/test_execution.py::test_real_docker_success_measurement_and_parallel_isolation tests/workspace/test_execution.py::test_real_parallel_repeated_cancel_reaps_only_owned_resources
# G1 真实副作用证据与非外部回归
PYTHONPATH=src "$RUNTIME_TEST_PYTHON" -m pytest -q -m "not integration" tests/workspace/test_execution.py
# 两条真实 Docker HTTP/API/Worker 链路；使用新独占 basetemp
PYTHONPATH=src TOOL_ERROR_PLATFORM_TEST=1 PLATFORM_API_TEST_PYTHON="$PLATFORM_API_TEST_PYTHON" "$RUNTIME_TEST_PYTHON" -m pytest -x -s -q --basetemp=/tmp/workspace-docker-final-20261007 tests/services/dearflow_agent/test_tool_error_platform.py::test_workspace_failure_worker_no_requeue_and_safe_replay tests/services/dearflow_agent/test_tool_error_platform.py::test_http_main_child_errors_and_restart_replay
# 仅在测试退出、自有资源回收后，按用户授权关闭并检查 Docker Desktop
docker desktop stop --timeout 45
docker desktop status
docker info --format '{{.ServerVersion}}'
```

## 交付边界

T32/T33非前端Docker后延事项已完成，当前任务状态以tasks.md为准。前端T23/F01-F10与浏览器由同事完成；G1分支B自动retry仍deferred，当前attempts=1、retry_wait_ms=0。云provider、公网模型/Langfuse及现役部署不在授权范围，未提交、未推送、未部署。最终文档门禁与四态结论单独写入verification.md本轮Final。
