# Delegation JWT - 开发任务

> 全部实施未开始。按J1→J2→J3→J4→J5→J6执行；不把文档完成勾成代码完成。每项完成后记录实际文件、命令、结果与限制。

## Phase 1：契约和平台修正

### J1 双端基线

- **状态：** [ ] 未开始。
- **改动内容：** 建立API签发→Runtime真实校验的子进程测试，覆盖固定23项operation和claim边界；先复现签发端已知差异。
- **代码位置：** 新建apps/platform-api/tests/test_runtime_delegation_contract.py；必要的子进程入口放apps/platform-api/tests/fixtures/runtime_delegation_verifier.py。Runtime原文件只读。
- **预期结果：** 不用mock验证器、不复制JWT校验实现、不让API生产依赖Runtime。
- **验证项：** C01—C05；API环境与Runtime环境版本写入证据；Runtime测试环境缺失时明确失败或未验证，不能无声skip后宣称通过。

### J2 签发输入收口

- **状态：** [ ] 未开始。
- **改动内容：** 按plan第3节收紧principal、permissions、非空模型、policy文本、scope类型/空值、credential_id；保留合法值归一化与v2输出。
- **代码位置：** apps/platform-api/src/platform_api/core/security/tokens.py::create_runtime_delegation_token / _runtime_names；apps/platform-api/tests/test_runtime_delegation.py。
- **预期结果：** 非法输入在签名前以ValueError拒绝；合法输出被现有Runtime接受；无模型哨兵行为保留，不改变TTL/算法/context_hash。
- **验证项：** C02—C06；类型、空白、长度边界、工具字节预算、service account缺凭据；现有测试中无凭据service account正例须改为合法凭据或明确负例，不删测试绕过。

### J3 两处工厂与安全失败

- **状态：** [ ] 未开始。
- **改动内容：** Catalog仅service account传actor.credential_id；Gateway初始/scoped及Catalog签发ValueError均走现有安全503，不泄露原文；请求工厂不跨HTTP缓存。
- **代码位置：** apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py::_runtime_headers；apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py::get_runtime_gateway_service / delegation_headers_factory；扩展test_runtime_catalog_delegation.py及网关测试。
- **预期结果：** 用户不带凭据，服务账号绑定当前凭据；项目/刷新权限保持，追踪关联字段按另一专项集成，已有用户改动保留。
- **验证项：** C06—C08；无上游调用的失败断言；初始与scoped两处签发都检查；错误专项公共映射回归。

## Phase 2：授权矩阵和真实验收

### J4 动作、身份和兼容矩阵

- **状态：** [ ] 未开始。
- **改动内容：** 给23项各做合法token、错误operation/资源对照；覆盖原生8项/自定义15项隔离、user/service account回查、context实际摘要。
- **代码位置：** apps/platform-api/tests/test_runtime_delegation_contract.py；扩展test_runtime_thread_authorization.py、test_service_account_project_grants.py、test_run_requests.py、test_thread_acl.py；Runtime现有auth/platform及自定义authorize作为只读对象。
- **预期结果：** 区分基础JWT接受与端点授权；不把kid当选钥；不把run_id加入scope；消息内部原生回查冲突单列证据，不扩大权限修复。
- **验证项：** C01、C05—C10；正例和每类资源错配；签发成功但实际端点失败不得标全绿。

### J5 真实生命周期及回退

- **状态：** [ ] 未开始。
- **改动内容：** 在已有隔离环境通过平台执行Run/SSE跨过委托exp，验证重连/审批/取消当前授权；验证前一API产物兼容。
- **代码位置：** 本专项verification.md及后续implementation/证据；必要的测试脚本仅放API测试目录，不改Runtime。
- **预期结果：** 生命周期符合已批准三条；无自动重发/取消；缺真实环境记录未验证；实际部署/回退执行需另外授权。
- **验证项：** R01—R05；记录版本、时间点、非敏感Run/请求ID；禁止token/secret写日志或文档。

### J6 最终交接

- **状态：** [ ] 未开始。
- **改动内容：** 同步本专项、父导航、CONTEXT/FEATURES及API相关正式规范；明确已知不兼容、真实验证缺项和API回退方式。
- **代码位置：** 本专项四文件；docs/projects/20260922-cross-service-governance/README.md；docs/CONTEXT.md；docs/FEATURES.md；API现有委托规范（按服务导航定位）。
- **预期结果：** Phase/Final分开；没有把方案就绪或mock通过记成已上线；Runtime/GraphHarbor零改动。
- **验证项：** 文档检查、相对链接、git diff --check、API测试与既有lint，核对范围和工作区既有修改。
