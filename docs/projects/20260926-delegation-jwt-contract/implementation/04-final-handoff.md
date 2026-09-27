# 平台范围交接与验证

2026-09-27；对应J6。未修改Runtime/GraphHarbor源码、配置、依赖或数据库结构；未迁移、部署、提交或建分支。

## 修改文件

- `apps/platform-api/src/platform_api/core/security/tokens.py`：`create_runtime_delegation_token`收紧v2签发输入。
- `apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py`：`_runtime_headers`传递当前服务账号凭据和关联字段，补齐`Mapping`导入。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`：scoped签发的`ValueError`走安全503；该文件还含其他专项既有工作树修改，本专项不覆盖。
- `apps/platform-api/tests/test_runtime_delegation.py`、`test_runtime_catalog_delegation.py`、`test_service_account_project_grants.py`：签发边界、安全出口及凭据归属测试。
- `apps/platform-api/tests/test_runtime_delegation_contract.py`与`tests/fixtures/runtime_delegation_verifier.py`：平台签发→当前Runtime真实校验/授权矩阵；子进程输入不通过命令行传token。
- `docs/projects/20260926-delegation-jwt-contract/`、`docs/projects/20260922-cross-service-governance/README.md`、`docs/CONTEXT.md`、`docs/FEATURES.md`、`apps/platform-api/docs/standards/runtime-gateway-interface-standard.md`：任务、阶段证据、正式契约和当前状态。

## 验证与限制

API全量pytest：299 passed、15 skipped、606 subtests passed；修改后相关定向pytest：21 passed、46 subtests passed。Runtime只读鉴权pytest：46 passed。两份新增测试文件完整Ruff和格式检查通过；相关文件的E4/E7/E9/F规则通过；文档检查及本专项范围`git diff --check`通过。

完整Ruff在8个相关既有文件上仍报148条，主要为FastAPI默认参数B008等既有格式基线；没有跨专项清理。全工作树`git diff --check`因无关Web SDK patch的制表符告警失败，本专项范围检查通过。真实R01—R04详见[生命周期记录](03-live-lifecycle.md)；最初`after_seconds=70`样本实际未延迟，未用作通过证据。消息自定义委托进入内部原生Run回查时当前Runtime返回403，属于独立兼容限制；本期保持拒绝，不扩签`read`权限或修改Runtime。
