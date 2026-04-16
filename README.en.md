<h1 align="center">Enterprise AI Agent Platform</h1>

<p align="center"><strong>An AI agent platform foundation for enterprise delivery and secondary development</strong></p>

<p align="center">English | <a href="README.md">中文</a></p>

<p align="center">
  <img src="https://img.shields.io/badge/Vue-3%20Workspace-42B883" alt="Vue 3 Workspace" />
  <img src="https://img.shields.io/badge/Testcase-Agent%20Live-2563EB" alt="Testcase Agent Live" />
  <img src="https://img.shields.io/badge/Skills-Private%20Skill%20Stack-0F766E" alt="Skills" />
  <img src="https://img.shields.io/badge/MCP-Knowledge%20Ready-7C3AED" alt="MCP Knowledge Ready" />
  <img src="https://img.shields.io/badge/Harness-AI%20Continuous%20Coding-F59E0B" alt="Harness" />
  <img src="https://img.shields.io/badge/LangGraph-Runtime%20Core-111827" alt="LangGraph Runtime Core" />
  <img src="https://img.shields.io/badge/README-EN%2FZH-F59E0B" alt="README EN/ZH" />
</p>

<p align="center"><a href="#system-overview">System Overview</a> · <a href="#frontend-entry">Frontend Entry</a> · <a href="#quick-start">Quick Start</a> · <a href="docs/deployment-guide.md">Deployment Guide</a> · <a href="docs/CHANGELOG.md">Changelog</a> · <a href="docs/commit-and-changelog-guidelines.md">Commit Guidelines</a> · <a href="#acknowledgements">Acknowledgements</a> · <a href="#ai-deploy">AI Deployment</a></p>

## Testcase Agent Demo

<p align="center">
  <a href="https://youtu.be/SVplU-uIci0">
    <img src="docs/assets/testcase-agent-demo-preview.jpg" alt="Testcase Agent Demo" width="100%" />
  </a>
</p>

<p align="center">
  <strong><a href="https://youtu.be/SVplU-uIci0">▶ Watch the current platform Testcase Agent demo</a></strong>
</p>

<p align="center"><sub>The GitHub README uses an image preview here. Click it to open the YouTube demo.</sub></p>

An enterprise AI agent platform architecture built on `LangGraph / LangChain`, intended as a reusable foundation for further development.  
It separates the **platform governance layer** from the **Agent Runtime execution layer**, so the repo can support platform-side authentication, project management, audit, and catalog management, while also supporting runtime graph orchestration, model assembly, Tools / MCP / Skills integration, and rapid agent debugging.

The repository currently provides a default four-service local bring-up path, plus an optional runtime debug entry. It is suitable for:

- Teams that want to build on mainstream agent infrastructure instead of inventing a closed framework
- Projects that need both platform capabilities and agent execution capabilities
- Developers who want to validate LangGraph Runtime behavior and frontend interaction quickly
- Teams that want to bring AI-assisted collaboration into the real engineering workflow

> If you want to understand why the project is designed this way and how development should continue, start with [docs/development-paradigm.md](docs/development-paradigm.md). Most supporting docs in this repo are currently Chinese-first.

<a id="frontend-entry"></a>

## Current Frontend Entry

`apps/platform-web-vue` is the official platform frontend host and the default place for current platform frontend development.

Use the frontend entries in this repo like this:

- `apps/platform-web-vue`: official platform workspace frontend
- `apps/runtime-web`: runtime-facing debug frontend

If you just want the current official local demo path, start the root scripts and open `apps/platform-web-vue`.

## AI Continuous-Coding Harness

This repository is not only a codebase. It already acts as an engineering harness for continuous AI-assisted development.

That harness is made of several parts working together:

- `Boundaries`: platform governance, runtime execution, debug frontend, and result-domain service are separated instead of mixed together
- `Contracts`: local deployment contract, env conventions, startup order, API naming, and demo account rules are fixed
- `Patterns`: `runtime-service`, `platform-web-vue`, control-plane standards, and reusable examples already provide working implementation patterns
- `Delivery loop`: helper scripts, health checks, smoke tests, acceptance docs, changelog, and release runbooks form a repeatable delivery path

In short, the repo is meant to let AI agents keep building inside a controlled engineering environment, not just generate random code in a vacuum.

The current canonical docs for that harness are:

- `docs/local-deployment-contract.yaml`
- `docs/development-paradigm.md`
- `docs/local-dev.md`
- `docs/env-matrix.md`

## What Problem This Project Solves

Many agent projects can run a demo, but once they enter a real engineering context, things become messy fast: platform governance, runtime execution, debug entrypoints, and environment configuration all get coupled together.

This repo has a clear goal:

- Build an enterprise AI platform architecture on top of the mainstream `LangGraph / LangChain` ecosystem
- Decouple the platform layer from the runtime layer so ownership, evolution, and delivery stay manageable
- Provide a reusable runtime execution skeleton instead of a one-off demo
- Leave room for later business customization and testing-related scenarios

