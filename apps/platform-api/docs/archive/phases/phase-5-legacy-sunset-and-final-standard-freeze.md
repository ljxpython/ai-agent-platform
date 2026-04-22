# Platform API V2 Legacy Sunset 与 Final Standard Freeze

这份文档不再讨论“如何迁移得更平滑”，只讨论一件事：

> 如何把当前平台正式收口为一套可长期维护的最终标准。

最终口径已经定死：

- 正式前端只有 `apps/platform-web-vue`
- 正式控制面只有 `apps/platform-api-v2`
- `apps/runtime-service` 只负责 runtime plane
- `apps/platform-api` 退出正式链路，只保留历史参考价值

---

## 1. 最终目标

### 1.1 服务拓扑

```text
platform-web-vue
  -> platform-api-v2
       -> platform db
       -> runtime-service
       -> interaction-data-service
       -> future: redis / queue / object storage / oidc
```

### 1.2 最终态原则

- 登录、刷新、身份读取只走 `platform-api-v2`
- 项目、成员、用户、公告、审计、assistant、testcase、runtime catalog、runtime gateway 统一收口到 `platform-api-v2`
- 前端不再维护 `legacy/v2` 双 token、双 client、双项目上下文
- 页面组件不再感知“应该打哪个控制面”
- `runtime-service` 不承接平台主数据，不复制 control plane 逻辑
- 旧 `/_management/*` 只允许出现在历史参考代码，不允许继续出现在正式主链

### 1.3 最终交付标准

- 老板看到的是一套完整可演示的 Agent Platform Console
- 开发者拿到的是一套稳定的接口契约、模块规范和 Harness 工作流
- 后续接 PostgreSQL、Redis、对象存储、OIDC 时不需要推翻目录和模块边界

---

## 2. 明确删除的迁移期设计

这些设计只在迁移期有价值，最终态必须删除：

- `legacy` / `v2` 双 token 主逻辑
- `legacy` / `v2` 双 http client 主逻辑
- `resolvePlatformClientScope()` 这类“按模块猜当前走哪套控制面”的页面期分流
- `currentProjectId` 与 `runtimeProjectId` 双项目上下文并行
- 页面 service 中的 `mode: 'runtime'`、`mode: 'legacy'` 主分支
- 业务 service 中的 `/_management/*` fallback 主分支
- 启动正式演示时仍依赖 `2024` 旧控制面

允许保留的内容只有两类：

- 明确标注为 `reference / archive` 的历史代码
- 为数据迁移、联调排查准备的临时脚本，但不参与正式启动链路

---

## 3. 四个正式阶段

## Phase A: Legacy Sunset Baseline

目标：

- 让正式前端主链不再依赖旧 `platform-api`
- 把认证、项目上下文和主导航依赖切成单轨

范围：

- 登录 / refresh / logout / me
- 顶部项目切换器与工作区项目上下文
- `projects / members / users / announcements / audit / assistants / testcase / runtime catalog / runtime gateway` 的主 client 选择器
- 前端环境变量、demo 脚本、启动文档

执行项：

- [x] 登录改为只走 `POST /api/identity/session`
- [x] refresh 改为只走 `POST /api/identity/session/refresh`
- [x] 当前用户资料改为只走 `GET/PATCH /api/identity/me`
- [x] 前端 token 存储改为单 token 集合
- [x] `httpClient` 改为单一 `platform-api-v2` client
- [x] 去掉前端主链中的 `resolvePlatformClientScope()` 双分流
- [x] 去掉 `workspaceStore` 的双项目上下文，收口成单一 `projectId`
- [x] `WorkspaceProjectSwitcher` 只展示并切换 `platform-api-v2` 项目
- [x] 前端默认开发环境改到 `2142`
- [x] 正式 demo 脚本不再要求 `2024` 参与主链

Phase A 当前结果（完成于 2026-04-06）：

- `apps/platform-web-vue` 主链的 `/_management/*` 请求已从正式源码中清掉
- 本地 demo 已在不启动 `2024` 的情况下通过健康检查
- 浏览器 smoke 已验证登录、用户、项目、公告、审计、assistant 摘要都直接命中 `2142`

验收标准：

- 登录后任意正式页面不再发起 `http://localhost:2024/_management/*`
- 顶部项目切换、首页、chat、threads、assistants、projects、announcements、audit、testcase 可正常读取数据
- 关闭 `2024` 后，正式前端主链仍可工作

老板可见交付：

- 演示环境里旧控制面已经不再是前置依赖
- 前端进入任何核心页面不再出现 legacy 会话不一致问题

## Phase B: Control Plane Freeze

状态：

- [x] 已完成

目标：

- 把 `platform-api-v2` 固化成模块化单体的正式控制面
- 收掉“先能跑再说”的临时 service 设计

范围：

- identity
- iam / permission
- projects / members / users
- announcements / audit
- assistants / runtime catalog / runtime policies / runtime gateway
- testcase
- operations / platform config / service accounts

执行项：

