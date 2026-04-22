# Platform API V2 Phase B: Control Plane Freeze

这份文档对应 `phase-5` 里定义的：

> `Phase B: Control Plane Freeze`

它的目标不是“再多做几个页面”，而是把 `platform-api-v2` 真正冻结成一套能长期扩展的控制面标准。

---

## 1. 目标

Phase B 要完成四件事：

- 模块边界冻结
- 权限标准冻结
- 审计标准冻结
- DTO / 错误码冻结

冻结的意思不是“不许再改”，而是：

- 后续所有新功能只能沿着这套标准继续长
- 不允许再回到“先跑通再说”的散装模式

---

## 2. 执行范围

本阶段覆盖这些模块：

- `identity`
- `iam`
- `projects`
- `users`
- `announcements`
- `audit`
- `assistants`
- `runtime_catalog`
- `runtime_policies`
- `runtime_gateway`
- `testcase`
- `operations`
- `platform_config`
- `service_accounts`

---

## 3. P0 基线收口

- [x] `platform-web-vue` 主链已脱离 `2024`
- [x] `platform-api-v2` 成为唯一正式控制面
- [x] `platform-api-v2` 的公共错误响应完全统一
- [x] `platform-api-v2` 的公共 ID 解析与输入校验完全统一
- [x] `IAM policy deny` 失败码不再只有 `policy_denied`
- [x] adapter 不再直接向入口层抛 `HTTPException`

---

## 4. P1 模块边界冻结

- [x] 所有模块继续只保留 `domain / application / infra / presentation`
- [x] handler 不直接做业务编排
- [x] 外部系统错误只在 adapter 内映射
- [x] 跨模块数据组合只放在 application 层
- [x] 清掉各模块重复的 `_parse_uuid`
- [x] 重复 payload normalize helper 继续收口

验收标准：

- 新人看目录就能知道职责落点
- 公共逻辑不再复制粘贴进每个模块

---

## 5. P2 权限标准冻结

- [x] `IamPolicyEngine` 的 deny reason -> 显式错误码
- [x] 平台级权限、项目级权限在 service 层的调用口径统一
- [x] 缺 project scope、缺 platform role、缺 project role 的失败行为统一
- [x] 补齐 policy engine 的单测矩阵

验收标准：

- 权限失败时前端能看到稳定错误码
- `permission-standard.md` 中写的规则能在代码里直接对应到实现

---

## 6. P3 审计标准冻结

- [x] 审计 action 命名与 `audit-standard.md` 对齐
- [x] plane / target_type / target_id 的推导规则集中化
- [x] 失败 / 取消 / 成功的结果口径保持一致
- [x] 中间件只写审计上下文，不再混入业务兜底逻辑

验收标准：

- 审计数据能稳定回答“谁、何时、对哪个资源、做了什么、结果如何”
- action 命名不再出现新旧混杂

---

## 7. P4 DTO 与错误码冻结

- [x] 公共错误响应有统一 DTO
- [x] 公共成功响应继续扩到 `AckResponse` 之外的共享 schema
- [x] FastAPI 请求校验错误改成平台统一错误结构
- [x] 上游服务错误改成平台统一 envelope
- [x] `AckResponse` 之外的共享 response schema 继续补齐
- [x] 关键错误码建立回归测试

验收标准：

- 前端不需要为不同模块写不同错误解析分支
- 请求校验、业务错误、上游错误都落同一套 envelope

---

## 8. 当前执行顺序

本轮按下面顺序推进：

1. 先收 `公共错误响应 + UUID 解析 + adapter 异常映射`
2. 再收 `IAM policy` 显式错误码
3. 然后收 `audit middleware` 的 action / target 推导一致性
4. 最后补测试和文档勾选

---

## 9. 当前进展

2026-04-06 本轮完成：

- 已进入 `Phase B`
- 已完成 `P0 + P1 + P2 + P3 + P4` 的冻结收口
- 已新增公共层：
  - `core/errors/payload.py`
  - `core/identifiers.py`
  - `core/normalization.py`
- 已完成 adapter / middleware / policy / DTO 收口：
  - adapter 不再直接向入口层抛 `HTTPException`
  - `IamPolicyEngine` deny reason -> 显式错误码
  - `audit_log` 的 HTTP 推导逻辑集中到 `modules/audit/application/http_resolution.py`
  - `write_http_audit_event()` 收口为统一写入口
  - `OffsetPage[T]` 成为分页成功响应共享 schema
- 已补回归测试：
  - `tests/test_core_error_handling.py`
  - `tests/test_iam_policy_engine.py`
  - `tests/test_runtime_gateway_sdk_adapters.py`
  - `tests/test_audit_http_resolution.py`
  - `tests/test_phase6_normalization_regressions.py`
- 已验证：
  - `python3 -m compileall app`
  - `.venv/bin/python -m unittest discover -s tests`
- 当前结果：
  - 共 `34` 个单测通过
  - 请求校验、业务错误、上游错误统一落同一套错误 envelope
  - 分页成功响应开始统一到 `OffsetPage[T]`
  - 审计中间件职责收窄为“采集上下文 + 触发统一写入”
  - runtime gateway / testcase 的字符串清洗残留回归已补测试锁死

## 10. Phase B 结论

`Phase B: Control Plane Freeze` 到这里视为完成。

后续如果再开发新模块，必须遵守已经冻结的几条底线：

- 新模块继续按 `domain / application / infra / presentation` 四层落目录
- 错误码和错误 envelope 不得私自发散
- 分页类成功响应优先复用共享 schema
- 权限失败必须给出稳定错误码
- 审计 action / plane / target 继续沿用统一推导与写入入口
