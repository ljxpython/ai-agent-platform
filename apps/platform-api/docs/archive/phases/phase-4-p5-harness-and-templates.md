# Phase 4 P5 - Harness 与开发者范式收口

这一阶段的目标不是再写一堆“看起来很规范”的废话，而是把已经验证过的开发方式收成可复用模板，让后续人和 AI 都别乱写。

## 1. 当前 Harness 入口

优先阅读：

1. `docs/README.md`
2. `docs/handbook/project-handbook.md`
3. `docs/handbook/development-playbook.md`
4. `docs/standards/permission-standard.md`
5. `docs/standards/audit-standard.md`
6. `docs/standards/operations-standard.md`
7. `docs/archive/phases/phase-4-checklist.md`

## 2. 已沉淀出的固定范式

### 后端模块范式

- route 只负责参数和依赖注入
- service/use case 负责业务编排
- repository 只负责持久化
- 权限检查统一走 policy engine
- 审计统一走 middleware + action 命名规范
- 长动作统一走 `operations`

### 前端控制面范式

- 页面不直接拼接后端 URL
- 请求统一走 service 层
- 类型统一进 `src/types/management.ts`
- 治理页优先展示“真实治理能力”，不是做静态说明页
- 能在 `platform-config`、`operations`、`runtime policies` 治理的能力，不再散落到临时页面

### AI 协作范式

- 先确认模块归属
- 再确认契约
- 再确认权限与审计
- 再决定是否进入 operation
- 最后才写代码

## 3. 新模块开发模板

新增模块前至少补齐：

1. 模块边界说明
2. 权限码
3. 审计动作
4. HTTP 契约
5. 最小单测
6. 前端 service 接入
7. 验收清单

## 4. 交付门槛

一个功能如果想算“进入控制面”，至少要满足：

- 有代码
- 有权限
- 有审计
- 有最小测试
- 有前端入口或明确治理页落点
- 有文档或 checklist 说明

## 5. 常见陷阱

- 把复杂逻辑重新塞回 route
- 新接口不补 permission code
- 审计动作乱起名
- 运行时执行逻辑和平台治理逻辑重新混到一起
- 前端直接临时拼 URL 或偷偷绕过 service 层

## 6. 适合下一轮继续沉淀的模板

- service account 正式治理页模板
- system probes/metrics 卡片模板
- 新模块脚手架模板
- “从 checklist 到验收”的 issue / PR 模板
