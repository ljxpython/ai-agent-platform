# 08. `platform-web-vue` 工程初始化规范

## 目标

这份文档专门收敛三件事：

1. `platform-web-vue` 的 `package` 规范
2. `scripts` 规范
3. `env` 规范

这三件事如果不先定下来，后面新 app 刚起步就容易出现下面这些破事：

- 有人用 `npm`，有人用 `pnpm`
- 有人用 Node 20，有人拿 Node 25 硬跑
- 有人把环境变量写死在页面里
- 有人不知道该提交什么、该忽略什么

## 一、当前仓库的已知事实

结合现有项目，当前事实如下：

### 1. 现有仓库不是标准根级 workspace

当前仓库根目录下没有看到：

- 根级 `package.json`
- 根级 `pnpm-workspace.yaml`
- 根级 `pnpm-lock.yaml`

这意味着：

- 当前几个前端 app 还是“各自自治”的状态
- `platform-web-vue` 初始化阶段不要顺手去重构整个仓库的包管理边界

当前阶段的正确做法是：

- 只把 `platform-web-vue` 自己管好
- 不在 Phase 1 顺手引入全仓 workspace 改造

### 2. 现有稳定参考

当前 monorepo 里的稳定参考已经明确：

- `packageManager` 为 `pnpm@10.5.1`
- `apps/platform-web-vue` 的 `engines.node` 为 `>=20.17.0 <23`

`sub2api` 当前虽然没有声明 `packageManager` 和 `engines`，但它的 Vue/Vite 组合已经验证可运行。

### 3. 现有 env 管理并不规范

当前情况不太整齐：

- `platform-web` 没有 `.env.example`
- `sub2api/frontend` 没有 `.env.example`
- 只有 `runtime-web` 提供了 `.env.example`

这说明新 app 必须把 env 规范补齐，不然一开工就会靠记忆和口口相传。

## 二、`package` 规范

## 1. 包名与位置

正式新 app 已确认：

- 目录：`apps/platform-web-vue`
- 包名：`platform-web-vue`

### 2. 包管理器

统一使用：

- `pnpm@10.5.1`

原因：

- 已与 `platform-web`、`runtime-web`、`platform-web-vue` 当前实践保持一致
- 现有上下文里已经实际使用过
- 没必要在迁移时再引入第二套包管理器

明确要求：

- 不使用 `npm`
- 不使用 `yarn`
- 不混用锁文件

### 3. Node 版本规范

正式规范建议写成：

- `engines.node: >=20.17.0 <23`

团队默认开发版本建议固定为：

- `Node 22 LTS`

结论要写死成两层：

- 支持范围：`>=20.17.0 <23`
- 日常默认：`Node 22 LTS`

明确不支持：

- Node 25

原因很直接：

- 我们前面已经踩过不稳定版本的坑
- 这次目标是稳定迁移，不是替新版本生态做兼容测试

### 4. 锁文件策略

由于当前仓库不是根级 workspace，新 app 采用：

- app 级 `pnpm-lock.yaml`

建议：

- `apps/platform-web-vue/pnpm-lock.yaml` 提交入库

当前阶段不要做：

- 根级 workspace 改造
- 根级 lockfile 统一

这类事后面可以单独做，但不是这次迁移的关键路径。

### 5. 基础依赖原则

`platform-web-vue` 的依赖策略必须遵守一句话：

- 基座先最小可用，业务能力按需引入

这意味着：

- 不要一开始把 `sub2api` 全部依赖原样搬进来
- 只先装基座真正需要的依赖

## 三、依赖分层建议

### 1. 第一批必须有的运行时依赖

建议首批 runtime dependencies：

- `vue`
- `vue-router`
- `pinia`
- `axios`
- `vue-i18n`
- `@vueuse/core`
- `@tanstack/vue-virtual`
- `zod`

说明：

- `zod` 建议加入，用来做 env 校验和接口边界约束
- `@tanstack/vue-virtual` 直接为后面的 `threads`、大表格、长列表做准备

### 2. 第一批必须有的开发依赖

建议首批 devDependencies：

