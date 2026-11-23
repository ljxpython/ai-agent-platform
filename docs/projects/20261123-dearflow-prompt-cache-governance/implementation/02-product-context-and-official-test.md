# 临时动态上下文与官方小批验证

2026-11-23 用户批准按现有方案实施缓存优化，并用官方 URL 和 Key 替代中转站做少量对照。开发沿用分支 `feat/prompt-cache-experiments-20261123`、隔离环境 `wt_9b100adcf0ef`；本篇准备阶段当时没有修改主工作区业务源码、共享模型目录或正式服务，也没有提交、合并与部署。后续用户已确认并批准收尾，代码现已合入本地 main；所属测试环境已清理，不包含生产部署，现有脱敏数据仍可复算，见[清理核查](evidence/cleanup-verification.json)。

本文保存产品接线及准备经过，唯一进度仍在 [Task 7–8](../tasks.md)。后续用户已提供临时凭据，官方 16 次调用真实完成，零重试、无失败；结果与公开复算入口见[官方结果](03-official-results.md)。凭据仅进入执行进程，结束已移除并退出，本轮不再调用，用户可销毁。

## 实际请求怎样改变

改造前，构图时的 UTC 日期以及每次召回的个人记忆进入系统消息。改造后，主 Agent 基础系统规则不含这些动态值，静态说明两种上下文的来源与用途：

```text
System：基础规则、技能说明及本次允许工具的规则
已有历史消息
Human(name=runtime_date)：本次模型调用的 UTC 日期
Human(name=user_memory)：本次允许召回的最新记忆，非指令、非授权（为空或无权时不注入）
Human：当前真实用户原消息
本轮已发生的 Assistant 工具调用 / Tool 结果（如果有）
```

`middleware/dynamic_context.py` 只返回出站消息列表副本，把具名上下文插在最后一条真实 HumanMessage 前，不会挤进 Assistant/Tool 配对中。内部标记用于识别本工具生成的临时消息，不是身份、权限或授权凭据。原始用户消息及多模态块保持原对象，临时消息不写入 Agent state 或 Checkpoint，也不会被作为自动记忆来源。

`CurrentDateMiddleware` 在每次模型调用时计算 UTC 日期；同一个图跨天不用重新构建。`MemoryContextMiddleware` 仍使用原存储和权限链路，每次按真实用户查询召回，并在返回模型答案前再次检查共享状态；更正、删除、到期、共享、撤权及权限未知的现有行为保持。运行时维护/摘要专用路径跳过这两项注入，正常动态装配后继续经过 PII 和容量检查。

这次只改变主 Agent 原有的日期与记忆注入。子 Agent 原来没有该日期装配，未扩大其行为；图表 Schema 按需暴露、规范前置、审批、工具拒绝、工具输出裁剪和摘要保持。

涉及源码均位于 `apps/runtime-service/src/runtime_service/services/dearflow_agent/`：`agent.py`、`prompts.py`、`middleware/memory.py` 及新增的 `middleware/dynamic_context.py`。

官方付费执行前另外修改 `apps/runtime-service/src/runtime_service/runtime/modeling.py`：框架的 system 纯文本块数组在 DeepSeek 适配边界以空行合并为字符串，满足官方接口；原消息不变，普通字符串和 user 多模态保持，非文本 system 块拒绝。A/B 都走同一个生产适配器，重新冻结源码后再执行。对应两项建模序列化测试已纳入最终回归，没有先发送协议不符的付费请求。

## 少量官方对照

