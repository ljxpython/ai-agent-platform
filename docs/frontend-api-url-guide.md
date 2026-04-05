# 前端 API 地址与本地/远端调试说明

本文补充说明 `platform-web-vue` / `runtime-web` 在不同调试场景下应如何配置 API 地址，避免把浏览器端请求错误地指向 `localhost`。

补充口径：

- `apps/platform-web-vue` 是当前正式平台前端宿主
- `apps/platform-web` 只保留为历史兼容入口
- 如果你正在看旧的 `NEXT_PUBLIC_*` 配置示例，请把它视为旧前端的历史说明，不再是默认主线

## 1. 核心原则

前端代码运行在浏览器里。

这意味着：

- 浏览器里出现的 `http://localhost:2024`，指向的是“打开页面的那台机器”
- 不是指向部署前端的服务器
- 如果你在 Mac 上打开 `http://101.126.90.71:3000`，前端再去请求 `http://localhost:2024`，浏览器会把它理解成 `Mac:2024`

因此：

- 前端和后端都在同一台本机开发时，可以使用 `localhost`
- 只要前端页面是通过远端 IP/域名访问的，就不要再把浏览器请求写成 `localhost`

## 2. 推荐配置矩阵

### 2.1 五个服务都在 Mac 本地运行

适用场景：

- 你在 Mac 上本地启动 `platform-web-vue`
- `platform-api` 也在 Mac 上
- `runtime-service` 也在 Mac 上

推荐配置：

```env
# apps/platform-web-vue/.env.local
VITE_PLATFORM_API_URL=http://localhost:2024
VITE_DEV_PROXY_TARGET=http://localhost:2024
VITE_DEV_PORT=3000
```

```env
# apps/runtime-web/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8123
NEXT_PUBLIC_ASSISTANT_ID=assistant
```

### 2.2 前端在 Mac，本次联调的后端在远端服务器

适用场景：

- 你在 Mac 上运行 `platform-web-vue`
- 浏览器访问的是 Mac 本地前端
- `platform-api` 跑在服务器上

推荐配置：

```env
# apps/platform-web-vue/.env.local
VITE_PLATFORM_API_URL=http://101.126.90.71:2024
VITE_DEV_PROXY_TARGET=http://101.126.90.71:2024
VITE_DEV_PORT=3000
```

### 2.3 前端和后端都部署在远端服务器，并从外部机器访问

适用场景：

- 浏览器访问 `http://101.126.90.71:3000`
- `platform-api` 也部署在该服务器

推荐配置：

```env
# apps/platform-web-vue/.env
VITE_PLATFORM_API_URL=http://101.126.90.71:2024
VITE_DEV_PROXY_TARGET=http://101.126.90.71:2024
VITE_DEV_PORT=3000
```

不要写成：

```env
VITE_PLATFORM_API_URL=http://localhost:2024
```

因为这会让外部浏览器把请求发往“访问者自己的本机”。

## 3. `pnpm dev` 与 `pnpm build`

### 3.1 `pnpm dev`

开发模式下修改 `.env` 后，通常重启开发服务器即可。

但浏览器本地缓存的 API 地址仍可能覆盖新配置，因此切换环境后建议清理一次 `localStorage`。

### 3.2 `pnpm build`

`VITE_*` 变量会在构建时进入前端产物。

这意味着：

- `pnpm build` 之前必须先写好正确的公网地址或本地地址
- 如果改了 `VITE_PLATFORM_API_URL` / `VITE_DEV_PROXY_TARGET`，需要重新 `pnpm build`
- 不能指望旧的构建产物在 `pnpm preview` 时自动吃到新的 `VITE_*`

## 4. 浏览器缓存注意事项

当前前端会在浏览器 `localStorage` 里保存若干工作区状态，例如：

- 登录 token
- 当前项目 id
- chat 目标缓存
- 主题和语言选择

切换“本地联调 / 远端联调 / 公网访问”后，如果页面仍然打到了旧地址，先在浏览器控制台执行：

```js
localStorage.clear();
location.reload();
```

## 5. 当前正式前端代码口径

`platform-web-vue` 当前通过统一 env 模块和服务客户端收敛 API 地址：

- `VITE_PLATFORM_API_URL` 作为平台 API 基础地址
- `VITE_DEV_PROXY_TARGET` 作为本地开发代理目标
- `runtime-web` 继续保持直连 `runtime-service`

相关文件：

- `apps/platform-web-vue/src/config/env.ts`
- `apps/platform-web-vue/src/services/http/client.ts`
- `apps/platform-web-vue/src/services/langgraph/client.ts`

## 6. `runtime-web` 额外说明

`runtime-web` 默认应直连 `runtime-service`。

如果你希望从外部机器访问 `runtime-web`，那么 `runtime-service` 也必须能被该外部机器访问；否则即使前端页面能打开，浏览器里的请求仍然会失败。

也就是说，下面两件事必须同时成立：

- `runtime-web` 对外可访问
- `runtime-service` 对外可访问，或被反代到一个对外可访问的地址

## 7. 最后建议

如果你需要在“Mac 本地开发”和“服务器公网访问”之间频繁切换，建议：

- 本地使用 `.env.local`
- 服务器保留自己的 `.env`
- 每次切换目标环境后重启前端
- 必要时清理一次浏览器 `localStorage`
