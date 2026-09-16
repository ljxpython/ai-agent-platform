# 07 全部 23 个公共 Skills：逐项迁移与验收

## 目标

保留上游 23 个顶层公共 Skill 的迁移身份和适用能力，每项独立迁移、验证、启用。迁移对象包括指令、参考资料、模板、必要脚本及行为；目录复制成功不等于能力完成。

## 工作上下文

- **总入口：** [项目总纲与交接规则](README.md)。独立开发本章时先读总纲，不以聊天历史代替依赖证据。
- **实施阶段：** P4 K01—K11；P5 K12—K16；P6 K17—K23；各 K 逐个迁移／验证／启用。
- **必读前置：** [01 底座](01-architecture-and-boundaries.md)、[03 工具](03-tools-mcp-and-evidence.md)、[04 格式](04-workspace-sandbox-and-artifacts.md)、[08 C07 与 F4—F6](08-web-and-platform-contracts.md)；按当前卡片补 06／09 前置。
- **输入 → 输出／对接：** 上游资源／provenance、已授权工具／格式 → 已验证 Skill 版本、真实产物及专属 Web 交付；候选管理不能绕过权限。
- **当前切片／最近证据：** 2026-09-15进入P4后端准备；P3后端及GraphHarbor post30链路已通过，正式Skills尚未迁移。底座证据不计Skill完成。
- **下一任务：** 07/K02及其论文输入依赖；K01约定后端与交接done、页面deferred，证据见09。不提前建设K-G3/K-G4。
- **结束回填：** 更新本章任务／验证／状态及此处游标，按总纲登记最近 implementation 记录、契约变化和下一精确任务；部分切片通过不勾选整章完成。

## 方案设计

### 迁移原则：原样复制优先，实际不兼容处最小修改

用户已确认此原则适用于后续23项迁移：先检查原始资源能否在当前环境直接使用，能用就原样复制；确有工具、路径、参数或运行机制不兼容时才做最小适配。保留原slug、研究方法、模板、参考资料与业务输出要求，不先重写再声称等价。

- 独立脚本先核对依赖、网络与沙箱边界，兼容就复用；不复制DeerFlow服务、配置系统、宿主执行器或工具兼容框架。
- 修改工具名、工作区引用与官方HITL接入时，逐处记录原值、新值和必要原因；不以迁移为由重构相邻公共模块。
- 每项记录原样复制文件、适配文件、来源提交／SHA256／许可证、能力差异、实际验证证据。复制成功不等于行为准确；真实模型仍需验证技能读取、工具事实和真实产物。
- 原资源有当前平台无法支持的行为时明确partial／deferred，不静默删除，不用模拟成功补足。

### 1. 统一加载、发布与文件规则

- 来源根为 `../research/deer-flow/`，以下来源路径相对此根。固定调研提交见 01；逐文件记录实际哈希、上游路径、修改原因和许可证。
- 全部公共资源拟放在 `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/<slug>/`。保持原 slug；内部脚本按原 `scripts/`、参考资料按 `references/`、模板按 `templates/` 放置，不散落到仓库根或 Showcase。
- 使用官方 `SkillsMiddleware` 的渐进加载：先给模型名称与描述，被选中后读取完整指令，随后按需读取参考资料。技能描述不得隐式开放新工具；实际权限仍按 03 裁决。
- 构建时更新 `apps/runtime-service/pyproject.toml` 的 package-data，验证 wheel 包含深层脚本、模板、许可证。运行时通过 `importlib.resources` 定位；当前包内资源沿用只读 `/skills/<slug>/`，不为public分类引入重复路径。`/skills/custom/`在P6按需交付；不能假定源码checkout一直存在。
- 公共 Skill 来源记录拟为各目录 `provenance.json`，至少含来源提交、原始文件 SHA-256、适用 license、行为变化、验证记录链接。根 MIT 不覆盖所有子目录：`frontend-design` 和 `skill-creator` 自带 Apache-2.0，必须保留适用声明。
- 用户／项目创建的 Skill 存 Runtime 持久业务存储及只读版本资源，映射 `/skills/custom/`；不得修改部署包、个人 Codex Skill 目录或本仓库 `AGENTS.md`。
- 自定义技能流程为候选包 → 静态审查 → 离线行为验证 → 真实模型验收 → 授权启用；发布和替换走官方 HITL。运行开始冻结选用版本，运行中升级不能替换其内容。回退恢复上一已验证版本，不恢复已撤销的权限。
- 不创建 Runtime 插件注册框架。公共技能启用清单用服务私有声明与已验证版本；动态技能只存确实需要的版本、owner、哈希、验证与启用信息。平台 catalog 仅投影可用能力。