[官方接入说明](https://api-docs.deepseek.com/)在 2026-11-23 推荐 `deepseek-flash`，标明由 DeepSeek-V4.1-Flash-1017 提供服务；旧 Flash 别名仍接受但不代表旧版本仍运行。测试只使用 `https://api.deepseek.com` 的 Chat Completions、流式用量和显式非思考模式，不接 Anthropic，不改共享目录配置。

新增入口为 `apps/runtime-service/scripts/prompt_cache_official.py`，复用原捕获、执行、统计和费用算法。官方捕获与解析使用上述生产 `ChatDeepSeek` 适配器。Key 只从显式指定文件/变量读入内存；选定文件没有 Key 就失败，不回退到进程环境、Xiaok 目录或其他来源。本轮用关闭回显的输入向一次执行进程环境提供凭据，未创建密钥文件。HTTP 禁止自动跳转和自动重试；官方清单不能交给中转站连接执行。

- 固定历史回放：一组 AB，各四请求。前两次日期 2026-11-23、记忆 pytest，后两次模拟 2026-11-24、记忆 Vue；材料和历史固定，两项答案都检查。A 在工厂和记忆包装层恢复旧装配，B 直接捕获真实产品布局；静态文本归一化空白后相同，真实用户历史及工具相同，不声称整个请求字节相同。
- 完整任务：基线/优化各一个两轮任务，实际读取两份合成 CSV，均需算出 60，并回答本轮日期和偏好。除路径外，还检查真实工具结果成功且含 CSV 表头。正常每组四次模型调用，上限每组八次。
- 总量：正常约 16 次，上限 24 次；单并发、每次 120 秒、零重试。质量失败或真正的用量冲突即停止，不保证两组都能执行完，也不追样。调用前保存材料、布局、代码哈希和参数；准备后源码改变则拒绝直接执行旧清单。

两组有对称的 24 字符隔离标记，但无法清空或证明供应商缓存隔离。只有一个 AB 块，不宣称统计显著、严格冷启动或稳定收益。该捕获使用合成身份、记忆、空 custom/MCP 和受控上下文配置，不是三服务 E2E 或生产配置快照。

两批实际完成 8 次回放及 8 次完整任务模型调用，共 16 次；两组完整任务各两次真实读文件。回放断言各 4/4、完整任务两组断言均通过。读取比例分别为 52.66%→73.75%、53.63%→72.97%，标价估算分别下降 42.45%、37.55%；完整任务首正文中位数增加 31.01%，不能用缓存提高推导稳定加速。

## 用量与价格的边界

模拟官方原生响应只含 `prompt_cache_hit_tokens` 时，SDK 不一定把缓存读取透传到统一 metadata。实验同时保存原始用量与适配结果：原始用量有效、输入/输出一致而 SDK 缓存未知时，明确标记 `cache_normalization_matches=null` 和 `not_exposed_by_sdk; raw_native_cache_used`，仍按原始字段观测缓存；上报值冲突或用量不完整则停止。没有补零，没有伪造 SDK 透传，也未顺带修改生产账本。**实际官方 16 条响应同时提供原生与标准缓存字段，且与 SDK 结果全部一致**；模拟边界未在这批真实数据中发生。

[官方价格表](https://api-docs.deepseek.com/quick_start/pricing)当日列出峰谷价格。配置快照使用峰时每百万 Token：未缓存输入 0.30、缓存读取 0.006、输出 1.20 USD；谷时半价。峰时为 UTC 工作日 01:00–04:00、06:00–10:00，中国法定节假日除外。两组先用同一峰时价格估算，不把请求恰好跨时段当成优化收益。该快照复用费用算法所需的 `configured_catalog` 结构，另存官方出处；它不是读取共享模型目录得来的价格，也不是实际扣款证明。

Xiaok 的 97 次数据、1.8859788 USD 配置估算及全部负结果保持，不能和官方模型、价格或线路混成因果比较。旧公开数据已用新工具完全离线复算，与原 `summary.json` 逐项一致。

实际官方两批共计标价估算 0.022440552 USD，没有账户实扣证据。当前任务结果、耗时和源码见[官方公开数据](evidence/official-measurements.json)、[复算摘要](evidence/official-summary.json)与[九源码结构证据](evidence/official-product-layout-check.json)。

## 后续复现入口

本轮已结束，下列只说明有新的明确执行授权时如何复现，不能拿旧凭据继续请求。在所属 Worktree、独立依赖已就绪时，从仓库根运行。命令行只传文件路径或变量名，不传 Key 本身。文件应位于 Git 忽略的私有目录。以下 `--env-file` 必须由用户实际提供，不能凭空创建或填充凭据。

```bash
# 完全离线准备；输出文件必须尚不存在，父目录先就绪。
apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/prompt_cache_official.py prepare ".local-stack/cache-experiment/official-product-ready.json"

# 获取私有凭据后，执行固定八请求对照。
apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/prompt_cache_official.py replay ".local-stack/cache-experiment/official-replay" --manifest ".local-stack/cache-experiment/official-product-ready.json" --env-file ".local-stack/deepseek-official.env"

# 只有前一批质量/用量通过，继续各一个两轮完整任务。
apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/prompt_cache_official.py agent ".local-stack/cache-experiment/official-agent" --env-file ".local-stack/deepseek-official.env"
```

默认变量名 `DEEPSEEK_API_KEY`；也可用 `--key-env` 明确其他变量名。没有 `--env-file` 时只读当前进程环境。执行前核对冻结的模型/价格日期与源码；不得对旧准备文件强行绕过哈希检查。

## 验证与当前缺口

产品接线阶段回归为 158 项通过；加入生产序列化修正及完整官方边界后，最终相关回归 **180 passed、5 项既有 SWIG 弃用警告，62.55 秒**：

```bash
cd "apps/runtime-service"
.venv/bin/python -m pytest tests/runtime/test_modeling.py tests/scripts/test_prompt_cache_official.py tests/scripts/test_prompt_cache_experiment.py tests/services/dearflow_agent/test_dynamic_context.py tests/services/dearflow_agent/test_memory_contract.py tests/services/dearflow_agent/test_memory_access.py tests/services/dearflow_agent/test_memory_relevance.py tests/services/dearflow_agent/test_agent.py tests/middlewares/test_tool_output_pruning.py tests/middlewares/test_conversation_offloading.py tests/middlewares/test_pii_redaction.py -q
```

覆盖同图跨天和下一轮召回、六类记忆状态、前后权限、原消息不变、多模态与工具配对、Checkpoint 不含临时上下文、PII、维护模式、工具规范前置，以及官方入口的少量请求与真实本地 `read_file`。模拟模型和模拟用量只验证接线，不能充当官方读取率或任务质量数据。

首轮回归发现本次错误移除 `SystemMessage` 导入，影响记忆候选提取，已恢复；另一处测试误把系统内容块当字符串，已改为按真实块读取。新增原生字段夹具先触发缓存比较失败，随后区分了 SDK 未透传与真正冲突，最终回归包含这一分支。既有技能目录命名、空 custom 来源和 SDK transport 提醒未借机修改。

Phase 5 准备阶段的 Ruff、格式、文档及空白检查通过，当时七份 Markdown 的 65 处相对文件链接可达。原[八源码结构证据](evidence/product-layout-check.json)只代表那次离线稿，不能用其哈希核对当前实现；真实执行使用[九源码结构证据](evidence/official-product-layout-check.json)。当前复算及文档核查另见 [Phase 6](../verification.md#phase-6官方真实对照与文章证据task-82026-11-23)。

准备时曾因用户指定的官方变量为空而没有调用，已有 Xiaok 条目没有被擅用。用户随后提供临时凭据，先完成格式修正及清单重冻，再执行上述 16 次官方调用；不要将准备阶段的“官方调用 0”当成当前状态。旧 97 条数据复算保持。当前仍没有账户实扣、三服务真实 ACL、生产部署或人工最终验收结论，组合任务通过也不能覆盖旧日期单项失败和摘要截断。
