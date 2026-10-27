# DeerFlow Skills 全量迁移对齐、触发验证与缺陷治理工程 - 任务拆分

## Phase 1: 学术文献与深度调研类技能验证与排查

### Task 1.1: `deep-research` 链路实操与多轮抓取验证
- **目标：** 验证 `search_web` + `fetch_page` + `_evidence` 在本地与远程 Docker 沙箱下的连通性与交付闭环。
- **触发 Prompt：** `帮我深度调研关于人形机器人灵巧手行业现状`
- **预期：** 成功调用搜索与页面抓取，来源写入证据库，最终产出 Markdown 报告并经由 `present_artifacts` 交付。
- **状态：** `[x]` 已验证（Tavily search + Jina extract 实测通过，修复 trust_env 代理连通性，证据文件哈希存盘正常）

### Task 1.2: `github-deep-research` 真实 Token 额度与深度操作复验
- **目标：** 验证新配置的 `GITHUB_TOKEN` 在不同 operation（`info`, `readme`, `languages`, `releases`, `issues`）下的稳定性。
- **触发 Prompt：** `请对 GitHub 仓库 ljxpython/ai-agent-platform 做一次深度架构与代码资产剖析`
- **预期：** 多轮 API 请求 100% 成功，5000 次/小时高配额生效，0 报错。
- **状态：** `[x]` 已验证（10 个操作全量实测通过，Token 注入与 401 容错生效，5000 次/h 额度正常）

### Task 1.3: `academic-paper-review` & `systematic-literature-review` 论文检索链验证
- **目标：** 验证 `arxiv_search` 工具及其 XML 解析、去重机制、BibTeX 导出。
- **触发 Prompt：** `请检索并评审最近关于 Multi-Agent 架构的学术论文，并生成标准的 BibTeX 引用列表`
- **预期：** 正常返回 arXiv 论文元数据，生成学术格式总结。
- **状态：** `[x]` 已验证（修复 research_http.py trust_env=True 与 _evidence 空指针保护，真实拉取 2505.24239 论文并生成证据）

### Task 1.4: `consulting-analysis` & `newsletter-generation` & `code-documentation` 验证
- **目标：** 验证结构化输出类技能与文件读取工具链的装配完整性。
- **触发 Prompt：** `请使用 MECE 原则分析新能源汽车换电商业可行性`
- **预期：** 规范输出咨询分析报告，不报工具缺失。
- **状态：** `[x]` 已验证（SKILL.md 规范完整，补齐 skill_catalog.py VERIFIED 推荐集合，ZIP/PDF 解析单测全绿）

---

## Phase 2: 数据分析与商业图表类技能验证与排查

### Task 2.1: `data-analysis` 沙箱脚本与 Excel/CSV 解析排查
- **目标：** 检查 `scripts/analyze.py` 在当前 Docker 沙箱镜像（`runtime-agent-workspace:p5-v2`）中的执行可行性，排查 Python 依赖（duckdb/openpyxl/xlrd）。
- **验证项：** 模拟沙箱内执行 `analyze.py`，确保无缺失依赖报错。
- **状态：** `[x]` 已验证（沙箱镜像预装 duckdb/openpyxl/xlrd，实测 CSV 与多 Sheet Excel 的 inspect/query/summary 三组操作全部秒级跑通）

### Task 2.2: `chart-visualization` 26 种 AntV 图表工具装配与渲染流排查
- **目标：** 检查 `chart-schemas.json` 与 `generate_*_chart` 工具执行链路，排查 AntV 渲染或降级机制。
- **状态：** `[x]` 已验证（补全 skill_catalog VERIFIED 推荐，26 种图表参数模型归一化与校验契约通过，真实拉起 AntV MCP 成功生成柱状图/折线图/雷达图并落地本地资产）

---

## Phase 3: 前端设计、网页规范与部署类技能验证与排查

### Task 3.1: `frontend-design` 界面生成与工件交付验证
- **目标：** 验证生成完整交互式 HTML/Tailwind CSS 页面并打包工件的流程。
- **触发 Prompt：** `请设计一个极简现代风格的 SaaS 平台定价页面`
- **状态：** `[x]` 已验证（验证自包含 index.html + 本地 CSS/JS 打包为 ZIP 并在 ArtifactWorkspace 发布，MIME 与不可变沙箱展示正常）

### Task 3.2: `web-design-guidelines` 官方规范抓取验证
- **目标：** 验证 `fetch_web_guidelines` 访问 Vercel Guidelines 时的 ETag 缓存与内容校验。
- **状态：** `[x]` 已验证（实测直连 raw.githubusercontent.com 秒级抓取 8KB 规范，SHA-256 存证完整，静态审查契约通过）

### Task 3.3: `vercel-deploy-claimable` 部署打包验证
- **目标：** 验证 `deploy_preview` 工具的静态文件打包与 Claimable 协议签名。
- **状态：** `[x]` 已验证（修复 deployment.py trust_env=True，实测 deployment_package 转换 tar.gz、Secret 拦截与非法扩展名阻断）

---

## Phase 4: 多模态生成与平台元技能验证与排查

### Task 4.1: `image-generation` 与外部任务状态机验证
- **目标：** 验证 `IMAGE_25_URL` 凭据连通性、幂等性 key 机制与生成流程。
- **状态：** `[x]` 已验证（IMAGE_25_URL/KEY/MODEL 凭据齐备，ExternalTaskStorage 幂等建单、扣费收据防重机制完备）

### Task 4.2: `ppt-generation` 幻灯片生成与沙箱 PPTX 拼装排查
- **目标：** 检查 `skills/ppt-generation/scripts/generate.py` 的沙箱执行命令，验证 `python-pptx` 在沙箱中是否可用。
- **状态：** `[x]` 已验证（沙箱与本地 Pillow/python-pptx 预装齐备，实测 CLI generate.py 生成 16:9 演示文稿及演讲者备注 100% 成功）

### Task 4.3: `find-skills` & `skill-creator` & `skill-reviewer` 元技能闭环
- **目标：** 验证 `list_skills`、`review_skill_package` 的目录遍历与只读检查。
- **状态：** `[x]` 已验证（修复 import_skill 中 trust_env=True，目录遍历与只读边界完备，治理单测 100% 通过）

---

## 进度追踪
- [x] Phase 1 完成
- [x] Phase 2 完成
- [x] Phase 3 完成
- [x] Phase 4 完成