### 2. 每项共同完成门槛

每个 K 项都必须有以下独立证据，缺任何关键项不得标 done：

1. 来源／资源／许可证核对；记录保留、替换、删去的具体行为，不能静默缩水。
2. 确定性测试：至少一个成功输入和该技能的关键负例，检查实际文件内容或工具事实，不能只断言模型说“已完成”。
3. 真实模型端到端：从 Dear Agent 专属路由请求，经 Platform 授权、Deep Agent 选择技能、工具执行到回答／文件下载；记录选中版本、模型、工具、产物哈希和费用。付费／发布操作包含审批证据。对应前端阶段为 08/F4（K01—K11）、F5（K12—K16）、F6（K17—K23）；后端通过而专属页面无法完成交付时，该 Skill 只能记 partial。
4. 工具授权、作用域、失败与取消满足公共测试；当技能新增外部副作用或格式时，再补它自己的边界测试。
5. 本 K 验证完成并记录后，才开始下一 K 的迁移。可以提前实现共同底座；遇到外部服务不可用先补依赖或标 blocked，不能越过后把整批标完成。

单元／确定性测试统一拟放 `apps/runtime-service/tests/services/dearflow_agent/skills/test_<slug_underscores>.py`；对应固定输入及预期资源拟放 `apps/runtime-service/tests/services/dearflow_agent/skills/fixtures/<slug>/`。真实模型测试拟放 `apps/runtime-service/tests/e2e/test_dearflow_skills.py`，按 K 编号选择，不默认每次单测都调用供应商。源码已有 eval 素材需审查后复用，不照搬需要外部 CLI 的执行器。

### 3. 迁移顺序与能力卡片

所有卡片的前端共同前置为 08/F1 独立入口和 F2 基础交互；复用已有消息、工具、文件卡片即可清楚交付时不新建专属页面。每个 K 的实现记录须写“本项 UI 落点／复用组件、消费的 08 C 契约、专属路由验收证据、尚缺的格式或交互”，确保逐项迁移同时交付用户可用能力。只读技能目录在 F4 增量开放已验收项，技能管理写操作在 F6 完成前保持关闭。

上游 Skill 中的 ask_clarification 用法统一改为 02 §6 的 `request_information` 与官方恢复，不把原 human_input metadata／END 协议带进来。多字段模板保留其业务字段，按已支持 schema 转换；K04、K18、K20 等访谈／参数收集场景要验证真实表单回答与恢复。付费或发布仍另走工具 HITL，用户填写参数不等于批准外部副作用。

下列顺序按依赖排列；每项“验收”均包含上述真实 Web 链路要求。目标目录全部拟新增。纯指令技能仍需行为评估，不为了增加代码量给每个 Skill 写一个 Python 包装类。

#### K01 deep-research — 多轮深度研究

- **能力拆分：** 澄清研究范围、拆检索问题、多轮搜索、读取全文、交叉验证、带引用的综合报告。
- **参考：** `skills/public/deep-research/SKILL.md`。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/deep-research/`。
- **实现：** 保留研究流程提示；搜索／抓取改用 03 的授权工具；引用使用真实 EvidenceRef。规划采用官方 Todo，复杂分题可使用当前普通同步子 Agent；需要独立 child Run 的 Skill 标记 partial/deferred，简单研究不得强制开子任务。
- **前置：** P1 工作区／产物闭环、P2 搜索抓取与证据；首项即可验证不委派路径。
- **验收：** 固定三份相互有冲突的材料，报告指出分歧、引用可定位；真实研究题验证至少两个独立来源。网页不可达、来源不足、提示注入时明确限制，不能补造来源或遵从网页中的命令。

#### K02 academic-paper-review — 单篇论文评审

- **能力拆分：** 读取论文、解释问题与方法、分析贡献和实验、指出局限、结构化评审。
- **参考：** `skills/public/academic-paper-review/SKILL.md`。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/academic-paper-review/`。
- **实现：** 用公共 PDF 解析读取页码／段落证据；保留评审结构，输出 Markdown 或可下载报告，不能把模型常识当作论文原文。
- **前置：** K01、04 的 PDF 文本提取与来源定位。
- **验收：** 固定论文能定位方法／实验表述，真实上传 PDF 完成评审；缺页、损坏、仅扫描图像时明确无法提取，不伪称全文读完。OCR 不包含在本项默认承诺中。

#### K03 github-deep-research — GitHub 仓库研究

