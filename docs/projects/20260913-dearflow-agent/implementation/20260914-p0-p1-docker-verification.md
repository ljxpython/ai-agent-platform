# P0/P1 Docker 验证与剩余项核查

## 改动时间

2026-09-14

## 本次修改的代码文件

本次没有修改运行时代码；本次是对已落地代码进行真实容器验证，并更新阶段状态。当前实现代码位置如下，便于排查：

- `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`：Deep Agent 组合根、Runtime middleware、审批配置。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py`：Dear workspace、容器执行入口和会话隔离。
- `apps/runtime-service/src/runtime_service/workspace/execution.py`：Docker 限额、只读挂载、超时和清理。
- `apps/runtime-service/src/runtime_service/workspace/artifact_refs.py`：TXT 产物发布、哈希和读取。
- `apps/runtime-service/src/runtime_service/http/documents.py`：签名 scope 文件上传/读取与 outputs 支持。
- `apps/runtime-service/src/runtime_service/workspace/scoped.py`：graph/thread 工作区解析。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/capabilities.py`：Dear Agent 能力声明。
- `apps/runtime-service/src/runtime_service/graphs/dearflow_agent.py`、`langgraph.json`：graph 注册。
- `apps/runtime-service/deploy/Dockerfile.agent-workspace`：执行镜像定义。

## 验证

执行命令：

```bash
.venv/bin/python -m pytest -q tests/services/showcase_demo tests/test_scoped_and_refs.py
```

结果：**52 passed、3 skipped**。Docker daemon 已可连接，之前因 daemon 不可用导致的公共执行失败已消除。

## 仍未完成

- Dear Agent 专属 graph 的授权、审批、澄清、产物下载和恢复尚无专属测试证据。
- worker 重启后的持久恢复尚未验证；公共执行通过不等于 P1 全链路完成。
- 本次没有修改前端代码，也没有把已有前端测试当作后端验收。
