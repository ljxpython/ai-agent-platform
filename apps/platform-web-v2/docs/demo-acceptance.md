# Platform Web V2 演示与验收说明

更新时间：2026-04-02

## 1. 演示环境

- 前端目录：`apps/platform-web-v2`
- Node 版本：`20.17.0`
- 平台 API：`http://127.0.0.1:2024`
- LangGraph Dev：`http://127.0.0.1:8123`
- 生产演示地址：`http://127.0.0.1:3103`

建议启动方式：

```bash
source "$HOME/.nvm/nvm.sh"
nvm use 20.17.0
cd apps/platform-web-v2
LANGGRAPH_API_URL=http://127.0.0.1:8123 NEXT_PUBLIC_PLATFORM_API_URL=http://127.0.0.1:2024 pnpm start --hostname 127.0.0.1 --port 3103
```

## 2. 演示账号

- 管理员：`admin / admin123456`
- 普通账号：`test / test`

说明：

- `test` 已挂到现有项目 `测试3`
- 普通账号顶部上下文条会显示真实的 `member` 身份
- 审计页只对管理员开放，普通账号进入时会直接显示权限说明，不再打出一堆 `403`

## 3. 建议演示顺序

优先级按老板关注点整理：

1. `SQL Agent`
2. `Threads / Chat`
3. `Testcase`
4. `Projects / Users / Assistants`
5. `Me / Security / Audit`

建议实际演示路径：

1. 管理员登录 `admin / admin123456`
2. 打开 `/workspace/sql-agent`，直接发送 `hello`
3. 展示左侧主导航、顶部上下文条、主题切换
4. 展示 `/workspace/threads`、`/workspace/chat`
5. 展示 `/workspace/testcase/generate`、`/workspace/testcase/cases`
6. 展示 `/workspace/projects` 的项目切换，再进入 `/workspace/assistants`
7. 如需补充账号视角，再登录 `test / test`

## 4. 自动化验收脚本

全部在 `apps/platform-web-v2/tests` 下。

基础工作区烟测：

```bash
SMOKE_BASE_URL=http://127.0.0.1:3103 pnpm smoke:workspace
```

SQL Agent 实聊烟测：

```bash
SMOKE_BASE_URL=http://127.0.0.1:3103 pnpm smoke:sql-agent
```

项目切换链路：

```bash
SMOKE_BASE_URL=http://127.0.0.1:3103 pnpm smoke:project-switch
```

管理 CRUD 验收：

```bash
SMOKE_BASE_URL=http://127.0.0.1:3103 pnpm smoke:management-crud
```

普通账号工作区烟测：

```bash
SMOKE_BASE_URL=http://127.0.0.1:3103 SMOKE_USERNAME=test SMOKE_PASSWORD=test pnpm smoke:workspace
```

说明：

- `smoke:management-crud` 会创建一个 `smoke_*` 测试用户，并把它加入当前项目
- 这个脚本用于确认 `用户创建 -> 状态切换 -> 项目成员绑定 -> 普通用户登录` 的闭环

## 5. 本轮已验收结果

已通过：

- 管理员登录链路
- 普通账号登录链路
- `overview / me / security / assistants / chat / sql-agent / threads / testcase / audit` 页面打开
- `sql-agent` 实际对话成功返回数据库表信息
- 顶部项目切换可生效，并能带到后续页面
- 管理员可创建用户、切换用户状态、将用户加入项目
- 新创建普通用户可直接登录 v2 工作台
- 顶部上下文条已显示真实账号与角色，不再写死 `Role: admin`
- 普通账号访问 `audit` 不再持续触发 `403`

保留项：

- 默认主题的最终视觉评审还需要你和老板现场拍板

## 6. 当前结论

从技术验收口径看，`platform-web-v2` 已经达到替代旧 `platform-web` 的条件。

剩下主要是展示和视觉拍板，不再是功能迁移阻塞。
