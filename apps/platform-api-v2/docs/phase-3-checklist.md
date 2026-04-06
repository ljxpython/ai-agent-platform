# Platform API V2 第三阶段执行清单

这份清单接在 `phase-2-completion.md` 之后。

phase-3 的目标不是继续铺基础文档，而是把已经冻结好的边界真正推向“可持续演进”。

## P0 worker / queue 正式接入

- [x] 为 `operations` 增加 dispatcher / executor 抽象落地
- [x] 选定 Redis / queue 方案并完成最小 worker 进程
- [x] 把 `runtime refresh / assistant resync / testcase export` 至少接入一项真实异步执行
- [x] 为 operation 生命周期补齐真正的 started / succeeded / failed 审计联动

## P1 policy overlay 正式落库

- [x] 设计并落地项目级 runtime policy overlay 存储模型
- [x] 补齐 `models / tools / graphs` overlay 读取接口
- [x] 补齐 overlay 更新接口与权限校验
- [x] 在前端补第一版 policy 配置页

## P2 operations 前端治理页

- [x] 在 `platform-web-vue` 增加正式 operations 页面
- [x] 支持列表、详情、取消、状态徽标、错误载荷查看
- [x] 把 `runtime refresh / export / resync` 接到统一 operation 反馈流
- [x] 把 operation 详情与审计、资源详情建立跳转关系

## P3 PostgreSQL 正式切主

- [ ] 本地日常开发默认改用 PostgreSQL
- [ ] SQLite 只保留最小 smoke 口径
- [ ] 补齐新模块 migration 和升级回滚校验
- [ ] 输出 PostgreSQL 数据迁移与初始化脚本规范

## P4 平台配置与环境治理

- [x] 把 `platform-config` 从只读快照扩展成正式治理入口
- [x] 接入 feature flags 写入与读取
- [x] 补齐环境级配置的权限模型和审计动作
- [x] 前端增加运行环境 / 平台配置展示页

## P5 release / harness 收口

- [ ] 形成 phase-3 的 release checklist
- [x] 把 Harness 规范和阶段文档再压成开发者入口
- [x] 补齐 platform-api-v2 的 README 示例与常见问题
- [ ] 对前后端主要链路做一轮端到端演示回归
