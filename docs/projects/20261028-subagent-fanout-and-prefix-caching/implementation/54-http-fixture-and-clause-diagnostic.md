# HTTP夹具兼容与逐句证据诊断

2026-10-29，T5.2/T5.3/T5.7/T5.8的Phase验证，沿既有持续开发授权。

## 真实持久化链路夹具

`apps/runtime-service/tests/fixtures/tool_output_budget.py`适配现役overview报告与ResearchSynthesis：绑定实际schema名、找最后一条非System业务消息，复用现有compose测试helper；不再把结构化整合的nostream误记为自动摘要。原HTTP测试和所有权限/哨兵/重启/回退断言保持不变。

原夹具红测1 failed（390.87秒）：DearFlow子任务在旧报告格式/整合协议下进入error。修复后`TOOL_ERROR_PLATFORM_TEST=1 PLATFORM_API_TEST_PYTHON=<所属API Python> <所属Runtime Python> -m pytest tests/e2e/test_tool_output_budget.py -k large_result_http_restart_acl_and_rollback -q -x`得到1 passed（208.17秒），Ruff通过。使用测试自建原生临时PG/Redis和local后端，无Docker；仅适配测试，应用未变，不改变v42已冻结事实。日志所属`.local-stack/v42-http-fixture-{red,green}.log`，代码已逐字同步主目录。

## 固定材料诊断（独立于验收）

v42已判原质量4/5，具体错误保留于53号。首次发送前由`.local-stack/v43-clause-replay.py`登记清单，以其相同12项子发现、两段已读原文和原问题，对比原整合指令与通用逐句核对指令。最终答案排除；两臂仅最后通用指令不同，Schema/输出8192相同、每臂最多2次，无研究工具/新增材料/评分答案。候选要求核对claim和conditions的每个分句，发现矛盾或不支持时标争议/排除，并在已有证据支持时补充独立纠正版；不能因单个摘录匹配便接受整条断言。

诊断缺少正式动态中间件与工具，不代表平台验收或稳定性；全部请求/失败保留，不替补旧样本。登记`2026-10-29T13:00:16.615472+00:00`，实际3次请求：原指令1次、候选首轮重复finding_ref被拒、第二轮合法，但两臂均全部include、additions=[]，未修复v42的矛盾和引用支持缺口。因此候选未接入应用。清单/结果为所属`.local-stack/v43-clause-replay-{manifest,current,clauses}.json`。

随后在不改变应用/指令/Schema/材料的前提下登记独立模型诊断：已有maomaoai/deepseek-v4-pro和xiaok/deepseek-v4.1-flash，各最多2次，顺序执行，输出8192；`.local-stack/v44-model-replay-manifest.json`在首次调用前生成。只比较模型兼容性，不替补Kimi、不计正式组，结果待回填。
