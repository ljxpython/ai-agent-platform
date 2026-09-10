# 本地开发与联调说明

文档类型：`Operational`（仓库级 supporting doc）

本文是给人快速浏览的本地联调摘要；AI 代理在读取 contract 后，也可以继续读取本文来补齐启动、验证和脚本使用细节。

默认本地部署的唯一事实源是 `docs/local-deployment-contract.yaml`；如果本文与 contract 冲突，以 contract 为准。

## 1. 当前正式本地链路

以下内容对应 contract 中的正式本地演示 profile。

### 1.1 固定端口

- `apps/runtime-service`: `8123`
- `apps/interaction-data-service`: `8081`
- `apps/platform-api`: `2142`
- `apps/platform-web`: `3000`

### 1.2 当前默认链路

- 平台主链：`platform-web -> platform-api -> runtime-service`
- 结果域链路：`platform-api -> interaction-data-service`
- Runtime 落库链路：`runtime-service -> interaction-data-service`

## 2. 配置文件口径

根目录不维护统一 `.env`，本地调试时只使用各应用自己的配置文件。

## 3. 启动说明 (唯一支持方式)

**注意：本项目唯一支持的本地启动方式是使用 `local-stack.sh` 脚本。** 不要手动使用 `uvicorn` 或 `pnpm dev` 启动单个服务，否则会导致环境变量和服务发现异常。

启动整个开发环境：

```bash
bash "scripts/local-stack.sh" start
```

该脚本会自动处理依赖安装、环境变量注入和多进程管理。

停止服务：

```bash
bash "scripts/local-stack.sh" stop
```

查看状态：

```bash
bash "scripts/local-stack.sh" status
```

## 4. 最小健康检查

使用 `local-stack.sh status` 可以查看各服务状态。如果需要手动检查：

- `interaction-data-service`: `curl http://127.0.0.1:8081/_service/health`
- `runtime-service`: `curl http://127.0.0.1:8123/info`
- `platform-api`: `curl http://127.0.0.1:2142/_system/health`
- `platform-web`: 浏览器访问 `http://127.0.0.1:3000`

## 5. 当前约定

- 不共享 `.venv`
- 不共享 Node 依赖
- 不共享根级 `.env`
- `apps/platform-web` 是当前正式平台前端宿主
- `apps/platform-api` 是当前正式控制面宿主
- `apps/runtime-service` 是正式 runtime 执行层
- `apps/interaction-data-service` 是正式结果域服务
