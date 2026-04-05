<h1 align="center">企业级 AI Agent 平台</h1>

<p align="center"><strong>面向二次开发与企业落地的 AI Agent 平台底座</strong></p>

<p align="center"><a href="README.en.md">English</a> | 中文</p>

<p align="center">
  <img src="https://img.shields.io/badge/LangGraph-1.0%2B-0E9F6E" alt="LangGraph" />
  <img src="https://img.shields.io/badge/LangChain-1.2%2B-1C7ED6" alt="LangChain" />
  <img src="https://img.shields.io/badge/FastAPI-0.133%2B-009688" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Next.js-15.5-black" alt="Next.js" />
  <img src="https://img.shields.io/badge/React-19.1-61DAFB" alt="React" />
  <img src="https://img.shields.io/badge/MCP-Enabled-7C3AED" alt="MCP" />
  <img src="https://img.shields.io/badge/README-EN%2FZH-F59E0B" alt="README EN/ZH" />
</p>

<p align="center"><a href="#system-overview">系统总览</a> · <a href="#frontend-entry">前端入口</a> · <a href="#quick-start">快速开始</a> · <a href="docs/deployment-guide.md">部署文档</a> · <a href="docs/CHANGELOG.md">更新日志</a> · <a href="docs/commit-and-changelog-guidelines.md">提交规范</a> · <a href="#acknowledgements">致谢参考</a> · <a href="#ai-deploy">AI代理部署</a></p>

基于 `LangGraph / LangChain` 的企业级 AI 平台架构，可在此基础上进行二次开发。  
它把**平台治理层**和**Agent Runtime 执行层**拆开，既支持平台侧的认证、项目管理、审计、catalog 管理，也支持 Agent 侧的图编排、模型装配、Tools / MCP / Skills 接入与快速调试，适合作为企业内部 AI 平台和智能体应用的基础骨架。

当前仓库默认提供一套五服务本地联调方案，适合：

- 想基于主流 Agent 技术栈做二次开发的团队
- 想同时建设平台能力和 Agent 执行能力的项目
- 想快速验证 LangGraph Runtime、Agent 行为和前端交互的开发者
- 希望把 AI 协同开发真正纳入工程流程的团队

> 想先理解当前项目为什么这么设计、后续应该按什么范式继续开发，可先看 [当前项目开发范式说明](docs/development-paradigm.md)。

<a id="frontend-entry"></a>

## 当前前端与推荐入口

`apps/platform-web-vue` 已作为新的 Vue 迁移前端正式落地，并已接通首批真实平台页面：

- `overview`
- `projects`
- `users`
- `assistants`
- `me`
- `security`
- `audit`

迁移规划、技术栈决策、模块交付顺序与当前清单统一维护在：

- [docs/platform-web-sub2api-migration/README.md](docs/platform-web-sub2api-migration/README.md)

当前建议这样理解仓库里的几个前端：

- `apps/platform-web-vue`：当前推荐使用的前端工作台宿主，后续平台前端迁移和持续开发默认都在这里推进
- `apps/platform-web`：历史平台前端与兼容入口，保留用于迁移对照和必要兼容
- `apps/runtime-web`：直连 Runtime 的调试前端，适合做 Agent 调试与交互验证

如果你是第一次跑这个仓库，建议先区分清楚两件事：

- 想快速跑通仓库默认联调：按根目录脚本启动，打开的是 `apps/platform-web-vue`
- 想回看历史实现或做迁移对照：按需单独启动 `apps/platform-web`

## AI 持续编程 Harness

这个仓库不只是“放了一堆代码”，而是已经形成了一套可以指导 AI 代理持续开发、持续联调、持续验收的工程 Harness。

这里说的 Harness，不是单个工具，而是一整套受控的工程外壳：

- `边界`：平台治理、运行时执行、调试前端、结果域服务已经拆层，AI 不需要在一个大泥球里瞎改
- `契约`：本地部署 contract、环境变量矩阵、接口命名、默认启动顺序和账号口径都已固定
- `范式`：`runtime-service`、`platform-web-vue`、`Resources / Playbook`、迁移手册和样例页面已经沉淀出可复用范式
- `闭环`：根级脚本、健康检查、烟测清单、验收文档、CHANGELOG 和 release runbook 已形成可执行交付链路

