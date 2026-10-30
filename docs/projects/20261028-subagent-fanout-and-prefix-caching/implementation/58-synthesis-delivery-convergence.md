# 主级交付纠错收敛

2026-10-29，T5.3/T5.7，沿用用户已批准的交付契约和持续开发/真实模型测试授权。

## 实现范围

56号六次冻结组全部终态、公共源码无漂移且Pro恢复后，才将57号候选接入所属隔离Worktree。仅修改`apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/synthesis.py`及其直接图测试，不新增协议、模型层或调用额度。

- `_retry()`以当前Run固定消息ID覆盖最新反馈，不逐轮追加；仍保留有界私有草稿用于纠错。
- `awrap_model_call()`在已尝试交付后的纠错阶段调用已有`disable_tool_calls()`，仅由SDK装配ResearchSynthesis Schema。若模型仍返回执行工具，整批拒绝，不能发生工具副作用。
- 进入新Run时重置交付阶段，模型视图排除旧Run纠错指令；历史checkpoint保留原事实。普通聊天、计划、手动整理、取消、费用/调用预算与原引用校验沿用。

## 验证中

正式测试先红3项：交付后读取工具仍暴露/可执行、相同反馈逐轮累积、下一Run看到旧纠错指令。原记录`.local-stack/v46-app-red.log`为3 failed/17 deselected（12.24秒）。

首次扩大63项中60 passed/3 failed：新测试错误从公开结果读取私有状态、两个直接请求夹具缺少实际before_agent必设的owner。修正为从checkpoint读取私有状态、在夹具显式设置owner；不为测试放宽应用边界。修正后63 passed/7 warnings（40.29秒），`.local-stack/v46-app-green-2.log`；此前私有候选的55项测试中1项因正式串行臂关闭Pro委派而失败，54项通过；保留记录，不把它算成最终Pro装配通过。Ruff通过。

三份修正已校验原始hash后同步主目录，记录`.local-stack/v46-source-integration.json`。所属Runtime API/Worker已按原配置重启，local后端，无Docker。

## 真实独立烟测预登记

xiaok已有kimi-k3，model ID `bcaf9543-5cc9-40cb-9848-d1fbe90cc086`，目录窗口262144、输出8192。固定原题/原SHA/五项评分、主50/子16、三并发、工具100、原文和报告上限、费用限额关闭、Usage开启。模型和窗口变化单列，不与maomaoai组混算。一次完整正式Web→API→Runtime新Thread；失败保留，非六次组替补。

调用前清单`.local-stack/v46-delivery-smoke-22-manifest.json`，登记`2026-10-29T14:17:58.055706+00:00`，SHA256 `18ae4afcaaf047ff164ac8296f7bf3ec69a2677b2e2b7064e4dda019bf6ada81`。来源/题/采集器与1131份公共文件均有hash；采集器`collect-v46-delivery-smoke.py`。已终态 success，原五项5/5，22/22用量完整、主峰17,570、自动摘要0；完整检查及后续冻结见[59号](59-delivery-convergence-controlled-validation.md)。

预算/隔离/Usage关联扩大124 passed、1 skipped、47 warnings（55.37s）；skip不当作通过。真实恢复E2E在原生临时PG/Redis、local后端下1 passed（350.13s），首次因误选外供基础设施模式缺少POSTGRES_URI的夹具错误单独保留，未修改应用绕过。
