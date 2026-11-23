# 实验工具、运行结果与复核入口

本记录服务于[原任务](../tasks.md)，不另维护任务进度，仅保存首轮 Xiaok 实验事实。2026-11-23 在用户要求的独立 Worktree 开发实验工具、完成 97 次 Xiaok 真实调用并撰写文章；首轮当时没有修改 `src/runtime_service/` 生产源码。后续获准的[产品接线](02-product-context-and-official-test.md)和[官方 16 次结果](03-official-results.md)另行记录，不用本篇历史阶段说明代表当前源码。

**当前保留范围：** 用户已确认结果并批准合并和清理；代码已合入本地 main，本环境数据库和 `.local-stack/` 私有材料已销毁。下文私有批次路径与 `report` 命令为历史运行说明，不再指向仍存在的原批次；现有脱敏公开数据仍支持 `recompute` 离线复算，清理核查见[所属环境记录](evidence/cleanup-verification.json)。

## 环境和接线

- Git 基线 `6884f10e`，分支 `feat/prompt-cache-experiments-20261123`，环境 `wt_9b100adcf0ef`。独立依赖、双库迁移、种子导入和 doctor 已执行；没有启动全栈应用服务。
- 目录模型 ID `070cced3-350b-42ec-b678-994dd07b7078`，provider=`xiaok`，协议=`openai-compatible`，请求与返回 model=`deepseek-v4.1-flash`，主机 `xiaok.lol`。
- 连接指纹 `a4933b44f0a644e7073494529b4db6c6e016d653f851124c7e933d1f7d90b596`。底层部署、隐藏路由、实扣费用未知；返回模型别名一致不证明后端部署相同。
- 只读所属 Worktree 重加密后的目录配置，检查登记 root、数据库、角色和目标线路；不回退主环境或种子默认 miaomiaoai，不输出凭据或授权头。
- 两轮任务使用实际 DearFlow 工厂、真实模型、真实本地 `read_file` 和 `InMemorySaver` 历史。合成身份、记忆来源及空 custom/MCP 数据源保留明确边界，不覆盖 Platform HTTP、生产 ACL 或三服务 E2E。

## 文件职责

| 文件 | 用途 |
|---|---|
| [prompt_cache_cases.py](../../../../apps/runtime-service/scripts/prompt_cache_cases.py) | 五类合成材料、真实构图/中间件、适配后 HTTP 捕获、单因素出站变换、组标记与材料哈希 |
| [prompt_cache_experiment.py](../../../../apps/runtime-service/scripts/prompt_cache_experiment.py) | 离线准备、Xiaok 回放、SSE/usage/延迟采集、估算、脱敏、报告、图表和公开数据复算 |
| [prompt_cache_agent.py](../../../../apps/runtime-service/scripts/prompt_cache_agent.py) | 日期/记忆/组合两轮任务及真实摘要边界；主/辅助调用统一留证 |
| [test_prompt_cache_experiment.py](../../../../apps/runtime-service/tests/scripts/test_prompt_cache_experiment.py) | 单因素、缺失/冲突、故障停止、总超时、费用未知、脱敏、离线复算、读文件/历史和摘要辅助调用测试 |

## 使用方式

以下命令从仓库根目录执行。`prepare`、`report`、`recompute` 不调用模型；`run` 和 Agent 脚本会实际调用 Xiaok。所有输出使用新文件或新目录，禁止覆盖旧批次，也不要直接复用下面的演示路径重复实验。

```bash
# 离线捕获。只研究记忆、日期，各固定三次重复。
apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/prompt_cache_experiment.py prepare .local-stack/cache-experiment/NEW-manifest.json --cases C02 C03 --repeats 3

# 真实回放示例；当前交付无需重新执行。
apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/prompt_cache_experiment.py run .local-stack/cache-experiment/NEW-manifest.json .local-stack/cache-experiment/NEW-run --max-requests 48 --max-estimated-cost-usd 5

# 使用已保存的完整私有批次，离线复算并绘图。
apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/prompt_cache_experiment.py report .local-stack/cache-experiment/repeated-v3 --plots

# 真实两轮任务示例，末参还支持 memory、combined、summary。
apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/prompt_cache_agent.py .local-stack/cache-experiment/NEW-agent date

# 只用公开数据复算，不加载连接，不发送 HTTP。
apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/prompt_cache_experiment.py recompute docs/projects/20261123-dearflow-prompt-cache-governance/implementation/evidence/measurements.json
```

用户已明确无需追加额度限制。脚本仍要求一次运行的请求数和配置估算工程保护，并保留单并发、零自动重试、120 秒总期限与异常停止；它们不是新增人工审批。预留值使用字节量作为保守工程 proxy，不能当成供应商计费 Token 上界或实扣硬封顶。不得从一次保护额度反推用户账户余额或实际支出。

本次批次不需要重跑。回放结果、完整任务与失败均已封存；若要改变模型、材料、问法、输出上限或重复次数，应另开版本并登记，不能覆盖旧结果。

## 已执行的批次

