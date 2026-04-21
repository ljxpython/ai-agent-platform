# 16. 烟测与验收清单

## 目标

这份清单用于固定 `apps/platform-web-vue` 的最小可复现验收方式。

只要这份清单能稳定通过，就说明当前迁移成果已经具备：

- 可登录
- 可演示
- 可回归

## 一、命令级校验

在仓库根目录执行：

```bash
pnpm --dir "apps/platform-web-vue" lint
pnpm --dir "apps/platform-web-vue" typecheck
pnpm --dir "apps/platform-web-vue" build
```

通过标准：

- `eslint` 无报错
- `vue-tsc` 无报错
- `vite build` 成功

## 二、账号校验

固定校验账号：

- `admin / admin123456`

补充说明：

- 当前正式实现只保证 bootstrap 管理员账号
- 普通账号如果要纳入演示验证，需要先确认本地数据里确实存在该用户及其密码口径
- 不再把固定 `test` 账号视为当前 release 的必选前置条件

接口校验方式：

```bash
curl -X POST "http://127.0.0.1:2142/api/identity/session" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123456"}'
```

通过标准：

- `admin / admin123456` 返回 `200`
- 如果本地额外准备了普通账号，则该账号也应返回 `200`

## 三、关键页面烟测

### 必测路由

- `/workspace/overview`
- `/workspace/projects`
- `/workspace/assistants`
- `/workspace/sql-agent`
- `/workspace/chat`
- `/workspace/threads`
- `/workspace/testcase/generate`
- `/workspace/testcase/cases`
- `/workspace/testcase/documents`
- `/workspace/announcements`
- `/workspace/resources`
- `/workspace/resources/playbook`

### 通过标准

每个路由至少满足下面条件：

- 页面能进入
- 主内容区有可见内容
- 没有关键白屏
- 没有把用户卡死在 loading

## 四、关键交互验收

### 登录

- 默认用户名密码登录可直接进入 `/workspace/overview`
- 登录后不会停留在 `/auth/login`

### 顶栏系统区

- 项目切换器能展开
- 语言切换器能展开
- 公告中心能展开
- 用户菜单能展开

### Chat / SQL Agent

- 可进入工作台
- 会话列表默认折叠
- 运行上下文与参数在独立弹层中
- ToDo / Files / Tool Call / Artifact 可见
- 中断 / Continue / Debug 入口存在

### Threads

- 线程页进入后先展示列表
- 点中某个 thread 后再加载详情，不再整页一次性展开

### Testcase

- `generate / cases / documents` 三个二级页都能进入
- `documents` 支持在线预览与原始下载主链路

### 平台管理页

- `projects / users / announcements / audit` 可正常进入
- 列表页分页、列设置、筛选设置、排序、操作菜单能展开

## 五、响应式与主题验收

### 响应式

手机宽度重点复查：

- `/workspace/testcase/documents`
- `/workspace/testcase/cases`
- `/workspace/threads`
- `/workspace/chat`
- `/workspace/projects`

大屏重点复查：

- `/workspace/overview`
- `/workspace/projects`
- `/workspace/threads`
- `/workspace/chat`
- `/workspace/resources/playbook`

通过标准：

- 无横向溢出
- 顶栏可换行
- 筛选栏和操作区可换行
- 对话区、线程区、弹层不截断

### 主题

重点复查：

- `html.dark` 与 `data-theme-mode=dark` 同步
- `button / input / table tool button / dropdown / dialog` 不出现白底穿帮

## 六、截至 2026-04-05 的已验证结果

### 命令结果

- `pnpm --dir apps/platform-web-vue lint` 通过
- `pnpm --dir apps/platform-web-vue build` 通过

### 浏览器烟测结果

已实际走通：

- `/workspace/overview`
- `/workspace/projects`
- `/workspace/assistants`
- `/workspace/sql-agent`
- `/workspace/chat`
- `/workspace/threads`
- `/workspace/testcase/generate`
- `/workspace/testcase/cases`
- `/workspace/testcase/documents`
- `/workspace/announcements`
- `/workspace/resources`
- `/workspace/resources/playbook`

结论：

- 均可进入
- 均存在主内容区文本
- 未出现关键白屏

### 账号结果

- `admin / admin123456` 通过 `POST /api/identity/session` 返回 `200`
- 普通账号是否可用取决于当前本地 seed 数据，不再把固定 `test` 账号作为默认通过条件

### 主题与响应式结果

- dark mode 正式路径已复查
- 关键页面在手机与大屏下已复查横向溢出问题

## 七、已知非阻塞项

- `apps/platform-web-sub2api-base/.git` 嵌套仓库边界仍未清理，这是仓库整理项，不阻塞当前演示
- Node `25.x` 仍会触发 engine warning，正式建议使用 `20 LTS` 或 `22 LTS`

## 八、最终验收结论模板

如果上面条目全部通过，对外统一结论可以写成：

> `apps/platform-web` 的正式页面与核心链路已迁入 `apps/platform-web-vue`，当前演示环境可稳定完成登录、agent 工作台、testcase 工作区、线程页和平台管理页展示；剩余风险已收敛为非主链路项与仓库整理项。
