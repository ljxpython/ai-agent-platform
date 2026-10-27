# DeerFlow Agent 技能全景能力与前端验收实操手册

> **文档状态：** 生效中
> **服务重启状态：** ✅ 已完成整栈重启（Runtime API/Worker, Platform API, Web 均已热加载最新代码与环境变量）
> **前端访问地址：** http://127.0.0.1:3000

---

## 目录
1. [服务重启确认](#1-服务重启确认)
2. [全量技能功能与前端触发验证总表](#2-全量技能功能与前端触发验证总表)
3. [前端逐项验证实操与预期产物指引](#3-前端逐项验证实操与预期产物指引)
   - [第一波：学术与深度调研类 (7项)](#第一波学术与深度调研类)
   - [第二波：数据分析与商业图表类 (2项)](#第二波数据分析与商业图表类)
   - [第三波：前端设计、规范与部署类 (3项)](#第三波前端设计规范与部署类)
   - [第四波：多模态生成与平台元技能类 (7项)](#第四波多模态生成与平台元技能类)
   - [安全边界收口类 (4项)](#安全边界收口类明确不开放)
4. [排障与常见问题排查](#4-排障与常见问题排查)

---

## 1. 服务重启确认

### ❓ 是否需要重启服务？
**绝对需要！**
因为本次排查涉及 `runtime-service` 底层的多项核心变更：
1. **网络代理直通**：根治了 `research_http.py`、`search.py`、`deployment.py`、`skills.py` 内部硬编码 `trust_env=False` 导致本地 Clash 代理被强行屏蔽的致命缺陷；
2. **GitHub 鉴权与配额**：`.env` 中写入了新的 `GITHUB_TOKEN`，API 配额从 60次/h 升至 5000次/h；
3. **官方推荐目录**：`skill_catalog.py` 中补齐了 `github-deep-research`、`systematic-literature-review`、`consulting-analysis`、`chart-visualization` 4 个技能进 `VERIFIED` 集合；
4. **底层容错加固**：`_evidence` 存盘空指针防御、Docker RPC List 退化强转。

### 🚀 重启执行结果
老王我已通过 `bash scripts/local-stack.sh restart` 帮你完成了全栈热重启：
```text
[stop] platform-web, platform-api, runtime-worker, runtime-api 已优雅停止
PostgreSQL 5432 & Redis 6379 连通性通过
Alembic 数据库版本对齐完成
[start] runtime-api pid=25881 (8123) -> ready (7s)
[start] platform-api pid=25997 (2142) -> ready (2s)
[start] platform-web pid=26083 (3000) -> ready (3s)
[done] local stack is ready: http://127.0.0.1:3000
```
**现在所有新代码和环境变量已 100% 在内存中生效，你可以直接在浏览器打开前端进行测试！**

---

## 2. 全量技能功能与前端触发验证总表

| 序号 | 技能名称 (Slug) | 它是什么？可以实现什么？ | 前端触发 Prompt 提问话术 | 预期前端交互与工具调用现象 |
| :--- | :--- | :--- | :--- | :--- |
| **【第一波：学术与深度调研类】** | | | | |
| 1 | **`deep-research`** | 深度多维度互联网调研，替代单一浅层搜索，涵盖事实、多方观点与证据链 | `请帮我深度调研人形机器人灵巧手行业的最新技术突破与商业落地现状` | Agent 自动调用 `search_web`（多次检索）和 `fetch_page`（抓取正文），沙箱自动沉淀存证文件，最终输出结构化 Markdown 调研报告。 |
| 2 | **`github-deep-research`** | 深度剖析 GitHub 仓库的架构、语言占比、提交活跃度、PR/Issue 与版本发布 | `请对 GitHub 仓库 ljxpython/ai-agent-platform 做一次深度架构与代码资产剖析` | Agent 触发 `github_query` 工具，连续请求 `info`、`languages`、`releases`、`commits` 等，5000 次/h 配额生效，输出仓库全景报告。 |
| 3 | **`academic-paper-review`** | 检索 arXiv 最新学术论文并进行深度学术评审，提取研究方法、创新点与局限性 | `请检索并评审最近关于 Multi-Agent LLM 架构的 arXiv 论文，并总结核心创新` | Agent 调用 `arxiv_search` 极速返回论文元数据，附带论文编号（如 `2505.24239`），生成学术评审意见与 BibTeX。 |
| 4 | **`systematic-literature-review`** | PRISMA 规范系统性文献综述，构建筛选流水线，产出高权威学术综述 | `请按照 PRISMA 标准对大模型长上下文记忆管理做一次系统性文献综述` | 调用 `arxiv_search` + `search_web`，明确标注 `abstract_only` 范围，产出综述 Markdown 工件并调用 `present_artifacts`。 |
| 5 | **`consulting-analysis`** | 麦肯锡/BCG 咨询级战略与市场分析，运用 PESTEL、SWOT、波特五力、STP 等框架 | `请使用 PESTEL 和波特五力模型，分析新能源汽车换电模式的商业可行性` | Agent 严格遵循“先出分析框架 -> 结合检索数据 -> 策略推演”流程，严禁数据凭空编造，产出咨询级报告。 |
| 6 | **`code-documentation`** | 代码库与工程文档生成，支持 README、API 参考、开发指南与 Changelog | `请为这个项目编写一份工业级的 README.md 和核心架构指南` | 若上传 ZIP 包调用 `parse_document` 内存只读解析，识别工程架构并输出规范文档，无执行风险。 |
| 7 | **`newsletter-generation`** | 新闻简报与行业周报生成，涵盖日报、周报、深度分析版式，严格校准发布时间 | `请整理一份本周关于生成式 AI 与智能体落地的科技新闻周报` | 调用 `search_web` + `fetch_page` 核实新闻事实，明确标注新闻发布日期（非抓取时间），输出精美排版简报。 |
| **【第二波：数据分析与商业图表类】** | | | | |
| 8 | **`data-analysis`** | 基于 DuckDB 列式引擎与 openpyxl 对上传的 CSV / Excel 数据进行结构探测、SQL 查询与统计摘要 | （上传销售/财务 CSV 或 Excel 后提问）<br>`请分析这个表格中各品类的销售总额，并计算平均客单价和占比` | Agent 调度沙箱执行 `analyze.py`，执行 DuckDB SQL 聚合查询，输出 Markdown 表格或过滤后的导出数据。 |
| 9 | **`chart-visualization`** | 包含折线、柱状、雷达、双轴、桑基、思维导图等 26 种 AntV 专业图表绘制 | `请帮我生成一张柱状图，展示 2026 年 Q1 各部门预算对比：研发 50万、市场 25万、销售 30万` | Agent 触发 `generate_bar_chart`（需前端点击审批通过），调用 AntV 引擎生成图片并下载存盘，前端展示图表结果。 |
| **【第三波：前端设计、规范与部署类】** | | | | |
| 10 | **`frontend-design`** | 生产级前端单页/组件设计，拒绝 AI 模板感，产出自包含 index.html 与 ZIP 工件 | `请设计一个极简现代深色风格的 AI 平台定价方案（Pricing）单页` | Agent 在沙箱编写自包含 `index.html`，打包为 ZIP，通过 `present_artifacts` 发布，前端出现可下载或沙箱预览卡片。 |
| 11 | **`web-design-guidelines`** | 按照 Vercel Web Interface Guidelines 官方标准，对前端代码进行静态规范审查 | `请审查刚刚生成的 index.html 是否符合 Web Interface Guidelines 设计与无障碍规范` | Agent 调用 `fetch_web_guidelines` 拉取最新规则，对照代码输出 `file:line` 格式的静态审查报告。 |
| 12 | **`vercel-deploy-claimable`** | 将生成的静态 Web 站点打包上传至 Vercel，生成 Preview 预览链接与认领 Claim 链接 | `请将刚才设计的前端项目部署到 Vercel` | 触发 `deploy_preview`（受控于平台开关，且强拦截代码中的 API Key/私钥泄漏与非法扩展名）。 |
| **【第四波：多模态生成与平台元技能类】** | | | | |
| 13 | **`image-generation`** | 结构化 Prompt 图像生成与编辑，支持多图参考，具备防重复扣费幂等收据 | `请生成一张极具未来感的赛博朋克风格城市夜景，16:9 比例` | Agent 构造结构化 Prompt 调用 `generate_image`（需人工审批通过），使用外部绘图 API 生成高清图片并沉淀资产。 |
| 14 | **`ppt-generation`** | 逐页生成幻灯片图片底图，通过沙箱 python-pptx 组装为包含演讲者备注的 PPTX | `请帮我制作一份 3 页的 AI Agent 平台架构汇报幻灯片（PPTX）` | Agent 规划结构、生成各页底图，沙箱执行 `generate.py` 拼装生成 `.pptx` 文件，通过 `present_artifacts` 发布下载。 |
| 15 | **`find-skills`** | 在平台技能目录与 GitHub 生态中检索新技能与能力扩展 | `平台里有哪些关于数据分析和图表可视化的技能？` | Agent 调用 `find_skills` 列出相关技能元数据与功能说明。 |
| 16 | **`skill-creator`** | 交互式生成符合平台规范的新技能包（SKILL.md、provenance、脚本与测试） | `我想开发一个专门抓取 Hacker News 热点的技能，帮我创建技能脚手架` | Agent 按照标准技能结构设计 YAML frontmatter 与工作流规范。 |
| 17 | **`skill-reviewer`** | 静态安全审查技能包，检查目录穿越、大文件、权限越界与执行风险 | `请审查一下这个技能包是否存在安全风险和未授权网络访问` | Agent 调用 `review_skill_package` 进行只读解析并给出合规报告。 |
| 18 | **`bootstrap`** | 针对新项目或空白工作区的初始化向导与上下文装配 | `我是新接手这个项目的开发者，请帮我梳理环境现状和快速上手路径` | Agent 梳理项目边界、知识库与能力清单。 |
| 19 | **`surprise-me`** | 动态组合已有技能，打造令人惊喜的纯原生互动单页或创意小品 | `给我来点好玩的惊喜（Surprise me）` | Agent 遵循“自包含零外部依赖、Web Audio API 合成声音、产物即刻发布”原则，生成交互单页把玩。 |
| 20 | **`runtime-smoke`** | 运行时健康自检与沙箱执行能力探针 | `运行一次环境健康自检` | 验证沙箱执行、文件读写与环境基础能力。 |
| **【安全边界收口类（明确不开放）】** | | | | |
| 21-24 | **`music` / `podcast` / `video` / `claude-to-deerflow`** | 音频、播客、视频生成及外部转换器 | `帮我生成一首背景音乐 / 播客音频 / 短视频` | 🔒 Agent 在 Prompt 层严格阻断，如实告知用户：“播客、音乐、视频生成尚未开放”，杜绝大模型盲目执行外部脚本。 |

---

## 3. 前端逐项验证实操与预期产物指引

在浏览器访问 **`http://127.0.0.1:3000`**，进入任一 Project（例如之前测试的 `dear-agent` 会话），按照以下提示词逐一发送测试：

### 🎯 测试 1：GitHub 深度调研（验证 Token 5000 次/h 与多操作）
- **输入话术**：
  ```text
  请帮我调研 GitHub 仓库 ljxpython/ai-agent-platform 的主要编程语言分布、最近的 Release 版本和提交活跃度。
  ```
- **预期现象**：
  1. 思考链展示正在调用 `github_query` 工具（`operation="languages"`、`operation="releases"`、`operation="commits"` 等）；
  2. 不再出现之前 403 限流或 `runtime.execution_failed` 报错；
  3. 几秒内返回真实的仓库语言占比（Python, Vue, TypeScript 等）和详细数据。

---

### 🎯 测试 2：学术论文检索（验证 arXiv 代理打通与 XML 解析）
- **输入话术**：
  ```text
  请检索最近关于 Multi-Agent LLM 架构的 arXiv 论文，列出前 2 篇的标题、作者和摘要核心观点。
  ```
- **预期现象**：
  1. Agent 立即调用 `arxiv_search`（入参 `query="Multi-Agent LLM", max_results=2`）；
  2. 得益于 `trust_env=True` 代理修复，海外 `export.arxiv.org` 在 1 秒内响应；
  3. 返回真实论文（如 `2505.24239`），并列出摘要、PDF 链接与存证路径。

---

### 🎯 测试 3：AntV 商业图表生成（验证 AntV MCP 与图片下载）
- **输入话术**：
  ```text
  请帮我绘制一张柱状图，展示 2026 年团队 Q1 业绩：第一组 120万，第二组 95万，第三组 140万。
  ```
- **预期现象**：
  1. Agent 提出调用 `generate_bar_chart` 工具；
  2. 前端界面弹出【审批（Approval）】卡片；
  3. 点击【批准/同意】后，后台自动拉起 AntV MCP 服务生成图片并下载至本地；
  4. 对话区展示高清图表渲染结果或图表文件路径。

---

### 🎯 测试 4：DuckDB 数据分析（验证 Excel/CSV SQL 分析）
- **实操步骤**：
  1. 在输入框点击附件上传一个简单的 CSV（例如包含 `category,amount` 两列）；
  2. 发送提示词：
     ```text
     请分析上传的这份数据，计算总金额以及按分类汇总的平均值。
     ```
- **预期现象**：
  1. Agent 调用沙箱执行 `analyze.py --action query`；
  2. DuckDB 极速计算出聚合统计结果，输出整齐的 Markdown 表格。

---

### 🎯 测试 5：现代前端设计（验证自包含 index.html 与 ZIP 工件交付）
- **输入话术**：
  ```text
  请设计一个现代极简深色风格的 AI 智能体控制台 Dashboard 页面（包含侧边栏导航和几张指标卡片）。
  ```
- **预期现象**：
  1. Agent 编写自包含的 `index.html`，并打包为 `site.zip`；
  2. 调用 `present_artifacts` 交付工件；
  3. 前端右侧或消息下方出现 HTML 预览卡片与 ZIP 下载按钮。

---

### 🎯 测试 6：创意互动小品（验证 Surprise Me 与 Web Audio 原生音效）
- **输入话术**：
  ```text
  Surprise me! 给我做个有趣的单页解压小游戏。
  ```
- **预期现象**：
  1. Agent 遵循单文件自包含、零外部网络音频依赖原则；
  2. 极速生成一个 Canvas 或 CSS 动效的解压小游戏，使用 Web Audio API 合成点击音效；
  3. 产物即刻发布，用户可直接在沙箱内把玩交互。

---

## 4. 排障与常见问题排查

如果测试过程中遇到任何异常，请按以下检查点排障：

1. **海外网络依赖排查**：
   - 本地必须保持科学上网代理（Clash Verge 监听 `127.0.0.1:7897` 处于运行状态）；
   - 由于我们已在代码中开启了 `trust_env=True`，所有请求会自动借道本地代理访问 GitHub、arXiv、Tavily；
2. **查看实时后端日志**：
   - Runtime 日志：`rtk bash scripts/local-stack.sh logs runtime-api`
   - Worker 日志：`rtk bash scripts/local-stack.sh logs runtime-worker`
   - Platform API 日志：`rtk bash scripts/local-stack.sh logs platform-api`
3. **查看进程健康度**：
   - 随时运行 `rtk bash scripts/local-stack.sh status`，确认 4 大组件全部显示 `running` 与 `yes`。