一句话说，这个仓库已经不是“让 AI 随便写代码”，而是“让 AI 在明确边界、稳定契约和现成范式中持续完成开发”。

## 这个项目解决什么问题

很多 Agent 项目能跑 demo，但一到真实工程场景就容易混乱：平台治理、运行时执行、调试入口、环境配置全耦在一起，后面越改越难受。

这个仓库的目标很明确：

- 用 `LangGraph / LangChain` 主流生态构建企业级 AI 平台架构，不重新发明一套封闭框架
- 把平台层和运行时层解耦，便于分工、演进和交付
- 提供可复用的 Runtime 执行骨架，而不是一次性 demo
- 给后续业务二开和测试场景接入预留空间

## 前端效果展示

如果你想先看当前平台前端已经做到了什么程度、页面大致长什么样，以及前端这部分是怎么组织和展示的，可以直接看这篇记录：

- [平台前端效果展示与介绍](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/20260325_platform_frontend_intro.md)

这篇内容更偏平台前端视角，适合快速了解当前平台工作台的页面效果、工作区结构和一些实际展示结果。

![平台前端效果展示](docs/assets/image-20260325161139758.png)

<a id="system-overview"></a>

## 系统总览

当前根目录默认联调脚本会启动 5 个核心应用：

- `apps/interaction-data-service`：结果域数据服务 / 工作流结果落库与查询
- `apps/platform-api`：平台后端 / 控制面 API
- `apps/platform-web-vue`：正式平台前端宿主 / 管理台入口
- `apps/runtime-service`：LangGraph 执行层 / Agent Runtime
- `apps/runtime-web`：直连 Runtime 的调试前端

### 两条主链路

- 平台链路：`platform-web-vue -> platform-api -> runtime-service`
- 调试链路：`runtime-web -> runtime-service`

### 几个前端分别干什么

- `platform-web-vue`：当前推荐的迁移前端宿主，承接平台工作台、Agent 页面和后续正式前端开发
- `platform-web`：历史平台前端与兼容入口，适合回看旧链路和对照迁移结果
- `runtime-web`：适合做 Agent 调试、交互验证、Runtime 快速迭代

## 架构图

![系统架构图](docs/assets/system-architecture.zh.svg)

<a id="quick-start"></a>

## 快速开始

### 默认启动顺序

1. `runtime-service`
2. `interaction-data-service`
3. `platform-api`
4. `platform-web-vue`
5. `runtime-web`

### 根目录脚本

```bash
scripts/dev-up.sh
scripts/check-health.sh
scripts/dev-down.sh
```

这三个脚本分别对应：

- 启动：`scripts/dev-up.sh`
- 健康检查：`scripts/check-health.sh`
- 停止：`scripts/dev-down.sh`

### 如果你想单独启动 `platform-web-vue`

根目录默认脚本已经会启动 `apps/platform-web-vue`。

如果你要单独调试新的平台前端，也可以这样启动：

```bash
VITE_DEV_PORT=3002 pnpm --dir "apps/platform-web-vue" dev
```

然后打开：

- `platform-web-vue`：`http://127.0.0.1:3002`

这样不会和默认的 `platform-web-vue:3000` 端口冲突。

### 默认本地端口

- `interaction-data-service`：`8090`
- `runtime-service`：`8123`
- `platform-api`：`2024`
- `platform-web-vue`：`3000`
- `runtime-web`：`3001`

### 成功启动后访问地址

- `platform-web-vue`：`http://127.0.0.1:3000`
- `runtime-web`：`http://127.0.0.1:3001`

### 最小健康检查

```bash
curl http://127.0.0.1:8090/_service/health
curl http://127.0.0.1:8123/info
curl http://127.0.0.1:2024/_proxy/health
curl http://127.0.0.1:2024/api/langgraph/info
```

如果 `platform-api` 的 `/api/langgraph/info` 返回 `200`，且 `interaction-data-service` 的 `/_service/health` 返回 `200`，说明平台链路和结果落库链路都已基本打通。

