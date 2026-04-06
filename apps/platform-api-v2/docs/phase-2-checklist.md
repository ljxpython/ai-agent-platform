# Platform API V2 第二阶段执行清单

这份清单承接 `phase-1-checklist.md`。

目标不是再重复“搭骨架”，而是把 `platform-api-v2 + platform-web-vue` 从“首批模块可跑”推进到“可持续开发、可持续验收、可持续演示”的稳定阶段。

维护规则：

- 只要进入第二阶段的工作，都先落到这张表
- 每做完一项，就在对应条目打钩
- 打钩前至少补齐一种验证：
  - 编译通过
  - 接口烟测通过
  - 前后端联调通过
  - 文档同步完成
- 如果范围变化，不改口头结论，直接改这张表

## P0 阶段目标冻结

- [x] 明确第二阶段继续以 `apps/platform-api-v2` 为唯一平台后端重构主战场
- [x] 明确第二阶段继续以 `apps/platform-web-vue` 为唯一正式平台前端宿主
- [x] 明确 `apps/runtime-service` 仍不纳入本阶段业务逻辑迁移
- [x] 明确第二阶段重点从“首批模块迁移”转为“平台治理能力补齐 + 运行工作台稳定化 + 数据基线切换准备”
- [x] 明确第二阶段所有新增开发继续遵守 Harness、模块边界、权限边界、审计边界

## P1 运行工作台稳定化

- [x] 梳理 `chat / threads / sql-agent / testcase-generate` 当前共享基座与差异点
- [x] 收敛 `runtime_gateway` 相关前端 service，避免页面层继续散落 runtime 细节
- [x] 统一 thread / run / stream / cancel / history 的页面态与错误态
- [x] 为聊天工作台补齐稳定的“加载中 / 中断 / 重试 / 空态 / 无权限”交互基线
- [x] 为 `sql-agent` 页面补齐正式的查询、上下文、结果与异常展示标准
- [x] 为 `testcase generate` 页面补齐和通用 chat 基座的一致验收口径
- [x] 完成运行工作台的一轮前后端联调回归

## P2 平台治理能力补齐

- [x] 设计 `operations` 模块目录、DTO、状态机与审计事件
- [x] 落地 `operations` 模块首版（提交 / 查询详情 / 取消 / 列表）
- [x] 明确哪些现有长动作要纳入 `operations`
- [x] 为 `assistants / runtime_catalog / testcase export / resync` 梳理可进入 operation 的动作清单
- [x] 设计平台级配置入口（系统配置 / 运行时接入配置 / feature flags）
- [x] 明确 `policy overlay` 在项目级的落点与后续模块接入方式
- [x] 为治理类模块补齐统一错误码和审计事件命名

## P3 数据与部署基线推进

- [x] 冻结 SQLite -> PostgreSQL 的切换前置条件
- [x] 梳理当前 `platform-api-v2` 已落表模块与迁移顺序
- [x] 建立 PostgreSQL 开发库初始化与升级验收步骤
- [x] 为现有模块补齐 Alembic 迁移基线
- [x] 设计 Redis / queue 接入点，但本阶段不强制落库
- [x] 明确异步 worker 接入 `operations` 的边界，不把业务逻辑直接写进 FastAPI 路由
- [x] 输出一版“本地开发 / 演示环境 / 未来生产”三套部署口径

## P4 前端继续迁移与收口

- [x] 盘点 `platform-web-vue` 仍未完全切到 `platform-api-v2` 的模块与页面
- [x] 为剩余未迁模块建立模块级 control plane 列表
- [x] 收敛 `platform-web-vue` 的 service 包目录，避免 legacy / v2 混用继续扩散
- [x] 为已迁模块补齐统一的 loading / empty / permission denied / error banner 模式
- [x] 为已迁模块补齐导出、复制、详情弹窗等高频交互的复用壳
- [x] 对 `projects / users / announcements / testcase` 做一轮 UI 与契约一致性回归
- [x] 更新前端迁移策略文档，明确“哪些已完成、哪些还在 phase-2”

## P5 验收与发布基线

- [x] 为 `platform-api-v2` 形成第二阶段 smoke checklist
- [x] 为 `platform-web-vue` 形成第二阶段 smoke checklist
- [x] 形成“本地演示可用”的账号、启动方式、联调依赖和验收口径
- [x] 为第二阶段新增模块补齐 README 与文档导航
- [x] 形成一版 release / tag / changelog 的执行草案
- [x] 明确哪些能力达到“可汇报”，哪些能力仍属于“开发中”
- [x] 在阶段结束时补一份 phase-2 完成记录，作为 phase-3 输入

## 当前建议执行顺序

1. 先做 `P1 运行工作台稳定化`
2. 再做 `P2 平台治理能力补齐`
3. 同步推进 `P4 前端继续迁移与收口`
4. 在模块稳定后推进 `P3 数据与部署基线`
5. 最后整理 `P5 验收与发布基线`