## Frontend Showcase

If you want to see what the current platform frontend already looks like and how the frontend workspace is organized, start with this write-up:

- [Platform frontend showcase and introduction](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/20260325_platform_frontend_intro.md)

That article is more frontend-oriented and is useful for quickly understanding the current platform workspace structure and UI direction.

![Platform Frontend Showcase](docs/assets/image-20260325161139758.png)

<a id="system-overview"></a>

## System Overview

The default local bring-up currently includes four formal services:

- `apps/interaction-data-service`: result-domain data service for workflow result persistence and querying
- `apps/platform-api-v2`: official platform backend / control-plane API
- `apps/platform-web-vue`: official platform frontend / admin workspace entry
- `apps/runtime-service`: LangGraph execution layer / Agent Runtime

Optional debug entry:

- `apps/runtime-web`: debug frontend that talks directly to the runtime

### Two Main Paths

- Platform path: `platform-web-vue -> platform-api-v2 -> runtime-service`
- Debug path: `runtime-web -> runtime-service`
- Result-domain path: `runtime-service -> interaction-data-service`

### What The Frontend Entries Are For

- `platform-web-vue`: official platform product workspace and the default frontend host
- `runtime-web`: agent debugging, interaction validation, and fast runtime iteration

## Architecture Diagram

![System Architecture Diagram](docs/assets/system-architecture.en.svg)

<a id="quick-start"></a>

## Quick Start

### Default Startup Order

1. `runtime-service`
2. `interaction-data-service`
3. `platform-api-v2`
4. `platform-web-vue`
5. `runtime-web` (optional)

### Root Scripts

```bash
scripts/dev-up.sh
scripts/check-health.sh
scripts/dev-down.sh
```

These three scripts are:

- Start: `scripts/dev-up.sh`
- Health check: `scripts/check-health.sh`
- Stop: `scripts/dev-down.sh`

### If You Want To Start `platform-web-vue` Separately

The root scripts already start `apps/platform-web-vue`.

If you want to run it alone during frontend work:

```bash
VITE_DEV_PORT=3002 pnpm --dir "apps/platform-web-vue" dev
```

Then open:

- `platform-web-vue`: `http://127.0.0.1:3002`

### Default Local Ports

- `interaction-data-service`: `8081`
- `runtime-service`: `8123`
- `platform-api-v2`: `2142`
- `platform-web-vue`: `3000`
- `runtime-web`: `3001`

### URLs After Startup

- `platform-web-vue`: `http://127.0.0.1:3000`
- `runtime-web`: `http://127.0.0.1:3001`

### Minimum Health Checks

```bash
curl http://127.0.0.1:8081/_service/health
curl http://127.0.0.1:8123/info
curl http://127.0.0.1:2142/_system/health
curl http://127.0.0.1:2142/api/langgraph/info
```

If `/api/langgraph/info` on `platform-api-v2` returns `200`, and `/_service/health` on `interaction-data-service` also returns `200`, the platform path and result persistence path are basically connected.

![Local Startup Flow](docs/assets/local-dev-startup-flow.en.svg)

## Repo Structure

```text
AITestLab/
├── apps/
│   ├── interaction-data-service/
│   ├── platform-api-v2/
│   ├── platform-web-vue/
│   ├── runtime-service/
│   ├── runtime-web/
│   └── ...
├── docs/
├── scripts/
└── archive/
```

- `apps/`: business apps, including the default local startup set and other maintained application directories
- `docs/`: deployment, development, constraints, and background docs
- `scripts/`: unified start, stop, and health-check scripts
- `archive/`: historical archive notes

<a id="docs-by-goal"></a>

## Read Docs By Goal

![Documentation Navigation Diagram](docs/assets/readme-doc-navigation.en.svg)

### I Want To Bring Up The Environment First

Start with:

- `docs/local-deployment-contract.yaml`
- `docs/local-dev.md`
- `docs/env-matrix.md`

### I Want Full Deployment Details

Then read:

- `docs/deployment-guide.md`

### I Want To Continue Development Or Customize The Project

Focus on:

- `docs/development-paradigm.md`
- `docs/development-guidelines.md`
- `docs/project-story.md`

<a id="ai-deploy"></a>

### I Want An AI Agent To Help Me Deploy

Entry document:

- `docs/ai-deployment-assistant-instruction.md`

If you only want to trigger the standard local deployment flow, this sentence is enough:

```text
Read `docs/ai-deployment-assistant-instruction.md` and help me deploy the environment.
```

If you already know which models should be used locally, it is better to provide the model configuration to the agent in the same message. That makes it much easier for the agent to finish the bring-up in one pass instead of stopping midway to ask for runtime model settings.

