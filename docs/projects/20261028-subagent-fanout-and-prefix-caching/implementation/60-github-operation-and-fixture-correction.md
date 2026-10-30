# GitHub 操作必填与回归夹具修正

2026-10-29。属于已批准 T5.3 的通用工具输入/收敛修复；v47 六次终态并确认无漂移、恢复 Pro=true 后实施。原题、五项评分、模型与调用额度保持既有配置，未提交或部署。

## 已观察问题与最小修复

v47 第二次委派有一个子任务 26 次缺 operation/ref/path 的 GitHub 调用，被 `operation="info"` 默认值解释为成功元数据查询，子模型却自述尝试了文件读取。以实际工具参数为准，不推断供应商为何漏参。

`apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/github.py` 将 operation 改为必填，工具说明明确内容读取与元数据操作的区别。复用 SDK 的参数校验及原纠错流程：漏参、null、非法枚举在 HTTP 前报错，纠正为 readme 后能在同一图继续读取指定 SHA。仍允许显式 info，不猜测/补齐用户未提供的操作、ref 或 path，不新增错误处理层或调用额度。

`tests/services/dearflow_agent/skills/test_research_batch.py` 新增三种无效操作的实际 SDK 图回归，验证错误 ToolMessage、call ID、网络请求数和纠正后的不可变 README 结果；既有私有仓库拒绝用例显式选择 info。

## 扩大回归夹具修正

v47 扩大回归的 9 失败完整保留，未以修改应用来迁就旧断言：

- `tests/middlewares/test_runtime_middleware.py`：构造合法的当前 ResearchReport overview，原六组 Schema 不扩执行权限断言保留。
- `tests/services/dearflow_agent/test_source_quotes.py`：补实际 before_agent 会设置的当前 Run owner。首次复验又暴露旧测试按裸 ModelResponse 取值，改为读取 SDK ExtendedModelResponse.model_response，并断言 finishing 状态；旧 Run 来源仍须被拒绝。
- `tests/services/dearflow_agent/test_tool_errors.py`：模型视图的安全错误 JSON 后可有当前 Run 证据注册表，使用 raw_decode 读取首个 JSON；新增持久 checkpoint 仍为原 JSON 的相等断言，原安全码、outcome、name、call ID 与后续交付断言保留。
- Showcase 执行用例显式 `RUNTIME_BACKEND=local` 复验 1 passed（6.88s），未启动 Docker。

## Phase 验证及同步

独立漏参回归在旧应用上为 1 failed / 2 passed（6.03s），实际多出一次 info HTTP；红测日志 `.local-stack/v47-github-operation-red.log`。修复后直接关联五文件组合为 115 passed / 1 failed（27.87s），唯一失败是上述旧返回包装断言；修正后完整 source_quotes 文件 38 passed（7.81s），其余已通过用例未改。最终固定版本扩大回归由 Final 另行执行。

五份应用/测试修改先校验主目录原摘要，再逐字同步；记录 `.local-stack/v48-source-integration.json`。Runtime 标准同步操作必填契约，CHANGELOG 记录用户可感知修复；五份修改 Ruff 通过，使用 uvx 缓存工具，不改依赖锁。所属 Runtime API/Worker 已重启且 API ready。独立完整烟测预登记和实际结果待下节回填；本记录不代表三次质量、泛化或 Final 通过。

独立漏参回归在修复后的真实工具及 SDK 图上 3 passed（4.48s），日志 `v48-github-operation-green.log`；69 份主目录应用/测试文件与所属 Worktree 逐字一致。

## v48 独立正式任务预登记

清单 `.local-stack/v48-operation-smoke-manifest.json` 于 `2026-10-29T15:15:47.915738+00:00` 在模型提交前生成，SHA256 `e0c159adcd0884149c2ec4d4205d516f7369e9132a698a4abeaacc0bda69e667`。冻结 1131 份公共文件、当前测试及工具、环境、原题/SHA、Kimi262144/8192、主50/子16等既有参数；仅一次独立完整任务，失败保留，不混入正式组。

经正式页面新建 Thread `3a390ffc-e5d5-4fe2-a2b2-d8688a2f2da7` / Run `4e799a78-a59f-4d16-a0ec-7b64d1cfbd6f`，已 success。collector `collect-v48-operation-smoke.py` exit 0，拒绝覆盖或重复提交意图，逐次检查冻结；1131 份公共文件、12 份测试、10 份审计工具及环境未漂移。

## v48 终态与人工核验

- 原五项语义与支持引用 5/5；最终表第1–3条覆盖包组织、默认装配与子代发现，第4–8条覆盖压力/规范溢出、先剪后摘要和 replacement generation 推进才重试，第9/13条覆盖 loop 外可选服务、多 provider 与进程形态。
- 三个真实 `code_explorer` namespace，28 份来源固定 SHA、hash 和实际已读行校验通过；唯一最终流与 checkpoint 相等，没有原始 Schema 草稿泄漏。
- Usage 25/25 完整、账本对平；主 2 次调用，累计输入 30,260、峰值 18,095（配置窗口 262,144 的 6.90%）；子 23 次调用。全 Run 输入 302,538 / 输出 17,143 / 总 Token 319,681，cache_read 217,088，耗时 297.12 秒。
- root 自动摘要 0、压力剪枝 0、成功 spill 0；有界原文交接 1,785 字符，去重及确定性渲染校验通过。
- 附加结论局限：ACP/Codex/ClaudeCode 拒绝五种 start capability 在固定 SHA 源码中为真，但最终引用范围未单独支持全部附加限制；首条也把共享 driver 与 provider 并列。记录这两个表达/引用粒度局限，不用审阅新读的源码补核心评分。实际供应商窗口和部署版本未报告，费用未知。

私有终态 `.local-stack/v48-operation-smoke-terminal.json` SHA256 `964b8122851ae44616a0a3395387d02f8a55f9f1c2b5e8afb72848c21f5e0b6f`；人工评分 `.local-stack/v48-operation-smoke-review.json` SHA256 `b5174da717f71b5a744548e4644bf69803d32b46b7f29f193cc3583d27edc5ae`。这是一次独立通过，不代替正式三次稳定性、泛化或 Final。下一组预登记见[61号](61-v49-controlled-validation.md)。
