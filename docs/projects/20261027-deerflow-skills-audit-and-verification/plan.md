# DeerFlow Skills 全量迁移对齐、触发验证与缺陷治理工程 - 整体方案

## 背景
在排查前序 `github_query` 工具失败及远程沙箱 RPC 导致的 `runtime.execution_failed` 崩溃时发现，虽然本平台的 `dearflow_agent` 借鉴并迁移了 `deer-flow` 的大量 Skills，但在实际运行环境中：
1. 部分工具和技能存在隐式依赖（如沙箱环境中的 Python 脚本、外部 API 密钥、反序列化数据契约等）；
2. 缺少系统性的技能触发手册与自动化/人工验收基准，导致用户在前端提问时难以确定技能是否被命中、是否成功调用了底层工具；
3. 需要全面清查 `deer-flow` 的全部技能，拉通对比当前项目现状，发现潜在缺陷并就地修复。

---

## 技能全景对照与就绪矩阵（25 项全量梳理）

### 一、学术与深度调研类（7 项）

| 技能名称 (Slug) | deer-flow | 当前项目 | 底层依赖工具/脚本 | 官方打标状态 | 触发方式与 Prompt 示例 | 验收产物与标准 |
|---|---|---|---|---|---|---|
| **deep-research** | ✅ | ✅ | `search_web` (Tavily), `fetch_page` (Jina/httpx), `present_artifacts` | `VERIFIED` | “帮我深度调研关于人形机器人灵巧手行业现状” / “请针对 AI Agent 记忆机制做一份深度研究报告” | 必须调用 `search_web` + 多次 `fetch_page`，最终生成 Markdown 研究报告并由 `present_artifacts` 交付 |
| **github-deep-research** | ✅ | ✅ | `github_query` (GitHub REST API), `search_web`, `fetch_page` | 支持（刚修复） | “请对 GitHub 仓库 ljxpython/ai-agent-platform 做一次深度架构剖析” / “分析仓库 facebook/react 的 issues 和 release 现状” | 命中 `github_query` 工具（operation=summary/issues/releases 等），输出结构化调研证据，禁止 403 限流与崩溃 |
| **academic-paper-review** | ✅ | ✅ | `arxiv_search` (arXiv API), `present_artifacts` | `VERIFIED` | “帮我检索并评审最近关于 Multi-Agent 架构的学术论文” / “请针对 Transformer 变体检索 arXiv 论文并做横向对比” | 命中 `arxiv_search` 提取论文元数据/摘要，去重后生成结构化论文评审报告 |
| **systematic-literature-review** | ✅ | ✅ | `arxiv_search`, `search_web`, `scripts/arxiv_search.py` | 迁移完成待验 | “请按照 PRISMA 规范对我给出的研究课题做一份系统性文献综述（SLR）” | 严格遵循 PRISMA 流程（识别、筛选、合格性、纳入），产出 Markdown 综述及 `.bib` BibTeX 文件 |
| **consulting-analysis** | ✅ | ✅ | `search_web`, `fetch_page`, 咨询方法论框架 | 迁移完成待验 | “请使用 MECE 原则和波特五力模型，分析新能源汽车换电模式的商业可行性” | 运用成熟咨询框架，分层推导，产出麦肯锡/BCG 风格咨询建议书 |
| **code-documentation** | ✅ | ✅ | `github_query`, `read_file`, `grep`, `ls` | `VERIFIED` | “请阅读我们项目 /workspace 中的代码，生成一份完整的开发指南与 API 文档” | 针对指定代码文件或 GitHub 仓库，提取架构拓扑、模块职责与函数签名，生成技术文档 |
| **newsletter-generation** | ✅ | ✅ | `search_web`, `fetch_page`, `present_artifacts` | `VERIFIED` | “帮我编写一份本周 AI 开源领域精选技术周刊（Newsletter）” | 抓取最新新闻与发布记录，格式化为包含导读、亮点、分析排版的 Newsletter Markdown |

---

### 二、数据分析与商业图表类（2 项）

| 技能名称 (Slug) | deer-flow | 当前项目 | 底层依赖工具/脚本 | 官方打标状态 | 触发方式与 Prompt 示例 | 验收产物与标准 |
|---|---|---|---|---|---|---|
| **data-analysis** | ✅ | ✅ | `parse_document` (Excel/CSV), `execute` (执行 `scripts/analyze.py`) | `VERIFIED` | 附件上传表格后发：“请帮我分析这份销售数据，计算各区域环比增长和异常值” | 必须使用沙箱 `execute` 执行 Python 分析脚本，输出统计摘要与清洗后的数据 CSV |
| **chart-visualization** | ✅ | ✅ | 26 种 `generate_*_chart` 工具 (AntV G2/S2), `scripts/generate.js` | 迁移完成待验 | “帮我画一张展示 2026 年 Q1-Q3 营收趋势的折线图” / “生成一个饼图展示市场份额占比” | 调用对应的 `generate_line_chart` 等图表工具，前端渲染图片或图表产物（需人机协同审批） |

---

### 三、前端设计、网页规范与部署类（3 项）

