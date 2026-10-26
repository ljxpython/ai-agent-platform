# GitHub 调研工具与远程沙箱证据元组契约韧性治理 - 验证计划和记录

## 验证计划

### 单元测试
- [ ] `test_remote_evidence_returns_tuple`: 模拟 `RemoteWorkspace.call("research_evidence", ...)` 返回包含两个元素的 `list`，验证 `_evidence()` 返回值类型为 `tuple`，且 LangChain `tool.ainvoke()` 顺利通过无 `ValueError`。
- [ ] `test_github_query_with_token`: 验证在设置 `GITHUB_TOKEN` 环境变量时，`research_http.get_public()` 请求 `api.github.com` 的请求头正确携带 `Authorization: Bearer <token>`。
- [ ] `test_github_query_unauthorized_token`: 验证当 `GITHUB_TOKEN` 遭遇 401 响应时，系统能够稳定抛出受控的 `ToolException("research_rate_limited_or_forbidden")` 或相应标准错误码，不导致未捕获异常。
- [ ] `test_github_query_anonymous_fallback`: 验证未设置 `GITHUB_TOKEN` 时，仍然发起标准匿名请求，维持现有平滑兼容。

### 回归测试
- [ ] `apps/runtime-service/tests/tools/test_tool_errors.py`
- [ ] `apps/runtime-service/tests/services/dearflow_agent/skills/test_research_batch.py`

---

## 阶段验证记录

### Phase 1 验证
- **测试用例：** `test_remote_workspace_evidence_tuple_conversion_in_tool`
- **执行命令：** `apps/runtime-service/.venv/bin/pytest apps/runtime-service/tests/services/dearflow_agent/skills/test_research_batch.py -k test_remote_workspace_evidence_tuple_conversion_in_tool`
- **结果：** 通过（100% 绿灯）。验证了 RPC JSON 解码后返回的 list 在 `_evidence` 接收边界被防御性转换为 tuple，经由 LangChain 框架层解析时，`content_and_artifact` 元组契约严格成立，顺利生成 `ToolMessage`，彻底杜绝 `ValueError`。

### Phase 2 验证
- **测试用例：** `test_github_token_injection_and_unauthorized_mapping`
- **执行命令：** `apps/runtime-service/.venv/bin/pytest apps/runtime-service/tests/services/dearflow_agent/skills/test_research_batch.py -k test_github_token_injection_and_unauthorized_mapping`
- **结果：** 通过（100% 绿灯）。验证了设置 `GITHUB_TOKEN` 时注入 `Authorization: Bearer <token>`，设置 `GIT_TOKEN` 时平滑兼容，未设置 Token 时保持匿名请求，且 401 响应时安全捕获为受控异常。

---

## Final 验证记录与结论

### 综合验证执行
- **测试用例集：**
  - `apps/runtime-service/tests/tools/test_tool_errors.py` (35 items)
  - `apps/runtime-service/tests/services/dearflow_agent/skills/test_research_batch.py` (18 items)
- **执行命令：**
  `apps/runtime-service/.venv/bin/pytest apps/runtime-service/tests/tools/test_tool_errors.py apps/runtime-service/tests/services/dearflow_agent/skills/test_research_batch.py`
- **测试用例数：** 53 项
- **通过率：** 100% (53 passed, 6 warnings in 9.07s)
- **耗时：** 9.07s

### 完成度四态判定
- 最终判定：`done`（全量单测全绿，代码与环境配置均已落地，且真实 Token 经 GitHub API 验证额度 5000/hr 生效）
