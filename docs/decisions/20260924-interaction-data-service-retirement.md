# 退役 interaction-data-service

- **日期：** 2026-09-24
- **状态：** 已批准并在本机完成；未来 Docker 部署由用户另行管理。
- **决策者：** 用户（2026-09-24 确认退役服务、现行文档/脚本和独占数据资源）。

## 背景

平台 Testcase 页面和 Platform API 适配器已于 2026-09-10 退役；三个现行应用的源码不再调用 `interaction-data-service`。旧服务仅维护 `test_case_documents` 和 `test_cases`，但整仓 Compose、建库脚本与现行文档仍把它作为活跃成员。当前成果页读取 `runtime-service` 的 workspace/artifacts，不依赖旧结果服务。

## 决策

删除 `apps/interaction-data-service/` 全目录及其 Compose、建库、环境示例和现行文档引用；不迁移或兼容旧 `/api/test-case-service/*`。目标环境中停旧实例并清理经核实独占的数据库、角色、附件卷和目录。旧服务无 Alembic 迁移链，自动建表/补列逻辑随服务源码删除；Platform API 和 Runtime 的数据库及迁移历史不在清理范围。

## 实施约束

实际数据库与卷名可被部署配置覆盖。环境清理先识别调用方、数据库/卷归属，验证备份可恢复，然后按对象清理；不得对共享 Compose 执行 `down --volumes`。本次目标仅为本机；未来 Docker 部署由用户另行管理。验证结果见[项目记录](../projects/20260924-interaction-data-service-retirement/README.md)。