This fuller prompt is the recommended version. Replace the placeholders with your real values, and only let the agent write them into local `settings.local.yaml`. Do not commit real secrets back into the repo.

```text
Read `docs/ai-deployment-assistant-instruction.md` and help me deploy the environment.

Use `<YOUR_REASONING_MODEL_ID>` as the default reasoning model.
Also configure `<YOUR_MULTIMODAL_MODEL_ID>` for the current multimodal pipeline.
If runtime model config is missing locally, write the following into `apps/runtime-service/runtime_service/conf/settings.local.yaml`, then continue deployment, startup, and verification. Do not commit the real API key back to the repo.

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

## Practical References

If you want a set of notes closer to real development work, see:

- [ai-learning-portfolio repository](https://github.com/ljxpython/ai-learning-portfolio)
- [my_work_record index](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/README.md)

These notes do not duplicate the source code. They focus on the practical path: how things were done, how they were verified, and how they were reviewed afterward. They are useful as a reference for both **agent capability development** and **platform capability development** in this repo.

A useful way to think about them:

- The root `README` of this repo is more of a project map, system layering guide, and document index
- The `ai-learning-portfolio` notes are more about real implementation flow, validation steps, and retrospective thinking

If you want the mainline reading path, start with:

- [Deployment and validation baseline](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/20260323_deployment_environment.md)
- [A simple Text-to-SQL capability case](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/20260312_texttosql_rd.md)
- [A complex multi-agent business case](https://github.com/ljxpython/ai-learning-portfolio/blob/main/my_work_record/20260314_requirement_agent_rd.md)

You can read those three notes like this:

- `20260323_deployment_environment.md`: how to prepare the local environment, start services, and verify that paths are connected
- `20260312_texttosql_rd.md`: how a relatively simple Text-to-SQL capability is designed and implemented around a concrete scenario
- `20260314_requirement_agent_rd.md`: how a more complex multi-agent business scenario moves from requirement understanding and role split to actual delivery

If this is your first time looking at the repo, the recommended reading order is:

1. Read this `README`, `docs/local-deployment-contract.yaml`, and `docs/local-dev.md`
2. Then check the local practice index in `ai-learning-portfolio`
3. If you want a simpler starting point, begin with Text-to-SQL. If you want a more complex collaboration case, start with the multi-agent requirement case

## Current Status

This repo has already completed:

- The default four-service startup set has been stabilized under `apps/*`
- `apps/platform-web-vue` is the official platform frontend host
- `apps/platform-api-v2` is the official platform control plane
- `runtime-service` can start
- `interaction-data-service` can start
- `platform-api-v2` can start
- `platform-api-v2 -> runtime-service` integration has passed
- `runtime-service -> interaction-data-service` has been wired into the local bring-up scripts
- `platform-web-vue` is the official platform frontend host, while `runtime-web` remains the optional runtime debug shell

Current conventions that are still kept:

- Each app maintains its own environment and dependencies
- There is no unified root `.env`
- Python and Node dependencies are not unified at the repo root for now

## Project Direction

The long-term direction of this repo is to evolve into a reusable, extensible, secondary-development-friendly AI agent platform foundation.  
Near-term capability growth is biased toward test-engineering-related scenarios such as:

- AI-assisted review
- AI-driven UI automation
- Automated script generation and testing assistance
- AI performance testing
- Text-to-SQL

For fuller project background, evolution history, and design tradeoffs, see:

- `docs/project-story.md`

## Support And Contact

If this repo helps you, a star is welcome.  
If you want to discuss testing platforms, AI-assisted development, or LangGraph / MCP practice, feel free to reach out.

Personal WeChat:

<img src="docs/assets/image-20250531212549739.png" alt="Personal WeChat QR" width="300"/>

## Historical Code

The old `AITestLab` code is no longer kept on the current working branch.

If you need the historical code, see:

- [AITestLab-archive](https://github.com/ljxpython/AITestLab-archive)

<a id="acknowledgements"></a>

## Acknowledgements

This project has benefited from several strong open-source projects and ecosystems, especially:

- [Wei-Shaw/sub2api](https://github.com/Wei-Shaw/sub2api/tree/main): strong inspiration for frontend layout rhythm, dashboard organization, and workspace interaction patterns
- [FastAPI](https://fastapi.tiangolo.com/): key foundation for the platform backend and service interfaces
- [LangGraph](https://docs.langchain.com/langgraph): key foundation for agent runtime orchestration and stateful execution flows
- [FastMCP](https://gofastmcp.com/): important reference ecosystem for MCP-based tooling and service integration

These references are not copied blindly. They are absorbed, reorganized, and adapted around the goals and engineering boundaries of this repository.

## Open Source Usage Notice

This project is maintained as public source code. Learning from it, referencing it, and building on top of it are all welcome.

If you use this project in public repositories, technical articles, demos, training materials, or redistributed derivatives, please clearly credit the original repository and author.
