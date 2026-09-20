# 后端与 Runtime 实施记录

日期：2026-09-20。用户已批准实施后端及 Runtime；前端交由用户开发。

状态：本轮后端与 Runtime 开发及本地验证 done；前端、联合发布 deferred。

- `apps/platform-api/src/platform_api/modules/runtime_policies/`：删除旧工具策略，增加项目/用户禁用记录与管理接口。求值只读新表，不读工具 Catalog。
- `apps/platform-api/src/platform_api/core/security/tokens.py`：签发 delegation_version=2、false-only tool_overrides 和 tool_policy_version；网关每次具体操作按项目、用户、graph 求值。
- `apps/platform-api/migrations/versions/20260920_0002_runtime_tool_restrictions.py`：新表空初始化，旧白名单表退役；不转换旧数据、不支持恢复旧授权。
- `apps/runtime-service/src/runtime_service/runtime/{contracts,auth,resolver,capabilities,tool_access}.py`：Agent 代码声明、签名禁用、可用能力求交；删除 Context.tools 和 Catalog 白名单；新版配置哈希和快照。
- `apps/runtime-service/src/runtime_service/middlewares/runtime_config.py`：模型 schema、模型输出与实际 handler 共用有效工具集合，无 internal 绕过。
- `apps/runtime-service/src/runtime_service/http/`：Terminal/Skills/Memory/文件/图片按对应工具检查，保留资源 scope；终端关闭保留清理入口。

根因：旧实现将 Catalog 缓存作为工具授权来源，同时对默认 optional 工具全量校验，新增工具未同步就会阻断普通对话；internal 绕过又形成另一条权限路径。现在统一为 Runtime 声明与环境可用能力，减去平台签名禁用集合，schema、输出校验和 handler 共用结果。

补充修正：签发时同步数据库读取进入线程池；服务账号只应用项目规则；expected_scope 明确比较 operation，不能将读取委托用于副作用操作。

新增测试：`apps/platform-api/tests/test_tool_restrictions.py`、`apps/runtime-service/tests/runtime/test_tool_governance.py`；既有审计、鉴权、网关、Catalog、Dear 审批测试补齐新契约。Platform 阶段性全量 204 ran（7 skipped）；Runtime 分批结果及失败修复记录见 [验证记录](../06-validation-and-delivery.md)，不合计重复用例、不将 skip 计作通过。

前端未改动，交付契约及接入清单见 [前端交接](../frontend-handoff.md)。业务库 migration、联合部署及集群恢复演练尚未执行；无旧项目兼容或授权转换代码。