- `vite`
- `@vitejs/plugin-vue`
- `vite-plugin-checker`
- `typescript`
- `vue-tsc`
- `eslint`
- `typescript-eslint`
- `eslint-plugin-vue`
- `vitest`
- `@vue/test-utils`
- `jsdom`
- `tailwindcss@3.4.x`
- `postcss`
- `autoprefixer`
- `prettier`
- `prettier-plugin-tailwindcss`

### 3. 第一阶段不要急着装的依赖

这些依赖等业务真正需要时再加：

- `chart.js`
- `vue-chartjs`
- `xlsx`
- `qrcode`
- `driver.js`
- `file-saver`
- `marked`
- `dompurify`
- `vue-draggable-plus`

原因：

- 这些都不是新 app 起壳子的前置条件
- 先装一堆不用的东西，只会把依赖和升级面搞脏

## 四、脚本规范

## 1. 基础脚本必须齐全

`platform-web-vue` 的 `scripts` 建议至少包含：

```json
{
  "dev": "vite",
  "build": "vue-tsc --noEmit && vite build",
  "preview": "vite preview",
  "clean": "node -e \"const fs=require('node:fs');for(const dir of ['dist','coverage','.vite']){fs.rmSync(dir,{recursive:true,force:true,maxRetries:5,retryDelay:100});}\"",
  "lint": "eslint .",
  "lint:fix": "eslint . --fix",
  "typecheck": "vue-tsc --noEmit",
  "test": "vitest",
  "test:run": "vitest run",
  "test:coverage": "vitest run --coverage",
  "format": "prettier --write .",
  "format:check": "prettier --check .",
  "check": "pnpm lint && pnpm typecheck && pnpm build"
}
```

### 2. 为什么这样定

#### `dev`

只负责本地开发，不夹带其他行为。

不要把这些塞进去：

- 清缓存
- 自动改 env
- 自动跑迁移脚本

#### `build`

必须先 `typecheck` 再打包。

不要只写：

- `vite build`

因为那样很多 TS 问题会直接漏掉。

#### `clean`

建议保留 Node 版删除脚本，而不是纯 shell `rm -rf`。

原因：

- 路径更稳
- 后续跨平台兼容性更好

#### `check`

这是给开发阶段和提交前用的最小质量门禁。

含义就是：

- lint
- typecheck
- build

先把这三项跑通，才谈后面的业务迁移。

### 3. 第一阶段先不要加的脚本

这些脚本后面有真实用例再补：

- `e2e`
- `smoke:*`
- `analyze`
- `release:*`

不是说永远不要，而是：

- 基座没起来之前，不要先把脚本表做成垃圾堆

## 五、配置文件规范

`platform-web-vue` 第一阶段建议具备下面这些文件：

- `package.json`
- `pnpm-lock.yaml`
- `tsconfig.json`
- `tsconfig.node.json`
- `vite.config.ts`
- `vitest.config.ts`
- `eslint.config.js`
- `postcss.config.js`
- `tailwind.config.js`
- `.env.example`
- `.gitignore`

### 1. TS 配置

建议保持：

- `strict: true`
- `moduleResolution: bundler`
- `noEmit: true`
- `paths: { "@/*": ["./src/*"] }`

明确要求：

- 保持 `strict`
- 不为了快一点临时关掉类型规则

### 2. ESLint 配置

建议直接使用：

- Flat Config
- `eslint.config.js`

原因：

- 新 app 没必要再退回 `.eslintrc`
- 现有 `platform-web` 已经在用新配置方式

### 3. Tailwind 版本

第一阶段固定：

- `Tailwind CSS 3`

原因：

- 与 `sub2api` 的样式系统一致
- 能直接迁移 token 和样式类
- 避免在视觉迁移阶段叠加 Tailwind 4 兼容成本

## 六、环境变量规范

## 1. env 文件约定

建议固定为：

- `.env.example`：提交入库，作为唯一示例
- `.env.local`：本地私人配置，不提交
- `.env.production`：由部署环境注入，不提交到仓库

明确要求：

- 新 app 必须提交 `.env.example`
- 任何新加 env 都必须同步更新 `.env.example`

## 2. 环境变量命名规则

Vite 项目统一规则：

- 只有 `VITE_` 前缀的变量可在前端访问

这意味着：

