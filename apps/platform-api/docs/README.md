# 文档导航

这里不再维护“平铺式文件清单”，而是维护当前有效的阅读路径。

## 先读这些（当前权威）

1. `../README.md`
   - 项目身份、职责边界、快速启动、阅读入口
2. `docs/onboarding.md`
   - 新开发者上手路径、模块地图、常见改动落点
3. `docs/current-architecture.md`
   - 当前真实架构、活跃路由、请求链路、边界治理
4. `docs/local-dev.md`
   - 本地开发、环境文件、数据库、bootstrap admin、启动顺序
5. `docs/testing.md`
   - 当前测试层级、命令、环境要求、最小验收

## 按专题阅读（当前保留）

- `docs/postgres-operations.md`
  - PostgreSQL 容器、备份恢复、当前迁移口径
- `docs/error-playbook.md`
  - 常见错误与排查命令
- `docs/assistant-management-design.md`
  - Assistant 管理设计与接口落地稿
- `docs/runtime-object-catalog-design.md`
  - runtime 对象目录与平台主数据设计
- `docs/testcase-management-api.md`
  - testcase 管理接口、权限约束与 interaction-data-service 依赖链

## 文档约定

- 只有“当前实现仍然有效”的文档才保留在 `docs/`
- 已经过期、会误导开发者的文档已删除，不再保留 archive 入口
- 设计文档不再承担“当前真相”职责；当前行为以代码与 `docs/current-architecture.md` 为准
- 命令示例优先保证可直接复制执行
