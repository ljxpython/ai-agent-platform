# 前端 API 地址与本地/远端调试说明

本文补充说明 `platform-web` / `runtime-web` 在不同调试场景下应如何配置 API 地址，避免把浏览器端请求错误地指向 `localhost`。

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

### 2.1 四个服务都在 Mac 本地运行

适用场景：

- 你在 Mac 上本地启动 `platform-web`
- `platform-api` 也在 Mac 上
- `runtime-service` 也在 Mac 上

推荐配置：

```env
# apps/platform-web/.env.local
NEXT_PUBLIC_API_URL=http://localhost:2024
NEXT_PUBLIC_PLATFORM_API_URL=http://localhost:2024
NEXT_PUBLIC_ASSISTANT_ID=assistant
```

```env
# apps/runtime-web/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8123
NEXT_PUBLIC_ASSISTANT_ID=assistant
```

### 2.2 前端在 Mac，本次联调的后端在远端服务器

适用场景：

- 你在 Mac 上运行 `platform-web`
- 浏览器访问的是 Mac 本地前端
- `platform-api` 跑在服务器上

推荐配置：

```env
# apps/platform-web/.env.local
NEXT_PUBLIC_API_URL=http://101.126.90.71:2024
NEXT_PUBLIC_PLATFORM_API_URL=http://101.126.90.71:2024
NEXT_PUBLIC_ASSISTANT_ID=assistant
```

### 2.3 前端和后端都部署在远端服务器，并从外部机器访问

适用场景：

- 浏览器访问 `http://101.126.90.71:3000`
- `platform-api` 也部署在该服务器

推荐配置：

```env
# apps/platform-web/.env
NEXT_PUBLIC_API_URL=http://101.126.90.71:2024
NEXT_PUBLIC_PLATFORM_API_URL=http://101.126.90.71:2024
NEXT_PUBLIC_ASSISTANT_ID=assistant
```

不要写成：

```env
NEXT_PUBLIC_API_URL=http://localhost:2024
```

因为这会让外部浏览器把请求发往“访问者自己的本机”。

## 3. `pnpm dev` 与 `pnpm build`

### 3.1 `pnpm dev`

开发模式下修改 `.env` 后，通常重启开发服务器即可。

但浏览器本地缓存的 API 地址仍可能覆盖新配置，因此切换环境后建议清理一次 `localStorage`。

### 3.2 `pnpm build`

`NEXT_PUBLIC_*` 变量会在构建时进入前端产物。

这意味着：

- `pnpm build` 之前必须先写好正确的公网地址或本地地址
- 如果改了 `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_PLATFORM_API_URL`，需要重新 `pnpm build`
- 不能指望旧的构建产物在 `pnpm start` 时自动吃到新的 `NEXT_PUBLIC_*`

## 4. 浏览器缓存注意事项

前端会在浏览器 `localStorage` 里保存这些键：

- `lg:platform:apiUrl`
- `lg:chat:apiUrl`
- `oidc:token_set`
- `lg:chat:apiKey`

切换“本地联调 / 远端联调 / 公网访问”后，如果页面仍然打到了旧地址，先在浏览器控制台执行：

```js
localStorage.removeItem("lg:platform:apiUrl");
localStorage.removeItem("lg:chat:apiUrl");
localStorage.removeItem("oidc:token_set");
localStorage.removeItem("lg:chat:apiKey");
location.reload();
```

## 5. 本次代码调整做了什么

为避免前端继续回退到硬编码的 `localhost:2024`，当前代码已做这些收敛：

- 新增统一的 platform API 地址解析逻辑
- 优先使用 `NEXT_PUBLIC_PLATFORM_API_URL`
- 其次使用 `NEXT_PUBLIC_API_URL`
- 如果浏览器里残留了旧的 loopback 地址，而当前环境变量已是公网地址，优先改用当前环境变量
- 对若干 `platform-web` 页面和管理接口客户端的默认回退逻辑做了统一处理

相关文件：

- `apps/platform-web/src/lib/platform-api-url.ts`
- `apps/platform-web/src/lib/oidc-storage.ts`
- `apps/platform-web/src/lib/management-api/client.ts`
- `apps/platform-web/src/lib/management-api/artifacts.ts`
- `apps/platform-web/src/providers/Thread.tsx`
- `apps/platform-web/src/providers/Stream.tsx`
- `apps/platform-web/src/app/workspace/sql-agent/page.tsx`

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
