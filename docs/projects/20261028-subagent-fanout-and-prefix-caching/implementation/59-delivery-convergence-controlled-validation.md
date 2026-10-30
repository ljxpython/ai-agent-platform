# 交付收敛后的独立烟测与冻结验证

2026-10-29。沿用已批准实现、原题/五项评分和真实模型测试授权。此处只记录 Phase；完整稳定性、泛化及 Final 未通过前不勾选依赖任务。

## v46 独立正式烟测

Thread `7849e092-4088-4ed7-80f5-5e682cd40ff3`，Run `cafac200-594b-4bc6-be9c-7e60ee9d75fe`。经正式 Web → API → Runtime，xiaok/kimi-k3、配置窗口 262144、输出 8192，原调用上限不变。终态 success；22/22 调用完整记账，finalized/available，missing/incomplete 均 0，费用限额关闭，价格未知。

| 检查 | 实际结果 |
| --- | --- |
| 原五项语义与引用 | 5/5：包分工；默认自动/手动整理与先剪枝；触发和重试；subagent 可选且 loop 外/多 provider；fresh、历史播种、进程内外和父发现 |
| 主级调用/累计输入 | 2 次 / 29,719 Token |
| 主单次输入峰值 | 17,570 Token，占配置窗口 6.70%；供应商实际窗口未报告 |
| 子级 | 3 个真实 code_explorer namespace，20 次调用、累计输入 210,877 Token |
| 全 Run | 输入 240,596 / 输出 16,070 / 合计 256,666 Token；缓存读取 164,864，不从窗口输入中扣除 |
| root 自动摘要 | 0 次；没有压力剪枝和成功 spill，不将零摘要解释成未限宽 |
| 来源 | 23 份固定 SHA/hash 核对；24 条文件行引用全部处于实际读取窗口 |
| 目录证据 | 原文件行解析器不能解析 Git tree URI，其失败保留；独立补充审计核实该不可变 tree，1/1 通过 |
| 交接/最终流 | 原文合并 896 字符，去重/真实工具窗口校验通过；程序渲染等于 checkpoint；唯一最终根消息与前端流一致，无原始 Schema 草稿泄漏 |

所属 Worktree `.local-stack/v46-delivery-smoke-22-terminal.json` SHA256 `43c37833c5e501be98ebdec14a9385c2dd73ab4eb7d3371b3b5eab31caca6d92`，逐项复核和审计保留为同前缀 `*-review.json`、`.audit.json`、`.sources.json`、`.source-fields.json`、`.directory-source-fields.json`、`.citation-windows.json`、`.handoff.json`、`.context.json`、`.live-final.json`、`.report-attempts.json`。这一次独立成功不替代三次稳定性。

## v47 六次对照预登记

清单 `.local-stack/relaxed-v47-manifest.json` 在首次模型提交前生成，登记时间 `2026-10-29T14:28:23.516001+00:00`，SHA256 `4a11a4a1a44644b89b7a3db20bf20e45c51f7eea73fcaa629c02c8f7167020d3`。冻结 1131 份公共文件、私有测试环境 hash、原题/来源 SHA、模型、窗口/输出、验证器和采集器。修正清单中继承的旧模型说明，当前配置以 Kimi 262144/8192 为准。

固定顺序为委派 1/2/3 → 串行 1/2/3，每次正式页面新建 Thread，上一 Run 终态后再启动；两臂仅 Pro delegation 布尔值不同。采集器 `collect-v47.py` 拒绝覆盖、保存提交意图，逐次核对来源/环境冻结和 Redis 快照；结果和失败全部保留，不补样。

委派三次均已终态 success，原五项核心语义均覆盖，完整质量按固定来源要求为 **2/3**；第二次保留了不属于固定提交的仓库元数据和两个仓库根 URL，不能算合格或以其他成功样本替补。

| 样本 / Run | 主调用 / 累计输入 / 单次峰值 | 全 Run Token | 耗时 / 质量 |
| --- | --- | --- | --- |
| 1 / `dc7534db-1276-48e8-8787-074b5eba0dcb` | 3 / 43,358 / 18,202 | 302,786 | 353.48s / 通过 |
| 2 / `99c663da-3fcb-4b15-935b-af8afc441f60` | 4 / 65,686 / 20,510 | 536,980 | 405.92s / 固定来源未过 |
| 3 / `7a97e713-54a7-4505-9dfa-e5d823559ed6` | 2 / 30,280 / 18,131 | 457,979 | 311.08s / 通过 |

三次均有三个真实 code_explorer namespace、完整 Usage、账本对平及 root 自动摘要 0，主峰值最高占配置窗口 7.82%。来源文件 hash、实际读取的文件行窗口、原文交接与唯一最终流均已审计；目录 URI 由独立补充验证器验证，原文件行解析失败不抹除。逐项人工评分保存于 `.local-stack/delegation-relaxed-v47-{1,2,3}-review.json`。第三次附加包清单把共享 driver 误列入 provider，后续专门一行澄清 driver 无 ctx key；保留这项表达矛盾，不把原五项外的展示问题暗中改成新评分项。

