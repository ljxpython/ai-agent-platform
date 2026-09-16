# P4 K02—K07：集中实现、统一验证

用户确认：本批次先集中实现K02—K07及必要依赖，随后集中运行定向／组合／平台验收；小改动不重复执行全量回归。按“原样复制优先、实际不兼容最小修改”迁移。实现完成和验证通过分别记录，前端只交接、页面deferred。不修改GraphHarbor业务边界。

| 项目 | 实现 | 验证 | 前端交接／页面 |
|---|---|---|---|
| K02 论文评审，PDF页码证据 | 已实现 | done：组合与真实PDF链路通过 | done／deferred |
| K03 GitHub只读仓库研究，分页及来源 | 已实现 | blocked：组合通过，GitHub匿名配额耗尽403，真实Run timeout | done／deferred |
| K04 两阶段咨询分析与数据缺口 | 已实现；实际图表生成依赖K09 | 本轮报告范围done；图表deferred | done／deferred |
| K05 arXiv综述、子Agent批处理、引用 | 已实现；沿用Ultra与受限子Agent | blocked：真实接口429／超时，未完成论文→子任务→引用全链路 | done／deferred |
| K06 安全代码包阅读与文档 | 已实现；不执行用户项目 | done：组合及真实ZIP链路通过 | done／deferred |
| K07 简报筛选、来源、Markdown交付 | 已实现；不发邮件 | partial：报告通过，联网正文核验未完成 | done／deferred |

## 代码与适配记录

目标均相对仓库根，六项业务资源集中在 `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/`。

| 文件／函数 | 改动及边界 |
|---|---|
| `skills/{academic-paper-review,github-deep-research,consulting-analysis,systematic-literature-review,code-documentation,newsletter-generation}/` | 六个原始资源树整体复制；每项LICENSE及provenance保留来源commit、逐文件SHA256；模板、原始脚本、eval原样保留。SKILL仅适配工具名／工作区路径及明确不兼容的执行协议 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/github.py:build_github_tool` | 固定GitHub API，公开仓库，只读操作；显式page/per_page、next_page/truncated，README／源码解码；不把100个贡献者样本说成总数；不加载token，私库后置 |
| 同目录 `arxiv.py` | 原样保留上游 `_build_search_query`／`_normalise_arxiv_id`／`_parse_entry`，不复制其网络客户端到生产执行路径 |
| 同目录 `arxiv_search.py:build_arxiv_tool` | 固定arXiv接口、日期／类别／排序、50条上限、版本ID去重、缺字段标记、abstract_only、检索式／时间／证据；禁止XML DTD／实体 |
| 同目录 `research_http.py:get_public` | 两个固定主机、无凭据、不跟重定向、总超时35秒和2MiB响应上限；限流／404／失败返回工具错误 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py:get_agent`、`capabilities.py` | 显式装配github_query／arxiv_search并纳入read权限；子Agent保持现有只读研究边界；task预算8→10以覆盖上游50篇／5篇一批，不增加独立子Run；产物能力声明增加Markdown/BibTeX |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/prompts.py`、`tools/artifacts.py` | 明确新工具与静态代码输入、摘要范围、缺日期／缺图表；产物一次发布一个文件 |
| `apps/runtime-service/src/runtime_service/workspace/archives.py:read_zip` | ZIP在内存读取，不落解包目录、不执行代码。20MiB总展开／256条／单文件2MiB／100倍压缩比；拒绝穿越、绝对路径、链接、加密、重复文件名和损坏包 |
| `apps/runtime-service/src/runtime_service/workspace/file_refs.py`、`documents.py:validate_document`、`tools/documents.py:parse_document` | 现有上传与解析增加application/zip；query按包内路径选文件，返回entries/files/skipped_binary/truncated。PDF继续复用页码与OCR警告，不加OCR |
| `apps/runtime-service/src/runtime_service/workspace/artifact_refs.py:ArtifactWorkspace`、`http/documents.py` | 沿现有不可变SHA256发布与下载增加.md/.bib，保持UTF-8和线程授权；不增加HTML预览 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py:upload_thread_file`、`presentation/http.py` | 网关允许ZIP上传、BibTeX文本下载MIME；鉴权和委托scope不变；GraphHarbor无需修改 |
| `apps/runtime-service/tests/services/dearflow_agent/skills/test_research_batch.py` | 六项官方加载、支持资源哈希、权限、分页、XML／日期／去重、ZIP负例、三类产物 |
| 同目录 `platform_batch.py`、`tests/services/dearflow_agent/test_platform.py`、`tests/e2e/test_dearflow_skills.py` | 复用已有平台登录／测试模型配置，K02—K07参数化真实输入→工具→审批→下载；每项打印thread/run/revision/sha256/可见token，费用未知 |
| `apps/platform-api/tests/test_runtime_gateway_files.py` | ZIP网关上传／BibTeX MIME与既有文件隔离回归 |

