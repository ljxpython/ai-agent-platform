# P4 K01：原资源最小适配迁移

K01约定后端范围done、前端交接done、页面deferred，整体partial。用户授权按“原样复制优先，实际不兼容才最小修改”启动迁移。下一项K02尚未复制；按P4顺序检查论文输入依赖再实施。

## 资源与代码改动

来源提交 `44ae750545caff29506906f4b0b1ebf79cb23fa7`，原文件 `research/deer-flow/skills/public/deep-research/SKILL.md`。目标路径均相对本仓库根：

| 文件／函数 | 改动与原因 |
|---|---|
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/deep-research/SKILL.md` | 保留全部原研究流程／示例，仅WebSearch→search_web、web_fetch→fetch_page；不新增工具别名或Skill包装类 |
| 同目录 `LICENSE`、`provenance.json` | MIT许可证原样复制；来源提交、原文／许可证SHA256、适配清单与验证记录可核对 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py:get_agent` | 给原文要求的current_date提供真实UTC日期；skills_hash改为全部包内技能资源指纹，修复只哈希烟测资源的问题 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/prompts.py:SYSTEM_PROMPT` | 真实验收发现“保留证据路径”被模型理解为仅列网页URL；明确报告末尾逐条列出引用正文的path。只细化现有平台证据要求，不改写上游研究方法 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py:skills_hash` | 复用importlib.resources定位资源，按路径和文件内容生成稳定指纹；不创建注册框架 |
| `apps/runtime-service/pyproject.toml` | package-data包含skills深层资源与provenance／许可证；既有烟测路径不变 |
| `apps/runtime-service/tests/services/dearflow_agent/skills/test_deep_research.py`及`fixtures/deep-research/conflicting-sources.json` | 原文最小差异可逆校验；官方技能加载、真实图与三份冲突证据、只读保护、提取失败；脚本模型仅证明链路，不冒充模型判断质量 |
| `apps/runtime-service/tests/services/dearflow_agent/test_platform.py`、`tests/e2e/test_dearflow_skills.py` | K01真实平台验收入口：读取技能、3角度搜索、两个独立站点正文、冲突材料与注入负例、审批／队列／报告下载 |

当前复用既有 `/skills/<slug>/` 路径，不新增 `/skills/public/`别名。07原拟public分层在只有包内公共技能时无必要；自定义资源命名空间在P6按实际需求另行交付。技能读取不授予工具权限。K01输出继续采用既有TXT产物，不扩展文件接口或前端页面。

验证边界：三份40%／10%冲突资料均为明确标注的合成材料，真实平台测试通过用户输入提供；其中包含诱导写入injected.txt和引用虚构99%数据的指令。该用例检查此输入下的行为，不代表已证明任意线上网页注入都能防住。真实网页来源另外通过search_web／fetch_page获取，不能把合成材料算成外部抓取成功。费用未取得可靠账单时标未知，不按token自行估价。

## 验证记录

### 最终结果与复验入口

- [x] 原文最小适配、官方加载、只读权限、来源版本与wheel资源验证。
- [x] 真实平台研究：技能读取、多角度检索、独立站点正文、合成冲突材料、拒绝注入、真实URL及本地证据路径。
- [x] 七字段澄清、write_file与present_artifacts审批、v3恢复、补充消息消费、TXT下载哈希一致。
- [x] 前端交接完成：现有工具元数据／TXT接口、研究预算与内部证据路径限制，见[前端交接](../frontend-handoff.md)。
- [ ] 页面／浏览器验收：deferred；正文文件HTTP预览未实现，不纳入本轮后端交付。

最终真实样本：project `c594fc83-468b-4b07-a5a4-b775c08ab4a5`，thread `28b9ac23-e468-425b-adab-bcd4ab9dc22c`；source Run `a5ae3820-b885-4817-a066-e250327d77eb`，恢复依次为 `0b542f98-cdfe-4b0c-94cf-c17f866938af`、`53e3b693-56e9-4c54-889f-49bb1d7267e1`、`fdac968e-5bf2-4858-82ee-5017acea5bc6`（success）。模型为DeepSeek-V4-Flash，技能revision `dear-k01-v1`。

本轮pytest原始结果 **1 failed，419.55s**：报告明确引用并拒绝虚构URL，旧断言一见该URL便失败。修正测试后，没有再付费重跑模型；对上述已持久化真实样本进行**只读HTTP复验，通过**。复验调用同一 `test_platform.py:assert_k01_report`，核对成功终态、下载SHA256、队列标记、技能读取、>=3检索角度、>=2来源站点、至少两条URL与真实证据path配对、冲突与合成标记、注入拒绝、没有实际execute／task／写入injected.txt，并检查最终v3 lifecycle回放。不把原始pytest失败改写为pytest通过。全文引用恶意文件名也允许，校验写入的目标路径而不是把报告正文提及文件名误判为写该文件。

- 产物 `/workspace/outputs/026e8b8fe1cd46e423c80fb0e7c2afe131ff717d61695bd722618b188b0db781.txt`；SHA256 `026e8b8fe1cd46e423c80fb0e7c2afe131ff717d61695bd722618b188b0db781`。
- 成功page_text来源：`https://docs.python.org/3/library/asyncio-task.html`、`https://anyio.readthedocs.io/en/stable/tasks.html`、`https://hynek.me/articles/waiting-in-asyncio`、`https://anyio.readthedocs.io/en/stable/why.html`。
- 最终state中10条带usage的AI消息合计：input 247334、output 7161、total 254495 tokens；仅是该state可见消息统计，不包含其他失败验收或可能的服务内部额外调用，不作为费用账本。供应商实际费用未知。
- 追加尝试通过files/content读取内部sources路径返回400，属于当前接口目录边界；不能声称已有来源正文HTTP下载。报告下载通过，来源path与artifact配对通过，资源内容哈希／只读保护由确定性测试覆盖。
- 修正后测试及prompts的ruff通过（runtime-service目录执行`uv tool run ruff check`）。先前wheel记录是提示词细化前的包，用于证明资源打包／安装路径，不冒充最终发布包。