- [x] 每个模块补齐 `domain / application / infra / presentation`
- [x] permission helper 与 route policy 全量校对
- [x] audit action / plane / target 枚举收口
- [x] DTO / schema / mapper 清理历史别名和临时字段
- [x] 统一错误码、分页、筛选、排序、搜索口径
- [x] 把平台正式页和治理页验收清单补齐

验收标准：

- 各模块职责边界稳定，入口层不再承接业务编排
- 权限、审计、分页和错误码在跨模块场景下表现一致
- 前端 service 不需要再写“临时兼容判断”

老板可见交付：

- 平台已经不是“能演示的壳”，而是“可持续开发的控制面底座”

## Phase C: Data & Delivery Freeze

状态：

- [x] 已完成

目标：

- 固化数据库、异步、交付和环境治理标准

范围：

- SQLite 开发基线
- PostgreSQL 生产基线
- Redis queue / worker
- Docker / compose / CI / release / backup / restore
- observability / probes / runbook

执行项：

- [x] 保持 SQLite 为默认开发库，明确 PostgreSQL 切主时机和迁移步骤
- [x] 固化 Redis queue 为可选生产后端，不影响本地单机开发
- [x] 完成 release / rollback / backup / restore 标准模板
- [x] 完成 health / probes / metrics / logs / tracing 标准文档
- [x] 完成部署参数、敏感配置、环境分层冻结

验收标准：

- 本地、dev、staging、prod 都有清晰启动与故障排查口径
- 切 PostgreSQL / Redis 时不需要改模块代码，只需要替换配置和基础设施

老板可见交付：

- 平台不仅能演示，还具备进入真实团队协作和持续交付的基础

## Phase D: Final Standard Freeze

状态：

- [x] 已完成

目标：

- 把最终开发范式、Harness、验收流程固化成团队标准

范围：

- README
- docs index
- harness playbook
- 模块 checklist
- 前端 examples / templates 使用规范

执行项：

- [x] 把“迁移说明”改写为“正式态规范”
- [x] README 明确正式前后端宿主与启动方式
- [x] 统一 AI / 人协作的 checklist、验收、提交和文档更新流程
- [x] 为新模块提供可复用样板和验收模板
- [x] 为前端页面开发给出 UI / 交互 / service / state / audit 的标准范式

验收标准：

- 后续开发者不需要再去翻旧项目猜做法
- AI 或人工接手时可以直接按 Harness 与 checklist 推进

老板可见交付：

- 这次重构沉淀成团队资产，而不是一次性的项目修修补补

Phase D 当前结果（完成于 2026-04-06）：

- 正式本地链路与正式端口已冻结
- 根 README、部署 contract、env matrix、本地联调说明已切到 `platform-api-v2`
- 已新增统一交付清单与模块交付模板
- 已新增前端控制面页面标准
- 后续开发不再需要回到旧 `platform-api` 猜正式口径

---

## 4. 最终前端范式

`apps/platform-web-vue` 的最终范式：

- 单一控制面 base URL：`platform-api-v2`
- 单一 token 生命周期
- 单一项目上下文
- service 按模块分包
- 页面只消费 service，不直接拼 URL
- 路由守卫只判断登录态和最小上下文，不再参与控制面分流
- 所有正式页面遵守同一套：
  - loading / empty / error 状态
  - 权限处理
  - 审计触发点
  - 组件壳层和视觉规范

建议目录目标：

```text
src/services/
  auth/
  identity/
  projects/
  users/
  announcements/
  audit/
  assistants/
  runtime/
  runtime-policies/
  runtime-gateway/
  testcase/
  operations/
  system/
```

---

## 5. 最终后端范式

`apps/platform-api-v2` 的最终范式：

- 模块化单体，不拆散 runtime plane 业务
- 入口层只处理协议和依赖装配
- application 层负责编排
- domain 层负责模型与规则
- infra 层负责数据库与外部系统
- presentation 层只暴露稳定契约
- 权限、审计、request context、observability 作为横切能力统一管理

模块边界固定为：

- control plane 在 `platform-api-v2`
- runtime plane 在 `runtime-service`
- 结果域在 `interaction-data-service`

---

## 6. Harness 最终范式

后续所有开发都按下面顺序执行：

1. 先写或更新 checklist / phase 文档
2. 再做最小可验证代码改动
3. 代码完成后补测试、手动验收路径和 runbook
4. 完成后回写文档勾选状态
5. 任何新模块都必须同步给出：
   - 服务边界
   - 权限点
   - 审计点
   - 前端 service 接入点
   - 手动验收方式

Harness 的核心不是“让 AI 一直写代码”，而是：

- 让 AI 和人共享同一套架构语义
- 让每次改动都有明确入口、边界、测试和验收
- 让后续功能开发可以沿用固定范式，而不是重新发明流程

---

## 7. 当前执行顺序

接下来按这个顺序推进，不再回到双轨思路：

1. 完成 `Phase A`，让正式前端主链脱离 `2024`
2. 完成 `Phase B`，冻结控制面模块边界和契约
3. 完成 `Phase C`，冻结数据、异步和交付标准
4. 完成 `Phase D`，冻结 README、Harness 和团队开发范式

当前 `Phase A / B / C / D` 已全部完成，旧控制面正式退出主链。
