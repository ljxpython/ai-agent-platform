# 双端契约与授权矩阵

2026-09-27；对应 J1—J4。平台签发器、Gateway scoped 安全出口和 Catalog 凭据传递已由先前工作树修改，本轮保留这些实现并补全可执行证据。

## 修改文件

- `apps/platform-api/tests/fixtures/runtime_delegation_verifier.py`：子进程使用当前 Runtime 虚拟环境的 `verify_delegation_claims`、`authenticate`、原生 `auth.on` 和自定义端点授权函数；只用受控响应代替 ACL 网络/存储边界，不复制校验实现、不输出token。
- `apps/platform-api/tests/test_runtime_delegation_contract.py`：23项operation接受；篡改签名、算法、issuer/audience、时间、版本、未知claim；空/实际context摘要；原生8项与自定义15项的正确/错误操作及Thread资源对照。缺Runtime环境即失败，不静默skip。
- `apps/platform-api/tests/test_runtime_delegation.py`：principal、permissions、policy文本、模型、scope与工具JSON 4096/4097字节边界；Gateway初始/scoped签发失败安全503；两次请求的关联字段和四个不同jti。
- `apps/platform-api/tests/test_runtime_catalog_delegation.py`：Catalog签发失败安全503且不访问上游。
- `apps/platform-api/tests/test_service_account_project_grants.py`：真实隔离数据库内拒绝把另一服务账号的凭据绑定到当前账号。

关键结果：API签发合法极值后当前Runtime校验器接受，非法输入在签名前由平台拒绝；Runtime HTTP认证仍强制audience。有效签名的缺失/不同kid被接受，符合现役Runtime不按kid选钥的事实，不构成轮换能力。自定义消息token在自定义入口通过操作检查，但进入内部原生Run读取会被原生 `auth.on` 以403拒绝；测试不扩大`read`权限。

测试命令、版本、通过数和未覆盖的实际业务路径见 `../verification.md`。Runtime/GraphHarbor文件、配置和依赖均未改。