- 不要把敏感密钥放进 `VITE_` 变量
- 不要再沿用 `NEXT_PUBLIC_*` 这套命名

### 3. 首批 env 清单

建议首批只保留下面这些：

| 变量名 | 必填 | 默认值 | 用途 |
| --- | --- | --- | --- |
| `VITE_APP_NAME` | 否 | `Platform Workspace` | 页面标题、页签、品牌文案 |
| `VITE_PLATFORM_API_URL` | 否 | `http://localhost:2024` | 平台后端基础地址 |
| `VITE_REQUEST_TIMEOUT_MS` | 否 | `30000` | Axios 超时时间 |
| `VITE_DEV_PORT` | 否 | `3000` | Vite 本地启动端口 |
| `VITE_DEV_PROXY_TARGET` | 否 | `http://localhost:2024` | 本地开发代理目标 |
| `VITE_LANGGRAPH_DEBUG_URL` | 否 | 空 | 仅用于少数调试工具，不作为业务主链路依赖 |

### 4. 明确不应该进入 env 的东西

下面这些不应该放进 env：

- `assistantId`
- `graphId`
- `projectId`
- 用户名密码
- testcase 页面当前筛选条件
- 文档预览格式选择

这些都属于：

- 运行时业务状态

不是：

- 部署配置

### 5. env 访问入口必须统一

不允许页面、组件到处直接写：

- `import.meta.env.xxx`

正确做法是：

- 新建 `src/config/env.ts`
- 在这里统一读取、校验、导出

建议模式：

- 用 `zod` 对 env 做一次解析
- 服务层和配置层只消费 `env.ts` 导出的值

这样做的好处：

- 变量缺失时能尽早报错
- 页面代码不会到处长环境变量分支
- 后面改名只改一处

## 七、接口地址规范

### 1. 平台接口地址

新 app 的平台接口地址建议统一收口到：

- `VITE_PLATFORM_API_URL`

默认本地开发值：

- `http://localhost:2024`

不要再同时并行维护：

- 一套 `NEXT_PUBLIC_PLATFORM_API_URL`
- 一套 `NEXT_PUBLIC_API_URL`
- 一套页面里手填的地址

### 2. LangGraph 访问规范

对 `chat`、`threads` 相关能力，默认策略建议是：

- 优先通过平台后端统一入口访问
- 不把 LangGraph 的 assistant/graph 选择写死在 env 里

这点非常重要，因为：

- 你前面已经明确 assistant/graph/id 是页面运行时选择
- 它们不是部署级固定配置

所以：

- `VITE_LANGGRAPH_DEBUG_URL` 只作为调试兜底
- 业务主链路仍然走平台上下文与页面选择

## 八、推荐的 `.env.example`

建议新 app 的 `.env.example` 初版至少长这样：

```dotenv
VITE_APP_NAME=Platform Workspace
VITE_PLATFORM_API_URL=http://localhost:2024
VITE_REQUEST_TIMEOUT_MS=30000
VITE_DEV_PORT=3000
VITE_DEV_PROXY_TARGET=http://localhost:2024
VITE_LANGGRAPH_DEBUG_URL=
```

## 九、Phase 1 初始化验收口径

只要 `platform-web-vue` 开始初始化，最少要同时满足下面这些点：

- `packageManager` 明确为 `pnpm@10.5.1`
- `engines.node` 明确为 `>=20.17.0 <23`
- `.env.example` 已提交
- `vite.config.ts`、`tsconfig.json`、`eslint.config.js`、`vitest.config.ts` 已齐
- `pnpm lint` 可跑
- `pnpm typecheck` 可跑
- `pnpm build` 可跑
- `pnpm check` 可跑

如果这些还没齐，就不能算初始化完成。

## 十、最终结论

`platform-web-vue` 的初始化规范可以压成一句话：

- 用 `pnpm@10.5.1 + Node 22 LTS`
- 用 `Vue 3 + Vite + Tailwind 3` 的最小基座起步
- 用 app 级 lockfile 管理依赖
- 用 `.env.example + src/config/env.ts` 管理配置
- 用 `lint + typecheck + build` 作为初始化阶段的最低门禁

这套东西先定死，后面迁移代码时才不会一边写页面一边补基础设施。