| 私有批次目录名 | 派发数 | 配置估算 / USD | 实际结果 |
|---|---:|---:|---|
| c01-v1 | 3 | 0.0426666 | 原解析因混合协议别名停止；原失败保留，新协议离线复算 |
| all-v2 | 32 | 0.9504213 | 五案例回放机械断言通过；C04 不等价候选仅回放 |
| repeated-v3 | 48 | 0.6278868 | C02、C03 各三重复；探索组不混入 |
| agent-date-v4 | 4 | 0.0589947 | A 第二轮日期错误，按规则停止，B 未执行 |
| summary-v4 | 2 | 0.1228905 | 真摘要和主模型均计数；最后事实正确，摘要触及输出上限 |
| agent-combined-v4 | 8 | 0.0831189 | A/B 各两轮、各两次实际文件读取，有限断言通过 |
| 合计 | 97 | 1.8859788 | 实扣未知，无自动重试 |

实验期间私有目录为仓库根下 `.local-stack/cache-experiment/`，曾保存 manifest、registration、逐请求原始 SSE/用量/计时、请求哈希和结果，Agent 批次另有 tasks。它们在公开允许字段逐条核对后，已按用户清理要求删除，不再保留完整私有请求；公开脱敏数据与复算摘要没有改写。

配置价来自目录版本 `4963f058-50b2-4676-8596-a194ea91b877`，更新时间 `2026-11-07T16:10:49.648383+00:00`；输入 1.5、输出 6、缓存读取 0.15 USD/百万 Token。仅按本次观察到的用量估算，credit/quota 单位未核实。不能声称实际节省了相同金额。

主要数字、逐重复反例、日期失败及组合结果见[文章](../article.md)；不在此复制一套进度。

## 协议、布局和质量边界

Xiaok 同时返回 OpenAI 的包含缓存总输入与其他协议的别名。`normalize_replay_usage` 选取 OpenAI 兼容字段后复用现有 `normalize_usage` / `estimate_usage_cost`，并与当前流式适配器核对，不建立第二套生产账本。若标准 `cached_tokens` 与 `prompt_cache_hit_tokens` 冲突则停止；缺失缓存字段记未知，不补零。v1 的旧解析失败及停止原因保持，新复算不是将原运行标成成功。

B 将相同有效记忆/日期块前置到最新 user 内容，在出站副本操作、不持久化。原 block-list 系统消息结构保持；无有效记忆时不创建新内容。跨角色的指令优先级与生产语义尚未独立证明，不能据此直接改中间件。

权限检查包括六种合成状态及现有记忆相关契约测试：更正、删除、到期、共享、撤权、权限未知后，不新增注入旧事实或个人记忆。它不能证明已生成的旧回答可撤回，也不能替代真实生产撤权回调。

日期任务第二轮两条出站系统消息均为 2026-11-24，模型回答 2026-11-23；四次模型调用后停下。组合任务问法不同且每组只有一个任务，不能用它覆盖日期失败。

摘要辅助输入 4,066/输出 512、主模型输入 75,621/输出 48 Token。辅助 `finish_reason=length`，单事实正确不能证明摘要整体忠实。C05 各轮历史不同，未构造同材料 B；目录窗口 131,072 与较高实际输入成功响应的差异保留，既不证明硬上限，也不以缓存抵扣保证窗口。

## 公开证据与复算

[measurements.json](evidence/measurements.json) 包含六批共 97 条白名单用量字段、计时、合成答案、执行登记、布局摘要及执行时的源/请求哈希；已去除 credit/quota、凭据、授权头、完整事件和完整请求。它足以复算 Token、读取比例、配置估算、请求完成耗时与任务结果，不足以独立重建全部出站正文或验证服务端内部实现。执行时脚本哈希保留；后续只对离线复算、图表和测试做补充，不用当前文件哈希冒充运行时哈希。

数据文件 SHA-256：`02eaa968d1b8a8b2db55ba1b638b10c28218bfa63085e7639ac8f36b0c5e5f14`。[summary.json](evidence/summary.json) 是对该文件的离线复算产物。三张图来自 repeated-v3，分别为[逐请求读取](evidence/cache-ratio.png)、[合并配置估算](evidence/configured-cost.png)和[完成耗时分布](evidence/latency.png)。缓存图逐案例/重复分面，避免 12 条曲线挤在一起；其余图各组均为 12 请求。

## 验证命令和结果

从 `apps/runtime-service/` 执行：

```bash
.venv/bin/python -m pytest tests/scripts/test_prompt_cache_experiment.py tests/services/dearflow_agent/test_memory_contract.py tests/services/dearflow_agent/test_memory_access.py tests/services/dearflow_agent/test_memory_relevance.py tests/services/dearflow_agent/test_agent.py tests/middlewares/test_tool_output_pruning.py tests/middlewares/test_conversation_offloading.py -q
```

首轮结果为 **127 passed，5 warnings，45.72 秒**。其中新增公开数据复算测试证明：从实际用量重新计价、保持源数据不变、计划未完成不宣称整组比例、缓存缺失不捏造零、任务质量与逐请求质量分开，以及 CLI 不加载连接。五项警告为既有 SWIG 弃用；实际捕获还出现既有技能目录名称与空 custom 目录提醒，未扩大本次范围修复。

四个新增 Python 文件通过 Ruff 检查与格式检查，公开数据 CLI 复算与随附摘要逐项一致；三张图已视觉核对。仓库文档校验、相对链接/锚点、空白、公开证据脱敏与生产源码未改动核查见 [Phase 4](../verification.md#phase-4文章与证据一致性task-6)。这些是本地技术验证，不是独立评审、生产验收或用户最终确认。
