# 材料变更保护、文件取证与真实评分验证

日期：2026-11-14。关联Task 1.4、2.3、3.0、3.2、4.2；仅344c两仓Worktree和合成资料。以下是阶段证据，不是联合Final。

## 这轮解决了什么

评测必须针对已经审核或已经评分的那份材料。本轮补齐三处检查：源导出编号没变但内容变了，旧批准不能继续发布；评分途中或写入重试时内容变了，旧分数不能发布；文件保护检查没有收齐原始文件证据时，不能判“文件都没改”。

用户另确认：评审人员暂时没有；模型使用`~/.my_best/.env`中的xiaok DeepSeek，本轮不设请求数和Token费用上限。已按此真实调用，保留运行超时、输入/输出和队列保护。没有启用生产采样，没有代替独立评审。

## 修复及失败复现

实际产品改动均在EvalFlow仓的`eval_platform/`、`tests/eval_platform/`，上游`mlflow/`未改。

| 场景 | 原问题及修复 | 实际验证 |
|---|---|---|
| 审核、发布、读取回流资料 | `curation.py`增加`validate_source`，比较源内容hash与接收记录；`dataset_registry.py`直接发布/冻结读取同样要求接收记录与源一致 | 2个内容变化负例先失败；修复后通过。原审核文件和冻结字节保持不变 |
| 两个审核人同时提交 | 使用现有版本号和文件锁；新增真实FastAPI路由并发测试，没有另造锁机制 | 两线程同时基于revision0提交批准/拒绝，恰好一个200、一个409；revision1且只保留一条审核。身份、原生审核和源接口为测试替身 |
| 评分后内容变了 | `inspection.py`在评分返回、原生写入及重试前核对hash；变化时终止并丢弃结果，不重新评分 | 3个负例先失败；修复后全部通过，原生写入未发生，后续tick不重放 |
| 只收到了部分原文件 | `targets/agent_platform.py`记录`checks.fixture_paths`；`scorers/agent_platform.py`核对v2每个fixture的实际初态，不能只遍历已有初态 | 2个缺失初态负例先失败；修复后通过。另测同内容别名、内容变更、终态缺失和错误初态 |

v1文件保护语义保留。旧v2历史证据若没有上传路径映射，新评分会报告`missing_protected_evidence`，不能凭缺失记录推定安全；应补可靠原始取证或在获准环境创建新的执行。历史报告不重写。

## 真实模型：调用成立，校准没有通过

从获准私有文件读取资源，没有输出密钥。只读查询xiaok模型列表，确认`deepseek-v4.1-flash`存在；返回字段没有context_length等上下文硬上限。因此`context_bound_verified`保持false，运行中的`sample_rate`仍为0。

在独立合成组件探针中复用巡检所用的`TaskCompletionMetric`和`XiaokJudge`，采用同样的保护：每样本3请求、累计输入32,000字节、累计输出8,192 Tokens、30秒。未调用`Inspection.tick`，未模拟源授权，未发布原生巡检结果。

| 样本 | 预先设定结果 | 实际分数 | 耗时 | 请求 / Tokens |
|---|---|---|---|---|
| 17+26，回答43 | 1 | **0.8，不一致** | 6.246秒 | 2 / 1,517 |
| 17+26，回答91 | 0 | 0 | 5.683秒 | 2 / 1,423 |

合计4请求、2,940 Tokens；两次评分都在运行限制内返回且用量完整。探针最终断言退出1，原因是正确答案未得预设满分。保留失败，不把预期改为0.8来补一个“通过”。这些数据不是误报率估计，也不足以批准发布阈值。

私有复核材料（EvalFlow Worktree）：

- `.local-stack/inspection-provider-metadata.json`
- `.local-stack/probe_inspection_judge_limits.py`
- `.local-stack/inspection-judge-limits-result.json`

完整自动巡检仍需网关路由硬上限证据；独立校准仍缺评审人。费用无上限的授权不等于已核实上述两项。

## 浏览器：真实带文件回归

使用`browser-skill`、浏览器实例`6848911c`的Agent标签页，EvalFlow Web9138 → API5011 → Agent API25087 → Runtime26645；已核对待测模型为Evaluation xiaok DeepSeek。仅一个合成文本文件，身份为现有非管理员`flywheel-reviewer`。

