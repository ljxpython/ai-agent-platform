# 批准记录与启动边界证据

日期：2026-10-07。关联任务：T00、T01、T02。

用户明确批准：“方案评审通过，可以开始实施了。把除了前端的开发项都开发完成，除非有 Block 项……docker我已经启动了”。本轮范围是 Runtime/API 及其验证和前端交接报告；不修改前端、不提交、不部署现役服务。

G0 按批准方案收敛原生 tasks 脱敏，并以现有工具容错测试/交接采用的 `runtime.execution_failed` 作为通用公开稳定标识。HTTP Envelope 码独立，不受此变更影响。对象保持有限 type/message/code，字符串保持字符串；Workspace 使用精确固定码。

G1 选择已批准分支 B：单次执行，当前 Docker/local 的自动启动重试 deferred。CPython 3.13 的 `asyncio.BaseSubprocessTransport` 先启动子进程，随后 `_connect_pipes()` 异步连接 stdout/stderr；管道连接可在命令已经产生副作用后抛出 EAGAIN。公共 `create_subprocess_exec()` 只暴露整体异常，缺少“命令未启动”的类型化证据。不能借 errno 或函数尚未返回 process 推导安全重试。

已用真实子进程副作用计数证明创建前/管道接线后故障的区别：创建前失败无副作用，接线后 EAGAIN 时 counter=once。测试对 CPython 底层边界注入故障；产品代码不依赖其私有 API、traceback 或异常文字。后续云 SDK 有可靠未提交信号时再实施 provider 内部重试；本期不新增空 retry 框架或耗尽码。

批准实施时 Docker daemon 可用，`python:3.13-slim` 已安装，当时集成资源使用测试独占容器和临时目录。用户随后要求使用本地已有环境、Docker 事项后延，原生 PG/Redis、local backend 和已有 Python 的阶段结果见 implementation/03-chain-validation.md。用户之后重新授权完成 Docker 后延验收并在用完关闭；T32/T33 已完成，Docker Desktop 已关闭，当前 Final 见 implementation/04-docker-final.md 与 verification.md。
