# GitHub内容读取显式版本边界

## 改动时间
2026-10-29；任务T0.SHA。

## 背景与改动
v19有两个子调用漏ref，默认分支README已不同于用户固定提交。`apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/github.py` → `build_github_tool()`在公开仓库HTTP请求前拒绝file/readme/tree空白ref，不再回退默认分支。显式分支/标签仍可用于普通读取；不可变结论仍须提交SHA，工具不猜用户目标。

`apps/runtime-service/src/runtime_service/tools/errors.py`将内部invalid_github_ref映射到既有tool.invalid_input/not_started，并安全提示显式ref及原样使用用户提交；不返回异常原因或秘密字段。不新增公共错误码、接口字段或权限。

`skills/github-deep-research/SKILL.md`的readme/tree示例同步补ref占位，说明长文件query定位。主Agent与子Agent共用同一工具入口，不加只针对本题的分支。

## 测试与兼容性
- 新增file/readme/tree × 空/纯空格ref六例，断言网络零请求；新增安全纠错反馈测试。
- 路径校验仍优先拒绝无效路径；旧元数据查询、分页、README目录、固定ref/hash/namespace、远程证据元组、真实Agent装配均回归。
- 先红7 failed/67 deselected/5 warnings（10.34s）；相关组合136 passed/2 skipped/44 warnings（115.48s），四个本轮Python文件Ruff通过。
- 这是内容读取工具的有意约束收紧：旧的省略ref调用现返回可修正输入错误，元数据查询不变。所有仓库直接调用者已检索；现有有效内容测试已传显式ref，无需伪造默认值。
- 真实效果在v20独立模型组核验；未把合成测试当成质量通过。
