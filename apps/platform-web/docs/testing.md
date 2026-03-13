# 测试与验证

## 1. 当前验证层级

### 1.1 构建验证

```bash
pnpm build
```

### 1.2 lint

```bash
pnpm lint
```

### 1.3 Playwright 回归

当前仓库已配置：

- `playwright.config.ts`
- `tests/platform-regression.spec.ts`

运行方式：

```bash
pnpm exec playwright test tests/platform-regression.spec.ts
```

说明：

- Playwright 会用 `PORT=3010 pnpm dev` 启动 webServer
- 当前没有单独的 `pnpm test` script，因此直接使用 `pnpm exec playwright test ...`

## 2. 最小验收建议

### 改页面/UI/management client

```bash
pnpm build
pnpm lint
```

### 改 workspace/chat/providers

```bash
pnpm build
pnpm lint
pnpm exec playwright test tests/platform-regression.spec.ts
```

## 3. 当前测试边界

- 当前自动化回归主要依赖 Playwright
- 很多页面交互是通过 route mock 完成，不等于真实后端联调
- 如果改动了 `platform-api` 协议或 runtime 行为，仍建议手工联调一次
