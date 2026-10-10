# 后台任务执行门禁

## 时间与授权

2026-10-09，用户在本会话批准 D01-D06，要求推进至只剩前端事项或真实阻塞；相关任务 T01。

## 环境

- 本工作树独立 `uv sync --frozen`，Runtime/Platform 虚拟环境各自安装，锁文件未改。
- Runtime 从锁定来源安装 `graphharbor`、`graphharbor-runtime` 双包 `0.13.0.post43`；版本号只证明安装，接口/Worker/迁移行为仍须实测。
- 初次 Docker daemon 不可达，已启动本机 Docker Desktop；只使用本专项拥有的测试资源，不停止/删除其他容器或访问现役数据库。
- 前端不实施；完整后端与回退证据收口到 verification.md。

## 验证

- 正式 post43 双包与 SDK 0.4.3 通过锁定冷构建；最新镜像 `runtime-background-verification:20261009-final`，摘要 `sha256:c6b2a38e07f606240afcd0708d41ad0a048e49c769716fed943dab8ce9d42e0d`。部署 Dockerfile 已移除 post20 固定安装并使用 `uv.lock`。
- 两独立 Linux controller 共享 daemon/绝对挂载通过，暖启动 ACK 0.91 秒。最终镜像 Linux API/Worker E 轮完成链路 **1 passed，473.24 秒**，证据 `/tmp/runtime-background-e2e-20261009-linux-release-e`；此前 C/D 失败轮在 verification.md 单列。
- 真实 PostgreSQL、后台命令容器、独立原生 API/Worker、两组合根受管真实模型及授权故障已取得阶段证据；审批/固定 Stop 和旧源码回退增量见 verification.md。
- T01 仍为 `blocked`：post43 缺按幂等 key 只读接受回执，Worker 尚未进入 guard 的 lost-ACK 窗口不能完整对账。按 `unknown/inflight` 保留事实并禁止二次 POST，具体接续见 engine-handoff.md。
- 新提交默认关闭；未部署现役、未修改引擎源码，阶段镜像可运行不代表完整生产门禁通过。
