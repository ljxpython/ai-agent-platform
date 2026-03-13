# 本地开发说明

## 1. 环境文件

当前开发优先使用：

```bash
cp .env.example .env
```

## 2. 常用环境变量

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_PLATFORM_API_URL`
- `NEXT_PUBLIC_ASSISTANT_ID`
- `LANGGRAPH_API_URL`
- `LANGSMITH_API_KEY`
- `FRONTEND_LOGS_DIR`
- `FRONTEND_SERVER_LOG_FILE`
- `FRONTEND_CLIENT_LOG_FILE`

说明：

- 管理面基线优先看 `NEXT_PUBLIC_PLATFORM_API_URL` / `NEXT_PUBLIC_API_URL`
- `LANGGRAPH_API_URL` 和 `LANGSMITH_API_KEY` 只在 `src/app/api/[..._path]/route.ts` 的 Next passthrough 场景使用

## 3. 启动开发服务器

```bash
pnpm install
pnpm dev
```

默认访问：`http://localhost:3000`

## 4. 推荐联调口径

### 只联调平台管理面

- 确保 `platform-api` 运行在 `http://localhost:2024`
- 通过登录页进入 `/workspace/*`

### 联调 chat / threads

- 确保 `platform-api` 可访问
- 确保 `platform-api` 已正确连接 `runtime-service`
- 如需 direct passthrough，再配置 `LANGGRAPH_API_URL`

## 5. 常见本地验证

- 登录是否成功
- `/workspace/projects` 是否能加载项目
- `/workspace/assistants` 是否能读写管理数据
- `/workspace/chat` 是否能建立 stream