- **能力拆分：** 仓库元数据、README／文件阅读、issues／PR／贡献活跃度研究、输出证据化仓库报告。
- **参考：** `skills/public/github-deep-research/SKILL.md`、`scripts/github_api.py` 的 `GitHubAPI`／`main`、`assets/report_template.md`（后二者相对该 Skill 目录）。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/github-deep-research/`。
- **实现：** 模板与指令保留；脚本中的 API 行为接入服务受控 GitHub 工具，处理分页、速率限制和响应截断。Token 仅服务端持有，禁止注入 shell 或模型；私库另验用户授权。
- **前置：** K02、GitHub 只读工具和分页证据。
- **验收：** 固定分页响应核对数量和链接；真实公开仓库报告能追溯来源。404、限流、私库越权、仓库文件内提示注入均不能触发权限扩大。

#### K04 consulting-analysis — 咨询式结构化分析

- **能力拆分：** 明确商业问题、选择分析框架、列数据缺口、收集证据、推导建议及风险。
- **参考：** `skills/public/consulting-analysis/SKILL.md`。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/consulting-analysis/`。
- **实现：** 保留“框架／数据要求 → 研究／结论”两阶段；缺少关键条件用官方 interrupt 提问，假设与事实分栏，数值来源绑定证据。
- **前置：** K03、官方澄清／恢复链路。
- **验收：** 同一案例有／无营收数据分别产生可计算分析／缺口声明；真实 Web 澄清恢复后交付报告。不得虚构 TAM、增长率和竞争对手收入填表。

#### K05 systematic-literature-review — 系统文献综述

- **能力拆分：** 研究问题、检索式、纳入排除标准、去重筛选、证据表、APA／IEEE／BibTeX 引用。
- **参考：** `skills/public/systematic-literature-review/SKILL.md`、`scripts/arxiv_search.py` 的 `search`／`_parse_entry`／`_normalise_arxiv_id`，同目录引用模板与 eval 资源。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/systematic-literature-review/`。
- **实现：** arXiv 网络行为接入受控工具，保留 XML 解析／ID 归一逻辑中适用部分；记录检索时间、式子和筛选原因，输出综述、证据表、引用文件。
- **前置：** K04、arXiv 接口与全文获取边界。
- **验收：** 版本化 arXiv ID 去重、字段缺失和 XML 异常有固定用例；真实小范围综述复查条目和引用。摘要可读但全文不可得时标明，不能宣称全部全文审查。

#### K06 code-documentation — 代码文档生成

- **能力拆分：** 理解源码目录与入口、提取公开 API、生成 README／架构说明／示例。
- **参考：** `skills/public/code-documentation/SKILL.md`。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/code-documentation/`。
- **实现：** 输入为用户上传的代码包／授权只读工作目录；解包按 04 限制，输出到任务工作区。生成示例允许静态检查，执行用户代码需既定沙箱策略，不修改平台自身源码。
- **前置：** K05、安全解包、文本文件与产物。
- **验收：** 固定小仓库的入口、函数参数、示例与实际代码相符；真实上传项目得到文档。目录穿越包、软链接、恶意安装钩子不得执行或逃逸。

#### K07 newsletter-generation — 简报生成

- **能力拆分：** 主题研究、候选筛选、摘要编排、来源链接、可交付简报。
- **参考：** `skills/public/newsletter-generation/SKILL.md`。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/newsletter-generation/`。
- **实现：** 沿用检索证据与 Markdown 产物；只生成和 Web 下载，不增加邮件发送／订阅入口。
- **前置：** K06、研究与文件交付。
- **验收：** 固定资料按日期筛选、去重且链接真实；真实主题生成简报。来源发布时间缺失应显示未知，过期内容不能冒充当日新闻，不产生邮件副作用。

#### K08 data-analysis — 表格分析与导出

- **能力拆分：** CSV／Excel 多文件装载、schema 检查、SQL 查询、统计摘要、结果表导出。
- **参考：** `skills/public/data-analysis/SKILL.md`、`scripts/analyze.py` 的 `load_files`／`_load_excel`／`_load_csv`／`action_inspect`／`action_query`／`action_summary`／`_export_results`。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/data-analysis/`。
- **实现：** 保留适用的数据脚本，DuckDB／openpyxl 固定进执行镜像；去掉运行时 pip 安装、`INSTALL spatial` 和全局 `/tmp/.data-analysis-cache`。缓存按 tenant/project/thread/task 隔离。限制 SQL 外部文件、扩展、网络和系统访问；XLS 单独实现解析器，不能用 openpyxl 声称支持旧 Excel。
- **前置：** K07、04 的 CSV／XLSX／XLS、执行镜像与资源限制。
- **验收：** 固定账表统计与预期精确相符，多文件同名 sheet 不覆盖，导出可重新读取；真实上传两张表完成联表分析。公式不执行、恶意 SQL 不越界、超内存可终止，XLS 与 XLSX 分别测。