| 技能名称 (Slug) | deer-flow | 当前项目 | 底层依赖工具/脚本 | 官方打标状态 | 触发方式与 Prompt 示例 | 验收产物与标准 |
|---|---|---|---|---|---|---|
| **frontend-design** | ✅ | ✅ | 纯代码生成能力, `write_file`, `present_artifacts` | `VERIFIED` | “请设计一个极简现代风格的 SaaS 平台定价页面（包含月付/年付切换和3档方案）” | 生成包含 HTML + Tailwind CSS 的完整响应式单页，可通过 `present_artifacts` 打包交付 |
| **web-design-guidelines** | ✅ | ✅ | `fetch_web_guidelines` (抓取官方规范) | `VERIFIED` | “请根据 Web 界面最佳实践规范，审查以下 UI 代码的可访问性与交互问题：...” | 命中 `fetch_web_guidelines` 获取权威设计基线，给出针对性审查与重构建议 |
| **vercel-deploy-claimable**<br>*(deer: vercel-deploy)* | ✅ | ✅ | `deploy_preview` (打包上传 Vercel API), `scripts/deploy.sh` | 改造完成待验 | “请把 /workspace/work/dist 下构建好的前端页面部署到 Vercel 预览环境” | 打包静态网页资产，调用 `deploy_preview` 获得安全的 Claimable 预览链接 |

---

### 四、多模态生成与媒体类（5 项）

| 技能名称 (Slug) | deer-flow | 当前项目 | 底层依赖工具/脚本 | 官方打标状态 | 触发方式与 Prompt 示例 | 验收产物与标准 |
|---|---|---|---|---|---|---|
| **image-generation** | ✅ | ✅ | `generate_image`, `edit_image`, `get_media_task` | 迁移完成待验 | “请为我的科幻小说生成一张赛博朋克风格的雨夜城市全景插画” | 经用户审批后调用 Image Provider 生成图片，记录外部任务收据，禁止重复购买 |
| **ppt-generation** | ✅ | ✅ | `generate_image`, `execute` (执行 `scripts/generate.py` 合成 PPTX) | `VERIFIED` | “请为我制作一份 5 页的 AI 智能体技术分享 PPTX，主题是多智能体协同” | 规划大纲，逐页生成高分辨率幻灯片图片，在沙箱运行 python-pptx 合成真实 PPTX |
| **music-generation** | ✅ | ❌ | 音乐生成服务（Suno/Udio 类接口） | **明确未开放** | 系统提示词硬约束：“播客、音乐、视频生成尚未开放，不调用上游脚本绕过” | 不开放，若用户提出请求应礼貌拒绝并说明边界 |
| **podcast-generation** | ✅ | ❌ | 多角色音频 TTS / 对话脚本合成 | **明确未开放** | 同上 | 不开放 |
| **video-generation** | ✅ | ❌ | 视频大模型生成服务 | **明确未开放** | 同上 | 不开放 |

---

### 五、平台元技能与辅助工具类（8 项）

| 技能名称 (Slug) | deer-flow | 当前项目 | 底层依赖工具/脚本 | 官方打标状态 | 触发方式与 Prompt 示例 | 验收产物与标准 |
|---|---|---|---|---|---|---|
| **find-skills** | ✅ | ✅ | `list_skills`, `find_skills` | 迁移完成待验 | “平台有哪些可以用来做数据可视化的技能？” / “帮我找找看有没有处理学术论文的技能” | 检索当前租户公开与自定义技能库，推荐匹配技能与使用说明 |
| **skill-creator** | ✅ | ✅ | `write_file`, `review_skill_package`, `upload_skill` | 迁移完成待验 | “我想创建一个专门用来分析 SQL 慢查询的自定义 Skill，请帮我生成完整的技能包结构” | 生成规范的 `SKILL.md`（带准确 frontmatter）、`scripts/` 与说明，打包为符合治理标准的 Skill |
| **skill-reviewer** | ✅ | ✅ | `review_skill_package` | 迁移完成待验 | “帮我审查一下刚编写的技能包结构是否符合规范、触发词是否精准、是否存在注入风险” | 验证技能的结构完整性、evals 测试集、元数据安全性 |
| **bootstrap** | ✅ | ✅ | 对话交互, `write_file` (`SOUL.md`) | 迁移完成待验 | “我想对你进行初始设定，定制一个专注于医疗器械法规合规的专家形象” | 通过多轮自适应提问，提炼并生成持久化角色定义文件 `SOUL.md` |
| **surprise-me** | ✅ | ✅ | 综合多技能动态编排 | 迁移完成待验 | “给我一个惊喜（surprise me）” / “展示一下你最拿手的综合技能” | 自动组合调研、创意设计、数据分析或图表，交付一次惊艳的复合体验 |
| **runtime-smoke** | ❌ | ✅ | `check_text.py` (平台特有) | 平台专有 | 内部冒烟测试使用 | 验证 TXT 读取、人机审批流与工件发布链路 |
| **claude-to-deerflow** | ✅ | ❌ | Claude 技能转换器 | 未迁移 | 外部转换工具，暂无平台原生需求 | 暂缓评估 |

---

## 缺陷排查重点与攻防推演

在逐个技能验证过程中，重点防范以下 4 类典型暗坑：
1. **跨沙箱 RPC 序列化破坏**：类似刚才修复的 `_evidence`，检查是否有其他工具（如 `data-analysis` 或 `ppt-generation` 执行脚本后的返回值）将元组退化为列表导致上层框架抛出 `ValueError`。
2. **沙箱容器环境缺失第三方库**：
   - `data-analysis` 需要沙箱中有 `pandas`, `openpyxl`；
   - `ppt-generation` 需要沙箱中有 `python-pptx`, `Pillow`。
3. **外部 API 凭据与限流容错**：
   - `image-generation` 与 `ppt-generation` 对 `IMAGE_25_URL` / `IMAGE_25_KEY` 的连通性；
   - `search_web` 对 `TAVILY_API_KEY` 的配额与连通性。
4. **系统提示词（System Prompt）对技能的触发引导是否充分**：
   - 检查 `prompts.py` 中是否有抑制大模型命中技能的负向提示；
   - 检查 `skill_catalog.py` 中的 `VERIFIED` 集合是否应动态扩充。
