# 企业级 AI Agent 平台架构

基于 `LangGraph / LangChain` 的企业级 AI 平台架构，可在此基础上进行二次开发。  
它把**平台治理层**和**Agent Runtime 执行层**拆开，既支持平台侧的认证、项目管理、审计、catalog 管理，也支持 Agent 侧的图编排、模型装配、Tools / MCP / Skills 接入与快速调试，适合作为企业内部 AI 平台和智能体应用的基础骨架。

当前仓库默认提供一套四服务本地联调方案，适合：

- 想基于主流 Agent 技术栈做二次开发的团队
- 想同时建设平台能力和 Agent 执行能力的项目
- 想快速验证 LangGraph Runtime、Agent 行为和前端交互的开发者
- 希望把 AI 协同开发真正纳入工程流程的团队

> 想先理解当前项目为什么这么设计、后续应该按什么范式继续开发，可先看 [当前项目开发范式说明](docs/development-paradigm.md)。

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

这篇内容更偏平台前端视角，适合快速了解 `platform-web` 当前的页面效果、工作台结构和一些实际展示结果。

![平台前端效果展示](docs/assets/image-20260325161139758.png)

## 系统总览

当前默认本地联调由五个应用组成：

- `apps/interaction-data-service`：结果域数据服务 / 工作流结果落库与查询
- `apps/platform-api`：平台后端 / 控制面 API
- `apps/platform-web`：平台主前端 / 管理台入口
- `apps/runtime-service`：LangGraph 执行层 / Agent Runtime
- `apps/runtime-web`：直连 Runtime 的调试前端

### 两条主链路

- 平台链路：`platform-web -> platform-api -> runtime-service`
- 调试链路：`runtime-web -> runtime-service`

### 两个前端分别干什么

- `platform-web`：适合做平台产品能力、管理台、平台侧聊天入口
- `runtime-web`：适合做 Agent 调试、交互验证、Runtime 快速迭代

## 架构图

```mermaid
flowchart LR
    User[User]

    subgraph Platform[Platform Layer]
        PW[platform-web<br/>Next.js]
        PA[platform-api<br/>FastAPI API]
    end

    subgraph Runtime[Runtime Layer]
        RW[runtime-web<br/>Next.js Debug UI]
        RS[runtime-service<br/>LangGraph Runtime]
    end

    IDS[interaction-data-service<br/>FastAPI Result Domain Service]
    DB[(Shared PostgreSQL)]

    User --> PW
    User --> RW

    PW --> PA
    PA --> RS
    PA --> DB
    PA --> IDS

    RW --> RS
    RS --> DB
    RS --> IDS
    IDS --> DB
```

## 快速开始

### 默认启动顺序

1. `runtime-service`
2. `interaction-data-service`
3. `platform-api`
4. `platform-web`
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

### 默认本地端口

- `interaction-data-service`：`8090`
- `runtime-service`：`8123`
- `platform-api`：`2024`
- `platform-web`：`3000`
- `runtime-web`：`3001`

### 成功启动后访问地址

- `platform-web`：`http://127.0.0.1:3000`
- `runtime-web`：`http://127.0.0.1:3001`

### 最小健康检查

```bash
curl http://127.0.0.1:8090/_service/health
curl http://127.0.0.1:8123/info
curl http://127.0.0.1:2024/_proxy/health
curl http://127.0.0.1:2024/api/langgraph/info
```

如果 `platform-api` 的 `/api/langgraph/info` 返回 `200`，且 `interaction-data-service` 的 `/_service/health` 返回 `200`，说明平台链路和结果落库链路都已基本打通。

## 仓库结构

```text
AITestLab/
├── apps/
│   ├── platform-api/
│   ├── platform-web/
│   ├── runtime-service/
│   ├── runtime-web/
│   └── interaction-data-service/
├── docs/
├── scripts/
└── archive/
```

- `apps/`：业务应用与默认四服务启动集
- `docs/`：部署、开发、约束和背景文档
- `scripts/`：统一启动、停止、健康检查脚本
- `archive/`：历史归档说明

## 按目标阅读文档

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

### 我想让 AI 代理帮我部署

入口文档：

- `docs/ai-deployment-assistant-instruction.md`

你甚至可以直接把这句话发给代理：

```text
阅读 `docs/ai-deployment-assistant-instruction.md` 帮我部署环境。
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
- `runtime-service` 可启动
- `interaction-data-service` 可启动
- `platform-api` 可启动
- `platform-api -> runtime-service` 联调已通过
- `runtime-service -> interaction-data-service` 已接入本地联调脚本
- `platform-web` / `runtime-web` 已去除 Google Fonts 构建时外网依赖

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