K05保留五阶段及三种引用模板，删除DeerFlow专属subagent_enabled、成功前缀和“超并发静默丢弃”描述，替换为Ultra授权与官方ToolMessage。原脚本仅参考，不向沙箱注入凭据或新增网络放行。K04图表为K09依赖，当前报告必须明确未生成。K07不发邮件。K06只读用户代码，不运行安装钩子。

## 验证记录

代码已集中写入，正在运行相关回归；验证结果未收口，不标done。集中验证命令（分别在对应app目录执行）：

```bash
# runtime-service：Dear与受影响共享文件链路
.venv/bin/python -m pytest -q tests/services/dearflow_agent tests/services/showcase_demo/test_documents.py tests/e2e/test_dearflow_skills.py --tb=short
# platform-api：使用项目已有unittest，无需安装pytest
.venv/bin/python -m unittest discover -s tests -p test_runtime_gateway_files.py -q
# runtime-service：真实模型与外部服务调用，逐项留证，前端不实施
DEAR_SKILL_E2E=1 .venv/bin/python -m pytest -q tests/e2e/test_dearflow_skills.py -k 'K02 or K03 or K04 or K05 or K06 or K07' --tb=short -s
```

源码六项写完不等于全部行为验证通过；模板中涉及K09或未授权工具仍必须明确限制。失败只复测相关链路。

- Runtime集中回归：**63 passed、13 skipped，260.33s**；13项opt-in跳过不计通过，保留已有Pydantic／SWIG／v3 beta警告。
- 平台文件网关：**5 tests OK，3.894s**。首次新增测试夹具缺完整FileRef导致502，补齐夹具后通过；未放宽生产响应校验。平台环境无pytest，使用已有unittest，不加依赖。
- 新增工具／ZIP／批次测试ruff通过，git diff --check通过。
- arXiv真实连通性：超时及HTTP429 `Rate exceeded.`，不把供应商不可用归为成功；继续其他技能真实验收。
- 干净wheel：`/var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/dear-k02-k07-build-mtti6z6t/dist/langgraph_open_teach-0.1.2-py3-none-any.whl`；SHA256 `7617e8186eae8511b7fa48327bbd57531a9911c5850135a789d1aa2432cf37e7`，31个技能资源与源码逐字节一致、无pyc。只构建验证，不发布。

## 真实平台逐项证据

模型DeepSeek-V4-Flash，model_id `9c276f29-a5cf-48a3-8cfb-86ab09f57537`。下列tokens仅统计对应最终state可见usage，不等于账单，费用未知。

### K02：通过

- project `7ee2a296-fc78-45d2-ba83-bd41d96dab95`，thread `efeba796-411e-43c7-829d-184f6380bf4a`。
- runs：`c18d5b60-0e14-4542-bb4a-4327fd970823` → `b66f5697-0a51-4db9-8443-3d2ae5214bb2` → `146aba6f-9467-4f33-8529-f8d224ed387d`。
- revision `dear-k02-v1`；Markdown SHA256 `0cfe25f2ac0ed6e47b68c590b9b0e64e531d7e7fcd5ea0e0c00385c054d3bd06`，6425 bytes；可见35731 tokens。
- 真实HTTP上传两页合成PDF，模型自行选择并读Skill，parse_document页码证据、样本20／80MB／50MB和局限、两次审批、v3恢复、下载MIME与哈希通过。合成论文不冒充真实学术发现；扫描／损坏PDF边界沿已通过共享解析回归，OCR仍未实现。

### K03：外部限流阻塞

- project `1360b574-e6a4-4ade-9a5b-27ef4437ff1a`，thread `5c212434-aea8-4f63-af8a-f9afdc390cd2`，run `3697ecbe-536d-4ef3-87a7-3a6fc87a780a` 最终timeout。
- Agent读取了Skill与模板，但github_query连续返回限流。直接复查GitHub响应403、x-ratelimit-limit=60、remaining=0；未拿到真实仓库数据，不能算通过。无私库／Token接入扩展，匿名配额恢复后只复测K03。确定性分页／私库拒绝测试通过，不替代真实来源验收。

### K04：本轮报告范围通过，图表后置

