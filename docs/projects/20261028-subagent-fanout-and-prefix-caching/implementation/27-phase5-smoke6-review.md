# 第六次完整烟测：窗口达标，最终整合仍遗漏事实

## 样本与判定

2026-10-29，经所属隔离栈正式 Platform Web → API → Runtime 执行。Run `651df39e-5ebd-4b54-a6ed-c80d4ddfbf25`，Thread `6f8ae800-14c4-401d-bfac-955775710268`。这是独立烟测，不计入尚未冻结的正式六次，也不覆盖前五次失败。

模型为已登记 xiaok `deepseek-v4.1-flash`，配置窗口131,072、输出8,192；累计费用限额关闭，Usage开启，`token_budget=null`。上游部署fingerprint及价格仍未知。Run success、finish_reason stop，最终报告7,891字符；按原有完整事实评分为 **3/5，质量失败**。

| 原评分项 | 最终报告中的证据与缺口 | 判定 |
|---|---|---|
| 1 包目录能力族 | 第一节第1–3行给出共享契约/提供方/消费者分组、compaction basic与命令包，以及subagent注册服务/模型工具；引用`packages/compaction/README.md#L27-L33`、`packages/subagent/README.md#L25-L36`等固定提交文件。按跨行完整语义接受。 | 通过 |
| 2 compaction概述 | 第一节第4–5行与第二节覆盖`/compact`、随附基础配置默认启用、压力与可选剪枝，但没有明确陈述摘要作用于较早历史。不能用“选区间”、实现文件在引用中或列出的未知区间实现补足该结论。 | 不通过，部分命中 |
| 3 触发/剪枝/重试流程 | 第二节第1、3、6行覆盖请求派生前pre-step、仅规范overflow的request-error、先剪枝重测再摘要，以及replaceGeneration前进才重试；固定提交`compaction-basic/src/index.ts#L158-L176`、`#L319-L327`、`#L190-L234`等支持。 | 通过 |
| 4 subagent定位/共存 | 第一节第5行明确agent loop之外的可选能力，第三节第1行给出命名provider共存；报告引用的`docs/subsystems/subagent.md#L5-L7`支持这些事实。按跨行语义接受，不新增固定措辞要求。 | 通过 |
| 5 提供方/父级发现 | 第三节第1–2行给出fresh/fork历史播种和ACP/Codex/Claude/另一Harness形态，但最终未陈述父Agent可发现子级。provider registry的`list()`与父子通信均不能代替子级发现。 | 不通过，部分命中 |

包目录子报告第3条已明确“同一服务还承担continuable子代理编排、direct-child发现与递归后代发现”，却没有进入最终主报告。父级自己的GitHub调用还读取了`packages/compaction/README.md`与`packages/subagent/README.md`开头，包含较早历史摘要与父级发现原文。本次没有真实spill、展示截断或压力pruning，不能把遗漏归因于窗口容量不足或工具限宽；遗漏至少发生在已可见证据到最终答案的选择/整合环节。单次样本不能证明task描述修改独立造成了用量差异。

## 技术审计

| 指标 | 结果 |
|---|---|
| Usage | 35/35调用完整，finalized/available，逐调用与总账对平；无fallback |
| 主Agent | 8次；输入170,508、输出8,679；单次输入峰值29,218，即配置窗口的22.3% |
| 子Agent | 27次；输入515,417、输出28,569；峰值41,201；三个真实code_explorer，子工具仅github_query |
| 总量/耗时 | 输入685,925、输出37,248、总723,173 Token；310.425387秒；成本未知 |
| root自动摘要 | 0；观察到running/completed；SSE订阅尚未关闭不等于Run未结束 |
| 来源/引用 | 54份来源、其中47份子来源；固定SHA、正文hash、本地git blob审计通过。41个读取窗口覆盖39个去重引用；窗口覆盖不等于全部附加断言已核实 |
| 私有组成计量 | 35/35关联Usage；实际spill、展示限宽、压力pruning均0；来源不可辨识的注入与上游隐藏行为仍unknown |

原始文件为所属Worktree `.local-stack/v25-full-smoke-6-terminal-read.json`，SHA256 `da5a76084a5a1aff78f0ea38f2dac086695a4436515f4cc73619bf798fe7b253`；同名`.audit.json`、`.report.md`、`.context.json`、`.sources.json`、`.citation-windows.json`保留。没有重发任务或以成功样本替换失败。

## 本轮Docker边界

当前研究链路使用已登记的local隔离栈，不依赖Docker。补跑既有容器后端执行/超时/取消测试扩大了本轮范围，已停止这条补测尝试；不再启动、配置Docker或请求管理员授权。Docker Desktop曾尝试打开，但daemon未连通，没有启动测试容器；未确认GUI已退出。既有Docker专项保留未验证，不能用local测试冒充容器验证，也不将其作为继续当前调研链路的前置条件。

T5.3/T5.6及T3.2/T3.3仍未完成，正式六次与泛化、Final未开始；不宣称同质量25%降幅。下一步聚焦通用整合中的事实保留，不能注入原题答案、降低五项门槛或以扩大窗口替代质量修复。
