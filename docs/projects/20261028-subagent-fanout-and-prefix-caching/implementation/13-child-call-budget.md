# 子任务调用额度与全局预算分离

## 改动时间与任务
2026-10-29；T0.N。

## 证据与原因
v12 使用225,701/1,000,000 Token，主峰值14.9%、整理0，但第三子在第8次末轮返回原始工具标记；compaction子也明确因预算耗尽放弃关键文档。全局预算与单子调用上限应分别约束，8次硬限制过早结束研究。不能仅靠更换模型或追加标准答案解决。

## 最小改动
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py` → `_build_agent()` 内的 `middleware()`：子Run/Thread模型上限由`min(8, base_limit)`调整为`min(16, base_limit)`，仍尊重更低的基础额度。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/subagents/code_explorer.py` → `code_explorer()`：已有额度说明同步为sixteen；没有追加目标路径、答案或研究维度。
- `apps/runtime-service/tests/services/dearflow_agent/test_agent.py`：核对Pro/Ultra两类子角色的额度、warning2与提示词一致。
- 私有`.local-stack/audit-sources.py`：仓库info元数据不作提交内容；file/readme/tree仍必须固定SHA，不放松证据校验。

## 验证
- 装配回归先红2 failed、22 deselected、5 warnings（17.17s）。
- DearFlow装配/Subagent边界/共享准入组合34 passed、1 skipped、33 warnings（74.15s），三份修改Python文件Ruff通过。
- 预警仍2次，最后调用禁工具、工具48、全局共享准入和原题不变；v13真实质量结果另记Phase，自动化通过不代表研究答案通过。
