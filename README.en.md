<h1 align="center">Enterprise AI Agent Platform</h1>

<p align="center"><strong>An Enterprise-Grade AI Agent Platform Foundation for Secondary Development · Built on the LangGraph Ecosystem</strong></p>

<p align="center">English | <a href="README.md">中文</a></p>

<p align="center">
  <img src="https://img.shields.io/badge/LangGraph-Runtime%20Core-111827" alt="LangGraph Runtime Core" />
  <img src="https://img.shields.io/badge/GraphHarbor-State%20Persistence-F59E0B" alt="GraphHarbor" />
  <img src="https://img.shields.io/badge/FastAPI-Platform%20API-009688" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Vue-3%20Console-42B883" alt="Vue 3 Console" />
  <img src="https://img.shields.io/badge/MCP-Tool%20Extension-7C3AED" alt="MCP Tool Extension" />
  <img src="https://img.shields.io/badge/Skills-Agent%20Skills-0F766E" alt="Skills" />
  <img src="https://img.shields.io/badge/Memory-Memory%20Loop-2563EB" alt="Memory" />
  <img src="https://img.shields.io/badge/HITL-Human--in--the--Loop-DC2626" alt="HITL" />
  <a href="https://github.com/ljxpython/ai-agent-platform/releases/latest"><img src="https://img.shields.io/github/v/release/ljxpython/ai-agent-platform" alt="Latest Release" /></a>
</p>

<p align="center">
  <a href="#system-overview">System Overview</a> ·
  <a href="#architecture-diagrams">Architecture Diagrams</a> ·
  <a href="#agent-ecosystem">Built-in Agents</a> ·
  <a href="#secondary-development">Secondary Development</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="docs/guides/deployment-guide.md">Deployment Guide</a> ·
  <a href="docs/CHANGELOG.md">Changelog</a> ·
  <a href="#acknowledgements">Acknowledgements</a>
</p>

---

## What Problem Does This Project Solve?

Many agent projects stop at the "toy demo" stage: platform governance, runtime execution, persistent storage, and frontend interactions are tightly coupled into a single monolith. When moving to production, teams immediately face authorization gaps, state loss, model lock-in, and fragile extensions.

This project delivers an **enterprise-ready engineering foundation built for secondary development**:

- **Decoupled Platform Governance & Agent Runtime**: The platform layer manages authentication, multi-tenant/project isolation, audit trails, and model catalog routing; the runtime layer focuses purely on graph orchestration, tool execution, and state persistence.
- **Mainstream Open-Source Ecosystem**: Built natively on `LangGraph / LangChain`, deeply incorporating design principles from `open-swe`, `deepagents`, and `deer-flow`.
- **Standardized Secondary Development Scaffold**: Explicit extension points (custom Agent graphs, custom Tools, MCP services, Skills) allow teams to clone this repo as a production scaffold and assemble custom business agents in minutes.

<a id="system-overview"></a>

## System Overview

| Service | Directory | Responsibilities | Core Stack |
|---|---|---|---|
| **Platform API** | `apps/platform-api` | **Control Plane**: Auth, project isolation, audit logs, model catalog, managed contract gateway | FastAPI + SQLAlchemy + PostgreSQL |
| **Platform Web** | `apps/platform-web` | **Console UI**: Workspace layout, agent chat stream, access controls, multi-turn rendering | Vue 3 + Vite + Tailwind CSS + Pinia |
| **Runtime Service** | `apps/runtime-service` | **Agent Runtime**: LangGraph graph registry, tool & MCP binding, session dispatch, SSE streaming | Python 3.11+ + LangGraph + GraphHarbor + Redis |

<a id="architecture-diagrams"></a>

## Architecture & Flow Diagrams

### 1. System Architecture Overview

> 🔗 **Interactive View:** [👉 Open Fullscreen Architecture Diagram (HTML)](docs/diagrams/arch-system-overview.html)

![System Architecture Overview](docs/assets/arch-system-overview.png)

---

### 2. Agent Execution Sequence