#### K09 chart-visualization — 图表与地图

- **能力拆分：** 从数据选择图型、生成图表／地图、下载图像、解释可视化。
- **参考：** `skills/public/chart-visualization/SKILL.md`、`scripts/generate.js` 的 `generateChartUrl`／`generateMap`、同目录 26 类图表参考资料。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/chart-visualization/`。
- **实现：** 优先复用并公共化当前 AntV MCP 能力；上游 Node 脚本直连 `antv-studio.alipay.com` 与现有 MCP 不保证等价。建立 26 类逐项参数／产物对照；表格生成缺口单独补，不能以常见柱图通过代替全覆盖。外发原始数据必须符合授权策略。
- **前置：** K08、公共图表工具与图片产物。
- **验收：** 26 类各一确定性参数／结果用例，并检查远端返回实际文件；真实代表性图表和地图验收。坏坐标、过大数据、远端失败／错误 MIME、含敏感数据未获授权时有明确结果。

#### K10 frontend-design — 网页产物设计

- **能力拆分：** 设计方向、页面结构与视觉、HTML／CSS／JS 项目生成、打包交付。
- **参考：** `skills/public/frontend-design/SKILL.md`、`LICENSE.txt`。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/frontend-design/`。
- **实现：** 输出独立网页文件／项目包，使用隔离预览；不把生成代码插入平台应用，不改平台 Vue 开发规范。移除业务提示中强制 DeerFlow 品牌外链，保留法律要求的版权／许可。构建仅用批准依赖与固定镜像，不运行任意远端安装脚本。
- **前置：** K09、HTML 隔离预览与代码包产物。
- **验收：** 静态资源引用、打包、可访问性检查；真实需求生成页面并在 Web 预览／下载。恶意脚本不能读取平台 cookie／父页面。开发验收用 Playwright 合法，不向 Agent 提供浏览器操作工具。

#### K11 web-design-guidelines — 网页规范评审

- **能力拆分：** 获取规范、静态阅读网页代码、检查布局／可访问性／交互约定、输出定位明确的建议。
- **参考：** `skills/public/web-design-guidelines/SKILL.md`。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/web-design-guidelines/`。
- **实现：** 受控抓取规范并记录来源与版本哈希；评审上传的源文件或 K10 产物，不引入浏览器自动操作。静态不能证明的运行行为明确写“待运行验证”。
- **前置：** K10、规范抓取与代码只读访问。
- **验收：** 固定页面中的缺 label／低语义结构等问题定位正确；真实页面报告可复查。规范 URL 不可达时说明使用哪个已固定版本，不能伪造最新规范或动态页面测试结果。

#### K12 image-generation — 图片生成与编辑

- **能力拆分：** 结构化视觉描述、文生图、单／多参考图编辑、结果图交付。
- **参考：** `skills/public/image-generation/SKILL.md`、`scripts/generate.py` 的 `generate_image`／`_resolve_provider`、同目录模板资源。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/image-generation/`。
- **实现：** 复用现有 `apps/runtime-service/src/runtime_service/tools/images.py` 的生成／编辑能力及模型配置，补多参考图／参数差异；不再维护技能脚本自己的密钥体系。保留供应商能力对照，未接入供应商不标已支持；付费操作走批准后的工具权限和 HITL。
- **前置：** K11、图片工具授权治理、受信上传引用。
- **验收：** 固定 provider 响应检验引用和参数，真实文生图／参考图编辑可下载；错误 MIME、内容策略拒绝、超时与重复审批重放不误记成功、不重复付费。

#### K13 ppt-generation — 图像式演示文稿

