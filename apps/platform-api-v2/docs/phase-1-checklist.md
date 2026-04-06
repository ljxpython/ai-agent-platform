# Platform API V2 第一阶段执行清单

这份清单把当前第一阶段要做的事情收敛成一张总表。

## P0 规则冻结

- [x] 明确 `apps/platform-api-v2` 是新的正式控制面主战场
- [x] 明确 `apps/platform-api` 不再承接新功能开发
- [x] 明确 `apps/platform-web-vue` 继续作为唯一正式前端宿主
- [x] 明确 `apps/runtime-service` 不纳入本轮重构
- [x] 明确后续开发默认遵守 `platform-api-v2` 的工程标准与 Harness

## P1 骨架落地

- [x] 创建 `apps/platform-api-v2`
- [x] 创建基础 `FastAPI` 应用壳层
- [x] 创建 `core/modules/adapters/entrypoints` 顶层结构
- [x] 创建系统健康检查入口
- [x] 创建 v2 README 与文档导航
- [x] 增加统一错误模型
- [x] 增加 request context / actor context / project context
- [x] 增加 unit of work 抽象

## P2 规范落地

- [x] 编写目标架构文档
- [x] 编写工程标准与 Harness 文档
- [x] 编写前端切换策略
- [x] 编写权限标准文档
- [x] 编写审计标准文档
- [x] 编写 operation/job 标准文档
- [x] 编写 Harness Playbook

## P3 首批模块迁移准备

- [x] 设计 `identity` 模块目录与 DTO
- [x] 设计 `iam` 模块目录与权限 policy
- [x] 设计 `projects` 模块目录与 DTO
- [x] 设计 `announcements` 模块目录与 DTO
- [x] 设计 `audit` 模块目录与 DTO
- [x] 实现 `identity` 首个样板模块（login / refresh / logout / me / change-password）
- [x] 实现 `projects` 第二个样板模块（project / member / project-role scope）
- [x] 实现 `announcements` 第三个样板模块（admin/feed/read/scope）
- [x] 实现 `audit` 第四个样板模块（query / middleware / action-plane-target 标准）
- [x] 实现 `assistants` 第五个样板模块（project CRUD / resync / parameter schema / upstream adapter）
- [x] 实现 `runtime_gateway` 第六个样板模块（LangGraph 受控代理 / 项目边界 / 流式转发 / runtime plane 审计）
- [x] 实现 `runtime_catalog` 第七个样板模块（models / tools / graphs snapshot / refresh / 项目权限边界）

## P4 前端协同准备

