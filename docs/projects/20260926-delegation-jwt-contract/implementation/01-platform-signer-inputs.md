# 平台签发输入阶段收口

2026-09-26，涉及 J2、J3 的部分实现。

`core/security/tokens.py::create_runtime_delegation_token` 在签名前拒绝非法 principal、permissions、空模型集合、超长/空白策略文本、无效 scope 值及缺当前凭据的 service account。正常 v2 claim、HS256、TTL 与上下文摘要不变。Gateway scoped 签发异常走现有安全 503；Catalog 按 actor 类型带当前 `credential_id`，并接收追踪专项当前请求的两个关联字段。Runtime 校验器及配置未修改。

`test_runtime_delegation.py` 18 项、`test_runtime_catalog_delegation.py` 15 项通过；旧的空模型正例夹具已改为合法模型，新增非法输入和 Catalog 凭据/关联断言。新增 `test_runtime_delegation_contract.py` 与只读校验 fixture：平台签发的23项operation在当前 Runtime 虚拟环境的现有校验器中通过，关联claim准确。claim拒绝矩阵、真实HTTP资源授权与跨委托到期点链路未执行，J1—J6尚不能标完成。