- **能力拆分：** 大纲与逐页设计、逐页生成图片并保持风格、组合 PPTX、页图预览／下载。
- **参考：** `skills/public/ppt-generation/SKILL.md`、`scripts/generate.py` 的 `generate_ppt`。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/ppt-generation/`。
- **实现：** 图像生成走 K12，Pillow／python-pptx 组合在受限沙箱执行。原实现是图片型幻灯片；本项不冒称原生可编辑图表／文本，若需要全可编辑 PPT 另列需求。
- **前置：** K12、PPTX 生成／校验与批量图片预算。
- **验收：** 固定三张图生成三页 PPTX，可重新解析，页尺寸和顺序正确；真实三页演示可预览和下载。缺图、页数超预算、生成中取消保留已成功产物并报告未完成页。

#### K14 podcast-generation — 多角色播客

> 2026-09-15 用户决定 deferred：本批不接入供应商、不启用工具或Skill、不执行真实付费验收；恢复开发时仍按下方完整设计验收。

- **能力拆分：** 编写对白脚本、分角色 TTS、混音拼接、MP3 与文字稿交付。
- **参考：** `skills/public/podcast-generation/SKILL.md`、`scripts/generate.py` 的 `ScriptLine`／`Script`／`tts_node`／`mix_audio`／`generate_markdown`／`generate_podcast`／`text_to_speech_volcengine`／`text_to_speech_minimax`。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/podcast-generation/`。
- **实现：** TTS 改受控供应商工具；原脚本并发和重试纳入统一配额／幂等。上游 `mix_audio` 实际直接拼接音频字节；迁移后用固定 ffmpeg 执行镜像规范化并拼接，验证格式／时长，避免把字节连接当作可靠混音。保留角色／段落关联、失败片段与文字稿，不向 shell 下发供应商 key。
- **前置：** K13、至少一个已验收 TTS 服务、音频产物；09 长调用恢复底座在媒体阶段先完成。
- **验收：** 固定短 WAV 片段混音验证时长／顺序；真实双角色短播客可播放且文字稿对应。中间片段失败不能静默丢句，取消和重试不得把已完成片段重复计费。

#### K15 music-generation — 音乐生成

> 2026-09-15 用户决定 deferred：本批不接入供应商、不启用工具或Skill、不执行真实付费验收；恢复开发时仍按下方完整设计验收。

- **能力拆分：** 音乐描述、可选歌词、远端生成、MP3 交付。
- **参考：** `skills/public/music-generation/SKILL.md`、`scripts/generate.py` 的 `generate_music`（MiniMax）。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/music-generation/`。
- **实现：** 通过受控音乐工具提交，记录模型、付费审批、业务幂等键和真实返回；音频入工作区后才返回可信文件引用。供应商不支持幂等时未知提交不能盲重试。
- **前置：** K14、音乐服务凭据／配额与音频链路。
- **验收：** 固定 API 响应验证音频 MIME／长度与错误处理；真实短音乐可播放／下载。付费后网络断开显示结果未知并核对，不伪称失败后自动重新购买。

#### K16 video-generation — 异步视频生成（后续实施）

用户澄清：**K16与音视频大文件／Range是后续做，不是取消**。状态deferred，保留在23个公共Skills迁移清单，本批不实现。

- **能力：** 文本／参考图描述、提交任务、持久化远端handle、跟踪状态、取回MP4。
- **参考：** `skills/public/video-generation/SKILL.md`、`scripts/generate.py` 的 `_poll_video_task`／`_retrieve_file_url`／`_generate_video_minimax`／`_generate_video_gemini`／`generate_video`。
- **实现：** 工具审批后提交，复用09的持久任务、租约／fence、未知提交保护与授权续接；不在模型中长循环轮询。供应商密钥不进沙箱。
- **前置：** 09完整长任务与供应商协议验证；04音视频大文件／Range授权传输；08前端播放／任务交接。
- **验收：** 真实短视频、重启后取回同一任务、MP4内容／哈希、Range；ACK丢失、取消不支持、远端失败、重复通知不重复付费或虚假成功。

#### K17 skill-reviewer — 技能包安全与质量审查

- **能力拆分：** 读取包、资源关系分析、识别危险行为、规范检查、审查报告及保障程度说明。
- **参考：** `skills/public/skill-reviewer/SKILL.md`、同目录 `references/` 与 eval 资源；工具入口为 `backend/packages/harness/deerflow/tools/builtins/review_skill_package_tool.py`。分析实现目录为 `backend/packages/harness/deerflow/skills/review/`，读取其中 `analyzer.py`、`readers.py`、`models.py`、`renderer.py`、`resource_graph.py`。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/skill-reviewer/`；按实际逻辑量拟新增服务私有 `skill_review.py`。
- **实现：** 重写 `review_skill_package` 为本平台受限只读工具；可复用适用纯分析逻辑及规则资源，不导入 Harness。候选技能内容按不可信数据审查，不加载进运行技能列表、不执行候选脚本；静态阻断项和已验证行为分开。
- **前置：** P5约定范围及安全解包与候选包资源读取；已纳入范围的K01—K15 在此之前由开发验收流程审查，不依赖尚未迁移的 reviewer 自审。
- **验收：** 固定良性包／路径穿越／远端脚本／伪造工具权限／提示注入包，规则结果可复查；真实上传技能包得到报告。报告必须明确“静态通过不代表运行效果验证通过”。

#### K18 skill-creator — 创建、改进和打包技能