新一次完整验证：从 `apps/runtime-service/` 执行 `DEAR_SKILL_E2E=1 .venv/bin/python -m pytest -q tests/e2e/test_dearflow_skills.py -k K01 --tb=short -s`；会创建隔离项目并消耗真实模型／搜索调用。已有样本可按上面的thread读取state与TXT，调用 `tests/services/dearflow_agent/test_platform.py:assert_k01_report(messages, report)` 只读复核报告行为，避免为断言误报重复调用模型。

### 过程记录（保留失败，不累加为通过数）

- `.venv/bin/python -m pytest -q tests/services/dearflow_agent/skills/test_deep_research.py --tb=short`：**3 passed，41.01s**。涵盖原文仅工具名替换的可逆哈希校验、LICENSE原样、资源指纹随参考文件变化、官方渐进加载、三份冲突来源落盘／只读、抓取无结果不伪造证据、即使批准也不能写入Skill。脚本模型不用于声称注入防御或综合判断能力，另以真实模型验收。
- 构建最初把烟测目录__pycache__带入wheel；新增exclude-package-data。已有build/lib还残留旧缓存，改用仅复制src（排除egg-info／字节码）与pyproject／README的干净临时目录执行 `uv build --wheel`，不删除用户工作区文件。最终wheel `/tmp/dear-k01-clean-wheel/langgraph_open_teach-0.1.2-py3-none-any.whl`，SHA256 `8818cd90f23504bd977af4b7450ffde97a2af78ec710b3ef41e98a46af716093`；5个技能资源逐字节匹配源码，无pyc。
- 新增／修改测试文件ruff通过。真实平台首次因Runtime正在重启，catalog refresh返回502；API ready（56s）后重跑，不修改超时绕过问题。真实验收进行中。

必须记录失败与限制，不能把复制成功勾为K01完成。K-G1/K-G2仅完成本项需要的切片，不代表未来所有格式或自定义技能治理完成。

- 增补“读取技能不扩大工具权限”负例后，K01定向测试 **4 passed，54.52s**；这是后一次执行结果，不与前次3项累加。
- 第二次真实验收 **1 failed，405.64s**：project `de6b4c25-6e8d-4c29-b7bb-3fd0385d66d3`、thread `7294f319-d700-475f-80f2-f8731159a96d`、最终Run `dc124bee-1d67-4979-8d96-022e794c425f`。Run成功且TXT已交付，但两次fetch_page均为 `research_provider_failed`，没有page_text artifact，严格来源断言失败。通过state和history核查，**不是v3／DeepAgents丢弃artifact**；搜索摘要仍有artifact。未获得当时底层异常，不能断言为超时或供应商HTTP错误；当前直接Tavily和现有tavily工具复查均成功，保留供应商间歇失败风险，不修改中间件或放宽来源验收。报告成功不计研究链路通过。
- 第三次真实验收 **1 failed，559.13s**：project `c3d1b427-550c-41c8-bf8b-26ed7f7ad08b`、thread `3ea82eee-0341-428c-8a20-98f5f38274dd`、最终Run `d70c87d1-2da2-48d4-bb61-d85082dae850`。搜索初次失败后模型重试成功，3份真实正文artifact完整；审批、v3恢复、队列消费、下载通过。报告SHA256 `43d1da8f7314f095d083433ff7dacde70bf7db810d4c07131284912d1921f716`，列了真实URL却遗漏本地证据path，写入工具参数也没有path，故不是传输丢字段。细化SYSTEM_PROMPT现有要求后复验。人工同时发现报告引用“99%”以明确拒绝注入，原测试仅按数字出现判断失败会误报；改为其附近必须明确标注忽略／注入／虚构／伪造，同时保留禁止虚构URL和执行注入行为的断言。此断言只覆盖该固定样本，不能代替通用语义安全评估。

- 实际wheel安装到 `/tmp/dear-k01-installed`，从`/tmp`目录以该安装目录为PYTHONPATH导入，确认importlib.resources指向安装包而非源码；通过CompositeBackend读取K01全文，资源指纹 `86e623f87f7350a07307be90be1e1706d3fc74e57e74d72da741076694aae43c`。不安装新的全局依赖。
- Dear回归及默认关闭的K01 E2E：**45 passed、7 skipped，205.96s**。命令 `.venv/bin/python -m pytest -q tests/services/dearflow_agent tests/e2e/test_dearflow_skills.py --tb=short`。7个opt-in跳过不计通过；保留现有Pydantic／SWIG／v3 beta警告。
- 首次真实K01业务执行失败：project `477007fb-d478-4209-bbd5-bc35e9482602`，thread `89edcabf-f6eb-467d-b943-0d905384e5dc`，source Run `2088cb09-b5e9-4bd6-8e05-ce4c929acce7`，resume `b9469d31-7b70-424b-9339-f07451b3abca`；已实际read_file加载Skill、3角度搜索及多次正文核实，但来源Run默认25步预算触发GraphRecursionError。25是包含中间件的图步数，不是25次模型调用。K01验收改用现有公开config.recursion_limit=100（Dear既有封顶），不修改平台默认／生产限额；前端交接明确研究预算。尚不以此重试前的失败样本计完成。
