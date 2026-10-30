# 已批准范围内的短来源原句绑定

2026-10-29。关联T5.3/T5.6/T5.7。**代码及受影响回归通过；第十次独立正式烟测4/5，未过真实质量验收，继续34号校验反馈修复。** 授权依据为28号A项“必要的短来源原句可由当前已读窗口校验后绑定到结论……总限额4800”；不改变五项评分或调用预算。

## 原因

v30六次已完整保留，详见32号。确定性组合能保住已有字段，但无法挽回来源→结论时遗漏的限定；串行3还出现“确实读过正确来源，但支持该子句的行未被引用”。采用一段短原句保留直接依据，并验证原句和引用相符，不新增审稿模型或自动写入本题答案。

## 最小改动

应用源码仅在所属Worktree，下面路径以`apps/runtime-service/`为根：

- `src/runtime_service/services/dearflow_agent/subagents/report.py`：ResearchFinding增加兼容旧快照的`excerpt=""`，最多1200字符，仍计入子报告4800及父组合18000总限额。当前Run已读取GitHub正文后，非unknown结论需短原句；非GitHub格式沿既有约束。子报告的模型包装器在既有预算内反馈校验失败，不重新研究、不扩大16次额度。
- `subagents/source_quotes.py`：从本Run成功的github_query ToolMessage取不可变提交、文件和实际返回行；验证引用范围、原句（仅折叠空白）与实际文本相符。拒绝错误commit/path、未读或截断行、逆向/超大范围、翻译或改写的引句。不会读取本机参考仓库或向模型补充未读来源。
- `subagents/code_explorer.py`：统一要求短原句保留原文语言和限定，先删可选细节，额度不变。
- `middleware/synthesis.py`：父级additions同样校验，只看本Run新增消息，旧Run的来源不能充当新证据；子报告原句随其他字段原样渲染到“原文依据”列，HTML/换行继续由既有单元格转义处理。三并发、SDK执行/取消、权限和公共SSE/Usage协议保持现有实现。

新字段使用默认值兼容读取历史报告，不把旧Run重评为通过。验证用的来源只来自正式工具本轮已返回内容。因历史已被摘要而缺少可核验窗口时，不能伪称验证成功；应补回必要引用窗口或把未验证部分保留未知。该行为可能增加必要回读，须实测，不宣称对任意长任务无额外开销。

## 能证明与不能证明

原句匹配证明“引用这段文字确实在已读的固定来源中”，不能证明推论正确、核心事实已齐全或整个长引用都支持每个子句；任意子句的遗漏与错误仍按原五项人工检查。存在task而模型未调用的v30委派1也不会由此自动修复，不掩盖其门禁失败。

没有新增模型层、调度器或公开接口，不修改真实模型费用授权。仅在实现变更后独立烟测，再决定是否满足重建冻结组的前置条件；不能在原v30组里补成功样本。

## 验证计划与当前结果

- 通用哨兵：事件回放仅已完成事件、草稿私有，与DSH问题无关。
- 覆盖原句/固定URL/path:line/短SHA、错误文本/路径/commit/分支、未读/截断/错误工具结果、超大/逆向区间、父/子纠错在原预算内成功或失败、旧非GitHub格式兼容、原句计入4800限额。
- 最短组合40 passed；新增原句校验20 passed，集合有重叠、不累加。首次fake模型复制后重置响应索引导致1 failed，改为测试模型共享响应序列后通过，业务逻辑未因此放宽。
- 首次扩大回归5 failed/319 passed/54 skipped/1 deselected；五项均为旧子任务fixture未提供新必需excerpt。给原始大哨兵之前补一行短的通用限定、在报告绑定该行；大原始哨兵仍不得传父。边界复验13 passed/1 skipped。
- 修复后执行`uv run --frozen pytest tests/services/dearflow_agent tests/services/test_execution_budget_composition.py tests/services/test_model_resilience_composition.py tests/services/test_pii_composition.py -q -k "not docker"`：**324 passed、54 skipped、1 deselected、114 warnings，193.09秒，exit 0**。skip/deselected不算通过；没有启动Docker。Ruff与两个工作目录的`git diff --check`通过。失败及重跑日志分别保留在所属`.local-stack/v31-source-quote-*.log`。
- 已串行重启所属Runtime API/Worker并确认各服务就绪。第十次烟测前冻结1130份公共源码/配置/采集文件及4份相关测试hash，原题/固定SHA/模型/W131072/O8192/主50子16额度、环境hash不变。manifest为`.local-stack/v31-full-smoke-10-manifest.json`，SHA256 `e3585a8e174dfd9574f859f51aa9cd411e32a8ae2d60662a85242819358c3281`，07:37:10 UTC登记；独立烟测不混入v30或新的正式六次。
- 第十次终态与真实逐项结果见[34号记录](34-smoke10-and-validation-feedback.md)：48/48 Usage完整、总1277294 Token、主峰值29.10%、root摘要0、最终流一致，但仅一份子报告有效，原五项4/5。失败保留，不重建六次或启动泛化。Final尚未开始。
