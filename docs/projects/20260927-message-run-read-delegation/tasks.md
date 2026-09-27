# 消息内部 Run 回查委托修复任务

## Phase 1：契约与回归

### M1 配对委托测试
- **改动内容：** 固定消息入口与原生 Run 的正反矩阵，包含缺头、错 operation、错主体/项目/凭据/Thread及原生隔离。
- **代码位置：** `apps/platform-api/tests/test_runtime_delegation.py`；`apps/runtime-service/tests/services/test_message_inbox_postgres.py`或相邻测试。
- **预期结果：** 错配在内部 GET 前拒绝，合法配对仍由原生 ACL 决定。
- **验证项：** 两侧定向pytest。
- **状态：** [x] 完成。API签发头、Runtime配对与原生隔离矩阵通过；PostgreSQL HTTP拒绝场景确认无内部GET、无入队。

## Phase 2：实现

### M2 平台转发与 Runtime 校验
- **改动内容：** 仅消息请求转发本次已有 `read` 委托；Runtime 校验配对后用于内部 Run GET。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`；`apps/runtime-service/src/runtime_service/webapp.py`。
- **预期结果：** v2、原生白名单和 Thread ACL 不变；不新增签发或权限。
- **验证项：** API与Runtime定向pytest、lint及无敏感值输出断言。
- **状态：** [x] 完成。仅消息操作携带第二份已有委托；Runtime先验证再回查，v2与原生授权函数未改。

## Phase 3：链路与交接

### M3 验证与记录
- **改动内容：** 执行完整消息入队/列表链路，记录版本、结果、限制；同步原专项与功能状态。
- **代码位置：** 本项目 `verification.md`、`implementation/`、相关正式规范与 `docs/CONTEXT.md`、`docs/FEATURES.md`。
- **预期结果：** Phase和Final分开；现役链路缺环境或需部署时标未验证。
- **验证项：** 单元、集成、真实链路、文档检查、范围diff检查。
- **状态：** [x] 完成代码、自动化验证及交接记录；现役真实链路未验证，需另行部署新API与新Runtime后验收。

## Task Completion Cards

| Task | 结果 | 证据 | 限制 |
|---|---|---|---|
| M1 | 完成 | API定向21项；Runtime授权与配对42项；PostgreSQL HTTP拒绝/正例1项 | 原生HTTP真实ACL由后续链路验收 |
| M2 | 完成 | API组合31项、395 subtests；Runtime配对9项；Ruff致命规则通过 | `webapp.py`既有格式基线未整理 |
| M3 | 部分验证 | 本机真实PostgreSQL消息队列测试通过；Phase与Final分区记录 | 现役服务仍是旧进程，未获部署授权；真实跨服务链路未验证 |