- **能力拆分：** 需求访谈、初始化 SKILL、补资源、验证、行为评估、改进描述、打包发布。
- **参考：** `skills/public/skill-creator/SKILL.md`、`LICENSE.txt`；`scripts/init_skill.py`、`quick_validate.py`、`package_skill.py`、`run_eval.py`、`improve_description.py`、`run_loop.py`、`aggregate_benchmark.py`、`generate_report.py`（脚本相对该 Skill 目录）。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/skill-creator/`；管理工具按实际需要放服务私有 `skill_tools.py`／`skill_storage.py`。
- **实现：** 保留初始化／校验／打包和评估素材；原 eval／description 改进依赖 Claude CLI，改用本平台受信 Deep Agent／官方 SDK 评估，独立 eval scope、不污染生产记忆。上游 `skill_manage` 替换为本平台候选版本管理，正式发布需 HITL，不写部署源码。
- **前置：** K17、技能版本存储、隔离评估与发布授权。
- **验收：** 创建一项文本整理技能，固定行为用例通过、真实请求能触发、打包重读完整；未通过 reviewer、目录穿越、名称冲突、未批准发布都不能启用。评估失败保留报告和原版本。

#### K19 find-skills — 查找与受控安装技能

- **能力拆分：** 按需求检索技能、比较来源、获取候选包、审查、安装到授权作用域。
- **参考：** `skills/public/find-skills/SKILL.md`、`scripts/install-skill.sh`。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/find-skills/`。
- **实现：** 移除 `npx skills add -g -y` 的宿主安装路径；受控 catalog／GitHub 下载固定修订，进入 K17／K18 流程。安装候选不等于启用，不执行第三方安装脚本、不自动获得其声明的权限。
- **前置：** K18、受控来源检索／下载、版本审查与发布流程。
- **验收：** 固定目录找到匹配包并保留来源哈希；真实 Web 搜索、确认安装、审查后启用。内容在审查后被替换、未知来源、同名污染、诱导全局安装均拒绝。

#### K20 bootstrap — 用户偏好与人格引导

- **能力拆分：** 多轮访谈、归纳风格与偏好、预览人格描述、确认后持久生效。
- **参考：** `skills/public/bootstrap/SKILL.md`、`templates/SOUL.template.md`、`references/conversation-guide.md`；原 `setup_agent(soul, description)` 交互意图。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/bootstrap/`。
- **实现：** 保留 5—8 轮引导的意图与模板；用官方 interrupt 和 06 的用户／项目偏好保存。确认的是风格与偏好，不允许修改 graph、模型授权、工具权限或平台系统指令；原 SOUL 语言规则在迁移记录中明确是否本地化。
- **前置：** K19、06 的显式记忆 CRUD 与偏好注入；必须在迁移 K20 前交付。
- **验收：** 固定问答生成可编辑偏好，真实确认后新线程生效；拒绝保存／删除后无隐式恢复，其他项目／用户不可见，偏好中的越权命令不能提升权限。

#### K21 surprise-me — 已启用技能组合推荐

- **能力拆分：** 发现当前技能、选择有意义的组合、说明提议、执行并交付组合产物。
- **参考：** `skills/public/surprise-me/SKILL.md`。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/surprise-me/`。
- **实现：** 只读取当前运行已启用、已验证且获授权的技能列表；按需求组合两个及以上技能，仍走普通 Deep Agent 规划与工具调用。付费、部署、发布继续审批，不能因为“惊喜”绕过授权。
- **前置：** K20、已验收技能能力描述。
- **验收：** 固定启用集不会选择未迁移项；真实组合“研究＋图表＋报告”交付可验证产物。可用技能不足时直接说明，不偷偷启用或安装新技能。

#### K22 vercel-deploy-claimable — 网页预览部署

- **能力拆分：** 打包网页、外发部署、取得 preview URL／claim URL、交付可访问预览。
- **参考：** `skills/public/vercel-deploy-claimable/SKILL.md`、`scripts/deploy.sh`；其 frontmatter 名称实际为 `vercel-deploy`，与目录 slug 不同。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/vercel-deploy-claimable/`。
- **实现：** 保留来源 slug 与公开技能名的显式映射；部署由受控工具执行。上游脚本上传到 `https://claude-skills-deploy.vercel.com/api/deploy`，无需用户凭据也属于外部发布，不能默认为安全／长期可用。先验证服务可用性和数据政策；审批展示精确文件清单／摘要／目标，排除密钥与无关文件，记录真实远端结果。若更换部署通道，记录行为差异再验收。
- **前置：** K21、K10 网页包、发布权限与外部副作用幂等。
- **验收：** 固定打包只含批准文件、审批后内容变更需重新确认；真实部署产生可访问链接。未批准不上传、远端超时结果未知不盲目重试、跨用户不可读取 claim 信息。外部服务不可用时本项 blocked，不把本地 ZIP 当部署通过。