- [x] 梳理 `platform-web-vue` 当前服务层结构
- [x] 确定第一批切换到 `v2` 的页面模块
- [x] 设计前端 `platform service client` 分模块结构
- [x] 接入 `legacy` / `v2` 双 token 与双 http client
- [x] 为 `runtime_gateway` 建立模块级 control plane 选择器
- [x] 为 `workspaceStore` 补齐 runtime 独立项目上下文
- [x] 让顶部项目切换器按页面路由切换 legacy / runtime 项目上下文
- [x] 让 `chat / threads / sql-agent / assistants` 使用 runtime 项目上下文
- [x] 让 `assistants` 与 `assistant graph` 读取链路支持显式 runtime 模式
- [x] 让 `assistants` 列表 / 详情 / 创建 / 更新 / 重同步 / 删除形成完整的 `v2` 前端写链路
- [x] 让 `overview` 页面中的助手摘要卡片改读 runtime assistants 上下文，避免总览页继续误读 legacy 助手目录
- [x] 让 `graphs` 页面与 `assistant create` 的 graph 目录优先读取 `platform-api-v2` 的 runtime graph catalog，并保留 legacy 兜底
- [x] 让 `runtime models / tools` 目录页切到 `platform-api-v2`
- [x] 让 `assistant create` 与 chat 运行参数读取 `platform-api-v2` 的 runtime models / tools 目录
- [x] 让 `runtime` 页面族接入 runtime 项目上下文，顶部项目切换与目录请求保持同一套 project scope
- [x] 让 `chat` 目标偏好补齐展示名链路，assistant / graph 入口与最近目标不再只显示原始 ID，并在缺失时由 `v2` 目录做受控兜底查询
- [x] 让 `threads` 页面与新建 thread 元数据补齐目标展示名，列表 / 详情 / Open in Chat 与 `chat` 目标表现保持一致
- [x] 让 `announcements` 管理页支持显式 runtime 模式，在 `v2` 打开时切到独立项目上下文并接通公告 CRUD
- [x] 让 `audit` 页面支持显式 runtime 模式，在 `v2` 打开时切到独立项目上下文并完成字段归一化
- [x] 让 `projects` 模块纳入模块级 control plane 选择器，`/workspace/projects*` 在 `v2` 打开时切到独立 runtime 项目上下文
- [x] 让 `projects` 列表 / 新建 / 详情 / 成员页支持显式 runtime 模式，形成完整的 `platform-api-v2` 项目管理前端链路
- [x] 让 `overview` 页面在 `v2` 打开时复用 runtime 项目上下文，项目摘要 / 审计摘要 / 助手摘要按模块 scope 切到 `platform-api-v2`
- [x] 让顶部 `AnnouncementCenter` feed 支持显式 runtime 模式，并接通 `platform-api-v2` 的 feed / 已读 / 全部已读链路
- [x] 让 `identity` 模块纳入模块级 control plane 选择器，并补齐 `PATCH /api/identity/me`
- [x] 让 `auth store / profile / security` 页面切到 `platform-api-v2` 的当前用户 / 改密 / 资料更新链路
- [x] 让 `users` 模块纳入模块级 control plane 选择器，并补齐 `GET/POST/PATCH /api/users*`
- [x] 让 `users` 列表 / 新建 / 详情 / 用户项目关系页支持显式 runtime 模式，形成完整的 `platform-api-v2` 用户管理前端链路
- [x] 让 `overview` 页面中的用户摘要卡片切到 `platform-api-v2` 的用户目录
- [x] 让 `projects` 成员页中的候选用户搜索复用 `platform-api-v2` 用户目录，避免 runtime 项目管理继续串回 legacy 用户接口
- [x] 让 `testcase` 模块纳入模块级 control plane 选择器，`/workspace/testcase*` 在 `v2` 打开时切到独立 runtime 项目上下文
- [x] 让 `testcase` 生成 / 用例 / 文档页面切到 `platform-api-v2`，接通 overview / role / batches / batch detail / cases / case detail / case create / case update / case delete / cases export / documents / document detail / documents export / relations / preview / download

## P5 验收基线

- [x] `platform-api-v2` 可以独立启动
- [x] 健康检查返回正确
- [x] 文档入口完整可读
- [x] 第一批模块迁移顺序和责任边界已拍板
- [x] `identity` 样板模块完成临时 SQLite 烟测
- [x] `projects` 样板模块完成临时 SQLite 烟测
- [x] `announcements` 样板模块完成临时 SQLite 烟测
- [x] `audit` 样板模块完成临时 SQLite 烟测
- [x] `assistants` 样板模块完成临时 SQLite 烟测
- [x] `runtime_gateway` 样板模块完成临时 SQLite 烟测
- [x] `runtime_catalog` 样板模块完成本地 LangGraph + SQLite 烟测（models / tools / graphs）
- [x] `platform-web-vue` 双控制面前端过渡基座已编译通过
- [x] `platform-web-vue` 已完成 runtime 项目上下文 + assistants/chat/threads 的本地端到端联调
- [x] `platform-web-vue` 已完成 runtime 页面 / graphs 页面 / assistant create / chat runtime 目录读取切到 `v2`
- [x] `platform-web-vue` 已完成 projects 页面族（列表 / 新建 / 详情 / 成员）切到 `platform-api-v2`
- [x] `platform-web-vue` 已完成 overview 摘要与顶部公告 feed 切到 `platform-api-v2`
- [x] `platform-web-vue` 已完成 auth store / 个人资料页 / 安全设置页切到 `platform-api-v2`
- [x] `platform-web-vue` 已完成 users 页面族与 overview 用户摘要切到 `platform-api-v2`
- [x] `platform-web-vue` 已完成 testcase 页面族切到 `platform-api-v2`，并补齐用例详情 / CRUD / 导出与文档导出 / 批次上下文