第二次问题子 namespace `tools:d688a798-0b66-9e0c-6ddf-e293edc53393` 的 26 次实际工具调用只传 owner/repo/start_line，缺 operation/ref/path。当前 `operation="info"` 默认值把缺参当作成功元数据查询；子报告所称“传了 file/readme/tree 和 ref，但工具返回 info”与捕获参数不符。主级补读了 compaction 契约，补齐核心语义，但不使裸仓库引用变成固定提交证据。待六次全部终态后，针对通用 operation 必填契约修复并重验；不在冻结组中途改应用、题目或额度。

委派采集器 exit 0 后，核对公共文件和环境无漂移，按登记 hash 仅将隔离 Worktree 的 Pro delegation 切为 false，重启所属 Runtime API/Worker。串行三次均 success，主累计输入 308,321 / 132,142 / 371,576、单次峰值 35,312 / 30,369 / 38,376，原五项评分 2/5、3/5、1/5，完整质量 0/3。缺失结论不从引文或子报告补分；串行首轮的五条本地来源别名未被固定解析器支持，失败保留，另有 13 条实际读过的不可变 GitHub 引用。

六次采集全部 exit 0 后核对 1131 份公共文件、环境、测试及验证器无漂移，按预登记 hash 恢复 Pro delegation=true；主目录始终为 true，随后才开始下一次修复。六次逐项审计与人工评分汇总为 [59-v47-controlled-comparison.json](59-v47-controlled-comparison.json)，SHA256 `b24e981eb2da074e9a2265af647c87ef8200b0b085638405af5a16b10f9d0ac7`。

| 全组中位数 | 委派 | 串行 |
| --- | --- | --- |
| 主累计输入 | 43,358 | 308,321 |
| 主单次输入峰值 | 18,202 | 35,312 |
| 全 Run Token（含子） | 457,979 | 317,313 |
| 耗时 | 353.48s | 305.61s |
| 完整质量 | 2/3 | 0/3 |

两组质量未对齐，不计算或宣称 25% 同质量输入降幅；主上下文减少不等于全 Run Token 或费用减少。provider 实际窗口及部署 fingerprint 未报告，费用缺价仍记 unknown。此组失败完整保留，不混入下一组。后续通用缺参修复见 [60号](60-github-operation-and-fixture-correction.md)；泛化与 Final 仍未通过。

## 并行自动化验证

69 份主目录相关 Python/TypeScript/Vue 文件与所属运行 Worktree 逐字一致（串行实验的模式布尔差异另行登记）。Runtime PostgreSQL checkpoint 集成使用本次自建临时原生 PostgreSQL，独立于现役库。

恢复 E2E 首次误用 `TOOL_ERROR_PLATFORM_NATIVE=1`，该模式要求调用者提供临时 PG/Redis，因缺 `POSTGRES_URI` 在夹具启动前失败，未执行应用断言。改用既有 `TOOL_ERROR_PLATFORM_TEST=1` 和该测试的 `RUNTIME_BACKEND=local` 参数；夹具自行创建原生临时 PG/Redis，无 Docker。第二次日志 `v46-native-recovery-e2e-2.log` 为 1 passed（350.13s）。API 预算/Usage 两文件为 37 passed、266 subtests passed（15.05s），日志 `v47-api-unit.log`。

- Web：157 套件通过、1 跳过；927 测试通过、1 跳过（181.65s）。lint exit 0（38 个既有 warning、0 error），含 vue-tsc 的构建 exit 0。日志 `v47-web-unit.log` / `v47-web-lint.log` / `v47-web-build.log`。
- Runtime 扩大：9 failed、651 passed、16 skipped（302.59s），日志 `v47-runtime-regression.log`，不能记为全绿。六项是 ResearchReport 测试夹具缺当前必填 overview；一项直接构造私有 state 缺 before_agent 实际设置的 owner；一项模型视图附有当前 Run 来源注册表，旧断言误将其整体当纯 JSON（持久 checkpoint JSON 未改）；最后一项未指定 local 而尝试默认 Docker。前三类夹具修正已准备，冻结组结束后应用并复验；不为迁就测试修改应用行为。
- 最后一项以 `RUNTIME_BACKEND=local` 独立复验：1 passed、5 warnings（6.88s），日志 `v47-local-approval-recheck.log`；未启动 Docker。
- 67 份 Python 修改文件 Ruff 通过；本地 Redis 启动探针 3 passed。

## 独立浏览器回放检查

使用独立 `subagent-final-verification` 上下文，不干扰采样浏览器。v46 历史报告语义锚点存在，Stop 在终态恢复后隐藏，无整理悬挂、无 pageerror；正式网关确认历史仍只有原先 1 个 success Run，无重发。390px 视口 document 宽度 390px，关闭历史侧栏后报告可见，人工查看 `.local-stack/v47-history-mobile-report.png` 已确认。桌面截图 `v47-history-desktop.png`，结果 `v47-history-browser-3-result.json`。

前两份浏览器检查脚本分别因等待 hydration 不足、误用 `/api/runtime/threads` 而失败，原产物保留；正确入口 `/api/langgraph/threads` 的第三份检查通过。此为 Phase 回放检查，不替代尚未开始的 Final。