> 🔗 **Interactive View:** [👉 Open Fullscreen Sequence Diagram (HTML)](docs/diagrams/seq-agent-run.html)

![Agent Execution Sequence Diagram](docs/assets/seq-agent-run.png)

---

### 3. Secondary Development Extension Points

> 🔗 **Interactive View:** [👉 Open Fullscreen Extension Points Diagram (HTML)](docs/diagrams/arch-extension-points.html)

![Secondary Development Extension Points](docs/assets/arch-extension-points.png)

---

<a id="agent-ecosystem"></a>

## Built-in Agent Ecosystem

### 1. Educational Starter: `showcase_demo`
- **Location**: `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/`
- **Capabilities**: Tool calling, HITL approval interrupts, subagents, sandbox workspace, and dynamic MCP.

### 2. Production-Grade Reference: `DeerFlow Agent`
- **Design Inspiration**: Incorporates paradigms from `bytedance/deer-flow`, `langchain-ai/deepagents`, and `langchain-ai/open-swe`.
- **Enterprise Features**:
  - 🧠 **Dynamic Multi-Mode Flow**: Research, Coding, Planning, and Subagent delegation.
  - 💾 **Memory Engine**: Short-term session state plus cross-session long-term memory pipeline.
  - 🛡️ **Secure Sandbox Workspace**: Dual local/Docker sandbox, live file tree, code preview, and .zip artifact download.
  - 💻 **Interactive PTY Terminal**: Real xterm terminal sessions, command auditing, and permission guards.
  - 🧰 **Production Skill Matrix**: Comprehensive tool suite for code analysis, search, and operations.

---

<a id="secondary-development"></a>

## Secondary Development Guide

| Extension Need | Target Path | Description |
|---|---|---|
| **Add Custom Agent Graph** | `apps/runtime-service/src/runtime_service/graphs/` | Define `StateGraph` nodes and edges using LangGraph |
| **Add Custom Tools** | `apps/runtime-service/src/runtime_service/tools/` | Write pure Python functions with `@tool` |
| **Connect MCP Servers** | Runtime Configuration | Standard MCP client support to mount external FastMCP or official tools |
| **Extend Control Plane APIs** | `apps/platform-api/src/platform_api/` | Follow `apps/platform-api/docs/handbook/` |
| **Extend Console UI** | `apps/platform-web/src/modules/` | Follow `control-plane-page-standard.md` |

---

<a id="quick-start"></a>

## Quick Start

```bash
# 1. Activate runtime virtual environment
source "apps/runtime-service/.venv/bin/activate"

# 2. Run system doctor
bash "scripts/local-stack.sh" doctor

# 3. Start full stack
bash "scripts/local-stack.sh" start

# 4. Status check
bash "scripts/local-stack.sh" status

# 5. Stop
bash "scripts/local-stack.sh" stop
```

---

<a id="acknowledgements"></a>

## Acknowledgements & Technical Core

### Core Inspirations & Architectural Pillars
- [open-swe](https://github.com/langchain-ai/open-swe): Core inspiration for sandbox workspaces, PTY terminal sessions, and production developer agent UX.
- [deepagents](https://github.com/langchain-ai/deepagents): Key reference for complex task decomposition, subagent orchestration, and execution trace persistence.
- [deer-flow](https://github.com/bytedance/deer-flow): Fundamental architecture reference for end-to-end streaming agent execution, memory loop governance, and engineering delivery.

### Ecosystem Foundation & References
- [LangGraph / LangChain](https://docs.langchain.com/langgraph)
- [FastAPI](https://fastapi.tiangolo.com/)
- [FastMCP](https://gofastmcp.com/)
- [Wei-Shaw/sub2api](https://github.com/Wei-Shaw/sub2api/tree/main)
- [HKUDS/LightRAG](https://github.com/HKUDS/LightRAG)

---

## License & Attribution

```text
Based on Enterprise AI Agent Platform:
https://github.com/ljxpython/ai-agent-platform
```