#### K23 claude-to-deerflow — 原外部客户端桥接，拟改为平台内操作

- **能力拆分：** 原技能从 Claude 侧检查 DeerFlow 状态、查模型／技能／Agent、管理对话／历史／附件；涉及外部 CLI 与 DeerFlow HTTP。
- **参考：** `skills/public/claude-to-deerflow/SKILL.md`、`scripts/chat.sh`、`scripts/status.sh`。
- **目标：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/claude-to-deerflow/`。
- **建议实现：** 保留来源身份，改为当前 Web 中的授权平台操作技能：查询当前可用能力、读取允许的会话与文件、帮助用户选择下一步。用本平台受控业务工具和官方 SDK；不安装 Claude CLI、不连接 DeerFlow、不新增外部客户端产品，也不允许递归调用自己形成无限委派。
- **范围冲突：** 这不是原 CLI 桥接行为的原样等价迁移。D5 必须由用户确认改写口径；若要求原 CLI，则与“仅 Web／不运行 DeerFlow”冲突，需要明确调整范围。本项不能静默删除，也不能仅保存 SKILL 文件后标完成。
- **前置：** K22、08 的能力／会话／文件授权接口及 D5 评审。
- **验收：** 按获批后的功能矩阵逐项对照原状态／列表／会话／文件意图；真实 Web 操作能完成授权范围查询与文件读取。其他租户枚举、修改平台授权、向 DeerFlow 发请求、递归运行均被拒；若 D5 未确认则保持 blocked，不占用“23 项完成”名额。

## 任务拆分

### 公共准备

- [ ] K-G1：实现官方技能加载、只读挂载与 wheel 资源验证，目标为服务组合根／Backend 及 `pyproject.toml`。
- [ ] K-G2：实现来源清单、版本冻结、测试输入和 per-skill 验收记录；只保存实际采用资源，不顺手导入上游整个工具链。
- [x] K-G1/K-G2的K01必需切片：官方加载／只读工具保护、MIT与provenance、原文最小差异哈希、干净wheel打包与安装后资源读取通过；各后续Skill的资源／版本验收及自定义技能冻结仍逐项完成，见09。
- [ ] K-G3：K17 前完成候选包审查工具，K18 前完成自定义版本存储／隔离评估／发布授权；代码留服务私有模块。
- [ ] K-G4：K20 前交付记忆／偏好底座；K23 前确认 D5。依赖工作可以先做，但不得将未验收技能提前启用。

### 逐项执行台账

P4当前执行口径：每项的“后端实现与验证／前端交接／页面验收”分别见[P4三类进度表](phases/P4-研究与数据%20Skills.md#三类进度与推进规则)。本台账是整体状态：后端通过而页面后置时仍为partial；本轮允许在后端验证及交接完成后推进下一K，不将后置Web验收伪装成通过。下面所有未执行项维持未勾选。

| 任务 | 技能 | 当前状态 | 实施／验证记录 |
|---|---|---|---|
| [ ] K01 | deep-research | partial：后端done、交接done；页面deferred | [09资源、改动与证据](implementation/09-p4-k01-deep-research.md) |
| [ ] K02 | academic-paper-review | partial：后端done／交接done／页面deferred | [10批次记录](implementation/10-p4-k02-k07-batch.md) |
| [ ] K03 | github-deep-research | blocked：组合通过、GitHub匿名配额耗尽403；交接done／页面deferred | [10批次记录](implementation/10-p4-k02-k07-batch.md) |
| [ ] K04 | consulting-analysis | partial：报告范围done、图表依赖K09；交接done／页面deferred | [10批次记录](implementation/10-p4-k02-k07-batch.md) |
| [ ] K05 | systematic-literature-review | blocked：组合通过、arXiv 429／超时；交接done／页面deferred | [10批次记录](implementation/10-p4-k02-k07-batch.md) |
| [ ] K06 | code-documentation | partial：后端done、交接done；页面deferred | [10批次记录](implementation/10-p4-k02-k07-batch.md) |
| [ ] K07 | newsletter-generation | 后端done：正文fetch定向复验通过；交接done／页面deferred | [10批次记录](implementation/10-p4-k02-k07-batch.md) |
| [ ] K08 | data-analysis | 后端done：Docker／两表SQL／导出下载；交接done／页面deferred | [11批次记录](implementation/11-p4-k08-k11-batch.md) |
| [ ] K09 | chart-visualization | partial：25/26图型与代表模型链路通过，双轴远端blocked；交接done／页面deferred | [11批次记录](implementation/11-p4-k08-k11-batch.md) |
| [ ] K10 | frontend-design | 后端done：HTML/ZIP生成与只读下载复核；交接done／页面deferred | [11批次记录](implementation/11-p4-k08-k11-batch.md) |
| [ ] K11 | web-design-guidelines | 后端done：规范版本与file:line评审下载；交接done／页面deferred | [11批次记录](implementation/11-p4-k08-k11-batch.md) |
| [ ] K12 | image-generation | 后端partial、供应商blocked／交接done／页面deferred | 文生图、单图编辑成功；多参考图APIConnectionError待验，旧unknown不重提，见[12](implementation/12-p5-media-and-tasks.md) |
| [ ] K13 | ppt-generation | 后端done／交接done／页面deferred | Docker、上传图及三次AI生成→完整PPTX发布下载均通过，见[12](implementation/12-p5-media-and-tasks.md) |
| [ ] K14 | podcast-generation | deferred | 用户2026-09-15明确延迟开发；供应商及实际需要的长任务后置；视频和大文件另按K16后续计划实施 |
| [ ] K15 | music-generation | deferred | 用户2026-09-15明确延迟开发；供应商及实际需要的长任务后置；视频和大文件另按K16后续计划实施 |
| [ ] K16 | video-generation | deferred | 用户澄清为后续实施；保留完整任务及验收，不在本批实现 |
| [ ] K17 | skill-reviewer | 后端静态审查链路done；交接done／页面deferred | [13记录](implementation/13-p6-memory-and-skills.md) |
| [ ] K18 | skill-creator | 后端真实创建/候选/审查/文本评估复验done（1 passed，613.76s）；交接done／页面deferred | [14复验记录](implementation/14-p7-production-gates.md) |
| [ ] K19 | find-skills | 本地发现/候选导入/查询/报告done；远端导入未验；交接done／页面deferred | [15](implementation/15-cleanup-k19-and-v08.md) |
| [ ] K20 | bootstrap | 后端澄清→保存→新会话注入真实通过；交接done／页面deferred | [13记录](implementation/13-p6-memory-and-skills.md) |
| [ ] K21 | surprise-me | 后端推荐与网页/规范组合真实通过；交接done／页面deferred | [13记录](implementation/13-p6-memory-and-skills.md) |
| [ ] K22 | vercel-deploy-claimable | 静态包/审批/幂等已实现；默认关闭、真实发布未验、动态框架未实现；交接done／页面deferred | [13记录](implementation/13-p6-memory-and-skills.md) |
| [ ] K23 | claude-to-deerflow | deferred：用户明确后置 | 不复制、不实现、不启用 |

## 验证要求与记录

- [ ] 上游顶层目录集合与 K01—K23 一一对应，无漏项、重复项；slug 与 frontmatter 差异显式保留。
- [ ] 每项具备来源、能力差异、目标文件、依赖、确定性用例、真实模型 E2E 与负例证据。
- [ ] 自定义技能的版本升级、撤销、回退、在途运行冻结和多租户隔离测试通过。
- [ ] 离线安装构建可复现，无运行时全局安装／Claude CLI／DeerFlow 服务依赖，无凭据写入技能资源。
- 2026-09-13：完成 23 项源码与迁移规划；尚无技能迁移或行为验证完成。后续每项在本台账链接 `implementation/` 中的实际记录，并使用 done／partial／blocked／deferred 如实判定。

## 状态

K01—K02后端与交接done；K03/K05外部限流blocked，K04报告范围及K06后端done，K07正文证据已通过；K08/K10/K11后端done、K09累计25/26图型通过且双轴远端blocked，见11记录；K12/K13代码已完成，K13完整AI三页链路done，K12单图成功、多参考图连接异常仍partial，K14/K15用户deferred，K16及音视频大文件用户明确后续实施（deferred），K17/K18/K20/K21约定后端链路通过，K19本地发现通过/远端导入未验，K22默认关闭且真实发布未验，K23 deferred。逐项完整完成数仍为0（页面未验收）。K23由用户明确后置；前端页面按用户要求后置，后端／交接／页面分别登记。

2026-09-15复核更新：K18单项真实平台验收1 passed（613.76s），见[14记录](implementation/14-p7-production-gates.md)。K19旧失败为产物发布后的模型节点触发本地30秒超时；2026-09-16已在Dear组合根调整为120秒，本地发现/候选导入/查询/报告真实复验1 passed（269.27s），远端导入未验，见[15记录](implementation/15-cleanup-k19-and-v08.md)。
