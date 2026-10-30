# 目录README定位修复

## 时间与任务
2026-10-29，T0.H；真实质量仍归T3.2。

## 现象
v8完成但质量未过；来源轨迹三次传入readme子目录path，工具仍访问根/readme。来源hash是真实的，但内容来自错误位置，浪费调用并遗漏包概述。不能把读取位置错误当模型调研不足，也不能以更多提示词掩盖。

## 修改
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/github.py` → `build_github_tool()`：readme独立分支，path解释为目录，访问`readme/{directory}`；空path保留根README；ref直接透传，目录路径继续原有校验和URL编码。工具说明明确目录path与file精确路径的区别。来源记录、哈希、namespace及输出行窗口复用原逻辑。
- `apps/runtime-service/tests/services/dearflow_agent/skills/test_research_batch.py`：根目录、嵌套目录及带空格目录3组回归，核对请求URL/ref、返回路径及子namespace。修复前3组均失败（旧根请求多带无关分页参数，子目录还丢失path）；修复不扩大权限。
- 私有来源审计额外输出`all_requested_readme_directories_match`，不因哈希正确就默认请求位置正确；v8回放为false，保留三处不匹配，不覆盖失败。

## 真实只读探针
本Worktree实际工具读取固定公开SHA的根、packages/compaction、packages/subagent，三者returned_path均位于目标目录；内容hash、固定提交原文及namespace全部匹配。证据`.local-stack/phase-v9-readme-live.json`。此探针不是正式模型对照，T3.2仍需原题两组三次。

## 定向门禁与新登记
GitHub/研究/Subagent/循环/工具错误组合135 passed、2 skipped、40 warnings（101.29s），Ruff与diff检查通过。v9公共源码22份，manifest SHA256 `c1e49666354bbf345a37cbe216d769eb0e5a55b99670dbefd1631304ab43cdda`；原题正式模型对照已启动，尚未验收通过。