![本地联调启动流程图](docs/assets/local-dev-startup-flow.zh.svg)

## 仓库结构

```text
AITestLab/
├── apps/
│   ├── interaction-data-service/
│   ├── platform-api/
│   ├── platform-web/
│   ├── platform-web-vue/
│   ├── runtime-service/
│   ├── runtime-web/
│   └── ...
├── docs/
├── scripts/
└── archive/
```

- `apps/`：业务应用目录，包含默认联调服务、迁移中的新前端宿主以及参考工程
- `docs/`：部署、开发、约束和背景文档
- `scripts/`：统一启动、停止、健康检查脚本
- `archive/`：历史归档说明

<a id="docs-by-goal"></a>

## 按目标阅读文档

![文档导航图](docs/assets/readme-doc-navigation.zh.svg)

### 我想先把环境跑起来

先看：

- `docs/local-deployment-contract.yaml`
- `docs/local-dev.md`
- `docs/env-matrix.md`

### 我想了解完整部署细节

再看：

- `docs/deployment-guide.md`

### 我想继续开发或二开

重点看：

- `docs/development-paradigm.md`
- `docs/development-guidelines.md`
- `docs/project-story.md`

### 我想做正式发版

先看：

- `docs/releases/release-policy.md`
- `docs/releases/v0.1.0-agent-workspace-demo-draft.md`
- `docs/releases/v0.1.0-release-runbook.md`
- `docs/releases/v0.1.1-agent-workspace-demo-draft.md`
- `docs/releases/v0.1.1-release-runbook.md`

<a id="ai-deploy"></a>

### 我想让 AI 代理帮我部署

入口文档：

- `docs/ai-deployment-assistant-instruction.md`

如果你只是想触发标准本地部署，这句话就够了：

```text
阅读 `docs/ai-deployment-assistant-instruction.md` 帮我部署环境。
```

如果你已经知道本地要用哪套模型，建议把模型配置也一次性发给代理。这样代理更容易一次把环境配好，而不是启动到一半再回头追问 runtime 模型配置。

更推荐直接发这段（把占位符替换成你自己的真实配置，且只让代理写入本地 `settings.local.yaml`，不要把真实 key 提交回仓库）：

```text
阅读 `docs/ai-deployment-assistant-instruction.md` 帮我部署环境。

默认推理模型使用 `<YOUR_REASONING_MODEL_ID>`。
当前多模态链路需要的模型一并配置为 `<YOUR_MULTIMODAL_MODEL_ID>`。
如果本地缺少 runtime 模型配置，请把下面内容写入 `apps/runtime-service/graph_src_v2/conf/settings.local.yaml`，并继续完成部署、启动与验证；不要把真实 API Key 提交回仓库。

default:
  default_model_id: <YOUR_REASONING_MODEL_ID>
  models:
    <YOUR_MULTIMODAL_MODEL_ID>:
      alias: <OPTIONAL_MULTIMODAL_ALIAS>
      model_provider: openai
      model: <YOUR_MULTIMODAL_MODEL_NAME>
      base_url: <YOUR_PROVIDER_BASE_URL>
      api_key: <YOUR_API_KEY>
    <YOUR_REASONING_MODEL_ID>:
      alias: <OPTIONAL_REASONING_ALIAS>
      model_provider: openai
      model: <YOUR_REASONING_MODEL_NAME>
      base_url: <YOUR_PROVIDER_BASE_URL>
      api_key: <YOUR_API_KEY>
```

## 实操参考

如果你希望参考一套更贴近真实开发过程的本地实操记录，详细见：