- project `165fda41-ca5c-479f-a83c-e0523c62db8d`，thread `9b8227bb-db17-4288-8cd9-9fedaedb49e5`。
- runs `53672069-7d93-4916-b21c-72860cf74614` → `48f5ea1a-0eee-4c8f-a2b3-4265f699f6a0` → `8cdd9e05-c8ef-4718-a28c-edac9982df0b`。
- revision `dear-k04-v1`，Markdown SHA256 `acc4656c1273fbe473915c1ed1d0f0729c9e0eb8f29495cfced15d317a515ce3`，4681 bytes，可见50365 tokens。
- 已知收入100→120计算20%，缺收入案例不计算增长率，TAM／利润率缺口声明；框架／报告、官方写入发布审批、下载通过。该用例输入范围明确，未触发澄清；澄清复用既有已通过组合链路。真实图表生成依赖K09，整体partial。

### K05：arXiv外部不可用，未完成验收

- project `ec20ebd6-ca3b-4e26-8016-a2d9c3285185`，thread `5fea3c51-b2c2-4dc4-a920-d581e8a51093`，run `f40ede8d-d209-4f3f-815e-68730b7d07dc` 最终timeout。
- 已读Skill、APA／BibTeX模板并调用arxiv_search，返回限流及provider_failed；模型仍重复尝试，未获得真实论文。不能用原有task测试声明本Skill已验收，论文→子任务→引用交付保持blocked。接口恢复后只重跑K05，禁止用合成论文替代本项真实外部验收。

### K06：通过

- project `c81905b6-7e9f-4b1f-b3d6-e868ccb58f69`，thread `40584700-0f22-40a7-8436-19010505877b`。
- runs `45513de7-4f1e-4059-9f35-8f4af936d22e` → `a16afa9d-c019-4d8c-9018-c270ca508387` → `54fa86ef-775e-4340-a22f-f6c8bdd5ea8b`。
- revision `dear-k06-v1`，Markdown SHA256 `ac657e68e398fb1ad94d5964067d52f238a1554e278fde586718866c3425549c`，1271 bytes，可见34389 tokens。
- 真实ZIP上传→parse_document→函数参数与静态示例→两次审批→下载通过；未调用execute。包中setup.py带失败钩子，仅作为文本；无宿主解包和安装执行。

### K07：部分通过

- project `3e534258-6848-4a26-8baa-5cbe99991b30`，thread `0505f910-d3bc-4b54-af69-eeb72e20e976`，source run `6fc5733f-0f48-485d-a337-3a69e20ae1d3`，恢复 `c6a097a0-2d4b-4361-9c8b-34021cdd8237` → `c36035c8-93a2-4bec-a736-d69b398b938a`。
- revision `dear-k07-v1`；Markdown SHA256 `912ba89c5846dad0b0589914ace30c343799ddb11941b352f028ae8b369a10a5`，3710 bytes。真实JSON候选输入经parse_document，去重、时间窗和未知日期均写入报告，search_web成功并有artifact，审批和下载通过；但没有fetch_page正文artifact，故来源核验条件未满足，标partial。后续仅复测K07联网正文核验，不重跑已通过文件链路。

本批次当前判断：K02/K04/K06本轮后端范围done；K03/K05 blocked；K07 partial。**所有Skill整体均未done，页面后置；K04图表另依赖K09。**“实现完成”与“真实验证通过”分列，前端交接已完成。K03/K05/K07分别缺真实供应商数据、真实供应商数据与子任务交付、正文抓取证据。

- 六项真实验收汇总：**3 passed、3 failed、1 deselected，2020.05s**；失败详情如上，不修改历史结果。
- 最终批次定向测试：**16 passed，83.11s**；不是与63项回归简单相加的独立覆盖数。
- K07针对实际遗漏，只在该Skill补明确“search后fetch正文再核实”的指令，保留严格fetch断言，单独复测；不放宽验收。先前wheel为该句补充前的资源快照，不冒充最终发布包。

补充PDF异常定向测试：**1 passed、15 deselected，68.22s**（扫描无文本层、损坏内容、越界页码）。原共享测试只有正常页码用例；本次新增异常测试补足，不将此前回归夸大为已覆盖所有异常。

## K07 定向复验通过（2026-09-15）

补充正文核验指引后保持 fetch_page 断言，不放宽验收。1 passed、6 deselected，478.89秒。thread=00a44750-903e-450d-9293-8679c11677a5；runs=6b3b54ec-e37e-43ff-98f7-3ed3e1e4012d、e33d9b58-f651-4d2d-82fb-4633b6c897de、69ede214-b3f4-4f78-a28d-0db6130aa2b7。产物SHA256=dd4f9d68eee057f9b0d81e9d246dbe1523f1ef5e77116a295a61e338bae44ac3，4211字节；可见tokens=55124，费用未知。K07后端done／交接done／页面deferred。
