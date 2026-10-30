# 固定提交文件内文字定位

## 改动时间
2026-10-29

## 相关任务
T0.A。

## 原因与实现
v18子任务顺次翻读长文档耗尽模型轮数。复用`apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/github.py` → `build_github_tool()`：file/readme新增可选query，256字符上限、拒绝控制字符，按casefold作逐行字面匹配，从start_line起定位首处；返回matched_line及附近原始行号。未命中明确match_found=false，不构造假文本窗口。query不发送给GitHub搜索，仍按固定ref取完整原文并复用原有证据hash/namespace；无query保持分页。max_lines与3000字符上限不变，前文过长时直接从匹配行开始。

工具说明与`subagents/code_explorer.py`通用角色提示要求优先定位相关段落，不注入本次仓库关键词、目标路径或评分答案。没有新增依赖或执行工具权限。

## 验证
`tests/services/dearflow_agent/skills/test_research_batch.py`覆盖Unicode casefold、字面方括号、后续匹配、未命中、参数前置拒绝、1行窗口与超长前文、原文hash及原分页。先红1 failed/23 deselected（11.42s）；修复联合Phase159 passed/1 skipped/62 warnings（53.15s），Ruff通过。真实质量待同版本对照。