操作过程：

1. 页面导入1条v2开发用例，明确标注“自动化开发验证；非独立人审”。文件选择控件两次控制上下文失效后，确认页面仍为0条，再用页面自带JSON粘贴入口；没有重放导入请求。
2. 页面发布冻结版本，数据集`d-941ec8a7c00846a58555b8fe2378b15b`，版本1。这里的版本1是题库修订号，用例格式仍为v2。
3. 页面选择该版本及现有具名配置，创建任务`04a1f77a-4e53-4240-b10e-675d935e782b`；只提交一次。
4. 实际Agent读取上传文件，返回标记`fixture-check-344c-43`。报告记录了文件名→上传路径、初态和终态，内容一致；实际read_file执行事件及Runtime包指纹齐全。
5. 任务通过，4项规则均pass：completion、answer_contains、protected_unchanged、tool_constraints。Agent 2次模型调用、21,320 Tokens，规则评分未调用裁判。报告保留`budget_policy_not_configured`警告，不宣称正式G3预算验收。

原生结果Run：`21f38325aed043d09769d8624649b0f8`。业务Run：`05749647-4f10-4a11-a491-2792b07c7420`。Trace：`tr-78c9b7d9f7b09203545823ad845b2f50`。完整脱敏摘要位于EvalFlow `.local-stack/fixture-browser-result.json`。

截图：

- [旧回流资料在重启后被拒绝](39-review-source-guard-after-restart.png)：仅扩展页面拒绝。该旧实验仍有原生合成Trace，不当作批次撤权全链路证据。
- [开发题库冻结](40-fixture-development-frozen.png)。
- [前端选择版本与真实模型配置](41-fixture-regression-setup.png)。
- [创建回执等待中的页面](42-fixture-task-receipt-pending.png)：曾观察到任务已经完成、弹窗仍loading，后续自行收敛；没有重提交。
- [任务通过](43-fixture-regression-passed.png)。
- [原生结果四项规则均为1](44-fixture-four-rules-passed.png)。
- [原生详情中的合成输入、响应与评分](45-fixture-trace-response.png)。

服务重启期间实验页短暂显示INTERNAL_ERROR，恢复后重新读取正常。浏览器`read`能力被已安装的1.8协议拒绝，使用受支持的sync继续；未升级扩展或绕过用户控制。该轮没有测撤权、生产数据或独立人审。

## 自动测试与文档验证

全部命令在对应Worktree独立环境执行。日志保存在EvalFlow `.local-stack/`；下列数量有重叠，不能相加。

| 验证 | 结果 / 日志 |
|---|---|
| 回流源变化失败复现 | 2 failed；`phase-review-source-red.log` |
| 回流/发布/执行定向回归 | 27 passed；`phase-review-source-green.log` |
| 第一轮扩展全量 | 283 passed / 2 warnings；`phase-review-source-all.log` |
| 回流最终定向 | 15 passed；`phase-review-source-final.log` |
| 巡检材料变化失败复现 | 3 failed；`phase-inspection-source-red.log` |
| 巡检定向 | 24 passed；`phase-inspection-source-green.log` |
| 文件初态缺失失败复现 | 2 failed；`phase-protected-source-red.log` |
| 最终后端扩展全量 | **289 passed / 2 warnings**；`phase-source-and-inspection-all.log` |
| 9个改动Python文件Ruff | All checks passed |
| 专题03示例 | 2份JSON预检、20条v1读取、v2原生映射往返及正负规则检查通过；无模型调用 |

后端全量命令：`.venv/bin/python -m pytest --confcutdir="tests/eval_platform" tests/eval_platform -q --color=no`。两项warning仍为未知pytest timeout配置及Starlette WSGI弃用，未掩盖。文档验证摘要见`.local-stack/schema-doc-verification.json`。

Task 3.0的字段/能力说明范围完成；其他关联任务仅增加上述阶段证据。20个原合成候选仍全部待审，本轮的1条机械验证用例不是这20题的人审结果。没有新CI执行、默认前端构建或生产验证。