- [ai-learning-portfolio 仓库](https://github.com/ljxpython/ai-learning-portfolio)
- [my_work_record 索引](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/README.md)

这组记录不是重复贴源码，而是专门补“具体怎么做、怎么验证、怎么复盘”的落地路径，可作为本仓库进行**智能体功能开发**和**平台相关能力开发**的参考。

建议这样理解这组内容：

- 根仓库 `README` 更偏项目地图、系统分层和文档导航
- `ai-learning-portfolio` 里的本地实操记录更偏真实开发过程、验证路径和复盘方法

如果你想按主线看，建议优先关注这些内容：

- [部署与验证基线](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/20260323_deployment_environment.md)
- [Text-to-SQL 简单能力开发案例](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/20260312_texttosql_rd.md)
- [多智能体复杂业务开发案例](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/20260314_requirement_agent_rd.md)

你可以这样理解这 3 篇记录的作用：

- `20260323_deployment_environment.md`：看本地环境怎么准备、怎么启动、怎么验证链路是否打通
- `20260312_texttosql_rd.md`：看一个相对简单的 Text-to-SQL 能力案例是怎么围绕具体场景做设计与实现的
- `20260314_requirement_agent_rd.md`：看多智能体复杂业务场景从需求理解、角色拆分到研发落地是怎么推进的

如果你是第一次接触这个仓库，比较推荐的阅读顺序是：

1. 先看当前仓库的 `README`、`docs/local-deployment-contract.yaml` 和 `docs/local-dev.md`
2. 再看 `ai-learning-portfolio` 中的本地实操记录索引
3. 如果想先从简单案例入手，就看 Text-to-SQL；如果想看复杂业务协作场景，就看多智能体需求研发案例

## 当前状态

当前仓库已经完成：

- 默认五服务启动集已迁入 `apps/*`
- `apps/platform-web-vue` 已作为新的迁移前端宿主持续推进
- `runtime-service` 可启动
- `interaction-data-service` 可启动
- `platform-api` 可启动
- `platform-api -> runtime-service` 联调已通过
- `runtime-service -> interaction-data-service` 已接入本地联调脚本
- `platform-web-vue` / `runtime-web` 已形成当前主线前端入口

当前仍保持的约定：

- 每个应用独立维护自己的环境与依赖
- 根目录不统一维护 `.env`
- 根目录暂不统一 Python / Node 依赖

## 项目方向

这个仓库的长期方向，是把它打磨成一套可复用、可扩展、可继续二开的 AI Agent 平台基础框架。  
当前会优先吸收测试工程相关场景能力，例如：

- AI 智能评审
- AI 驱动的 UI 自动化
- 自动化脚本生成与测试辅助
- AI 性能测试
- Text-to-SQL

更完整的项目背景、演进过程和设计取舍，见：

- `docs/project-story.md`

## 支持与交流

如果这个项目对你有帮助，欢迎 star。  
如果你希望交流测试平台、AI 协同开发、LangGraph / MCP 相关实践，也欢迎联系。

个人微信号：

<img src="docs/assets/image-20250531212549739.png" alt="个人微信号" width="300"/>

## 历史代码

旧版 `AITestLab` 代码已不再保留在当前工作分支。

如需回看旧版代码，请访问：

- [AITestLab-archive](https://github.com/ljxpython/AITestLab-archive)

<a id="acknowledgements"></a>

## 致谢与参考

本项目在持续演进过程中，参考并受益于一些优秀的开源项目与技术生态，尤其包括：

- [Wei-Shaw/sub2api](https://github.com/Wei-Shaw/sub2api/tree/main)：在前端视觉组织、后台工作台布局、列表页与系统区交互节奏上给了当前迁移工作不少启发
- [FastAPI](https://fastapi.tiangolo.com/)：平台后端与服务接口层的重要基础
- [LangGraph](https://docs.langchain.com/langgraph)：Agent Runtime、状态编排与执行流建模的重要基础
- [FastMCP](https://gofastmcp.com/)：MCP 工具接入与服务化能力的重要参考生态

这里的“参考”不是简单照搬源码，而是基于这些开源项目和技术生态，结合当前仓库的业务目标、工程边界和平台化需求，做了再组织、再封装和再落地。

## 开源与引用说明

本项目以公开源码方式持续维护，欢迎学习、参考和基于当前仓库继续二次开发。

如果你在公开项目、技术文章、演示材料、培训内容或二次发布中使用了本项目的代码、设计、文档或衍生实现，请明确注明来源仓库与作者信息。

建议至少保留类似说明：

```text
This project is based on or references AITestLab:
https://github.com/ljxpython/AITestLab
```
