# Phase 3 P0 - Operations Worker 落地记录

这份文档只记录一件事：

> `operations` 从“有表有接口”升级成“能被 worker 真实捞起执行”。

补充说明：

- 本文记录的是 `phase-3 / P0` 时点的最小 worker 方案
- `phase-4 / P1` 已继续补上：
  - artifact 生命周期治理
  - `redis_list` queue backend
- 以当前口径为准时，请同时参考：
  - `phase-4-p1-artifact-lifecycle.md`
  - `phase-4-p1-redis-queue.md`

## 1. 本轮落地结果

已经落地：

- `dispatcher / executor / worker` 抽象正式进入代码
- 当前最小 queue 方案选定为 `db_polling`
- `runtime.models.refresh / runtime.tools.refresh / runtime.graphs.refresh` 已接入真实异步执行
- `assistant.resync / testcase.documents.export / testcase.cases.export` 已接入真实异步执行
- export 类型 operation 已支持 artifact 持久化与下载出口：
  - `GET /api/operations/{id}/artifact`
- operation 生命周期补齐：
  - `operation.submitted`
  - `operation.started`
  - `operation.succeeded`
  - `operation.failed`
  - `operation.cancelled`

当前不做：

- 不在 phase-3/P0 直接硬上 Redis
- 不在 HTTP 路由里直接执行长任务
- 不把 worker 逻辑塞回 FastAPI request 生命周期

## 2. 为什么当前先选 `db_polling`

当前目标是零额外基础设施也能把 worker 跑起来，优先验证边界是不是对的。

所以现在先正式定下：

- dev / smoke / 演示：`db_polling`
- future production：保留切到 Redis queue 的替换口

这样做的收益：

- 本地起服务最简单
- SQLite / PostgreSQL 都能先跑通
- 后面切 Redis 时，主要替换 `dispatcher` 和 `worker entrypoint`，不用改业务 handler 和前端协议

## 3. 代码落点

核心文件：

- `app/modules/operations/application/execution.py`
- `app/modules/operations/application/worker.py`
- `app/modules/operations/application/audit.py`
- `app/modules/operations/bootstrap.py`
- `app/entrypoints/worker/main.py`
- `worker.py`

本轮接入的业务执行器：

- `app/modules/runtime_catalog/application/operations.py`
- `app/modules/operations/application/executors.py`
- `app/modules/operations/application/artifacts.py`

## 4. 手动启动方式

推荐直接用仓库根目录脚本：

```bash
bash "./scripts/platform-web-vue-demo-up.sh"
```

启动后检查：

```bash
bash "./scripts/platform-web-vue-demo-health.sh"
```

停止：

```bash
bash "./scripts/platform-web-vue-demo-down.sh"
```

如果你要逐个进程单独排查，再按下面的分步命令执行。

### 4.1 先准备环境变量

在 `apps/platform-api-v2` 下复制一份环境变量：

```bash
cp .env.example .env
mkdir -p .data
```

### 4.2 启动 runtime upstream

在 `apps/runtime-service` 下执行：

```bash
uv run langgraph dev --config runtime_service/langgraph.json --port 8123 --no-browser
```

### 4.3 启动 legacy platform-api

在 `apps/platform-api` 下执行：

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 2024 --reload
```

### 4.4 启动 platform-api-v2

在 `apps/platform-api-v2` 下执行：

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 2142 --reload
```

### 4.5 启动 operations worker

在 `apps/platform-api-v2` 下另开一个终端执行：

```bash
uv run python worker.py
```

### 4.6 启动 platform-web-vue

在仓库根目录准备前端环境变量：

```bash
cat > apps/platform-web-vue/.env.local <<'EOF'
VITE_APP_NAME=Agent Platform Console
VITE_PLATFORM_API_URL=http://localhost:2024
VITE_PLATFORM_API_V2_URL=http://localhost:2142
VITE_PLATFORM_API_V2_RUNTIME_ENABLED=true
VITE_DEV_PORT=3000
VITE_DEV_PROXY_TARGET=http://localhost:2024
EOF
```

然后启动：

```bash
pnpm --dir apps/platform-web-vue dev
```

## 5. 手动验收路径

推荐账号：

- 管理员：`admin / admin123456`
- 普通账号：`test / test123456`

推荐验收步骤：

1. 登录 `platform-web-vue`
2. 进入任一已选项目
3. 打开 `Runtime Models` 或 `Runtime Tools`
4. 点击右上角刷新
5. 观察前端提示：
   - 先提示“任务已提交”
   - 随后 worker 执行完成
   - 页面重新加载目录结果
6. 再到 `GET /api/operations` 或后续 operations 页面里确认状态已经从 `submitted -> running -> succeeded`
7. 进入 `Assistants` 列表或详情页，触发 `重同步`
8. 进入 `Testcase / 文档管理` 或 `Testcase / 用例管理`，触发导出
9. 进入 `Operations Center`，确认：
   - 可以看到 `assistant.resync / testcase.documents.export / testcase.cases.export`
   - 详情里能查看输入、结果、错误、元数据
   - 导出型 operation 可以直接下载结果产物

## 6. 什么时候可以从前端验证

当前已经可以直接从前端验证：

- `Runtime Models` 刷新
- `Runtime Tools` 刷新
- `Assistants` 重同步
- `Testcase Documents / Cases` 导出
- `Operations Center`
- `Runtime Policies`
- `Platform Config`

条件是：

- `platform-api` 已启动
- `platform-api-v2` 已启动
- `operations worker` 已启动
- `platform-web-vue` 的 `VITE_PLATFORM_API_V2_RUNTIME_ENABLED=true`

也就是说：

- 只要按本文档第 4 节把 4 个进程都拉起来，你现在就可以从前端验证这批功能是否可用

当前还不能只靠前端完整验证的内容：

- PostgreSQL 切主后的默认开发口径
- release checklist / tag / rollback 模板

## 7. 当前已知边界

当前 worker 是最小实现，还没做：

- 多 worker 并发 claim 的强化锁策略
- dead letter / pending replay / 高级多消费者治理
- worker 心跳、指标、告警
- operation 通知中心 / WebSocket 推送
- 对象存储外接的正式 backend 实现
