# ai-agent-platform 文档导航

> **AI 读取规则：** 新会话先读 `CONTEXT.md`；改动涉及某服务，再读该服务规范入口。本文件供人类导航用。

---

## 你在找什么？

### 🚀 第一次接触这个项目

→ **[architecture/README.md](architecture/README.md)** 了解系统全貌（架构、技术栈、三个服务）

### 🛠 搭本地环境 / 部署上线

→ **[guides/local-dev.md](guides/local-dev.md)** 本地开发环境搭建
→ **[guides/deployment-guide.md](guides/deployment-guide.md)** 部署指南
→ **[guides/zero-to-one-container-deploy.md](guides/zero-to-one-container-deploy.md)** 容器化部署完整流程

### 📋 日常开发规范

→ **[guides/development-guidelines.md](guides/development-guidelines.md)** 开发规范
→ **[guides/commit-and-changelog-guidelines.md](guides/commit-and-changelog-guidelines.md)** 提交规范
→ **[guides/database-operations.md](guides/database-operations.md)** 数据库操作

### 🔧 运维 / 上线操作

→ **[runbooks/](runbooks/)** 运维操作手册
→ **[releases/](releases/)** 版本发布记录

### 📖 技术洞察文章

→ **[knowledge/ai-harness-theory.md](knowledge/ai-harness-theory.md)** AI Harness 理论篇
→ **[knowledge/ai-harness-practice.md](knowledge/ai-harness-practice.md)** AI Harness 实战篇

### 🔍 查历史项目 / 决策背景

→ **[projects/](projects/)** 所有项目文档（含各项目内的架构决策分析）
→ **[CHANGELOG.md](CHANGELOG.md)** 版本变更历史

---

## AI 专用入口

| 文件/目录 | 用途 |
|---|---|
| [CONTEXT.md](CONTEXT.md) | 项目当前状态快照，每次新会话必读 |
| [FEATURES.md](FEATURES.md) | 全仓库功能清单 |
| [standards/README.md](standards/README.md) | 跨服务规范健康表（置信度一览） |
| [lessons/](lessons/) | AI 经验库（按需读取） |
| [changes/](changes/) | 仓库级改动留痕记录 |

---

## 目录速查

```
docs/
├── README.md          ← 你在这里
├── CONTEXT.md         ← AI: 会话快照
├── FEATURES.md        ← AI: 功能清单
├── CHANGELOG.md       ← 版本历史
│
├── architecture/      ← 系统教学文档（架构、技术栈、服务详解）
├── guides/            ← 开发者手册（开发规范 + 环境搭建 + 部署）
├── runbooks/          ← 运维操作手册
├── releases/          ← 版本发布
├── knowledge/         ← 技术洞察文章
│
├── projects/          ← 项目文档（含架构决策分析）
├── standards/         ← AI: 跨服务契约
├── lessons/           ← AI: 经验库
├── changes/           ← AI: 改动留痕
│
├── assets/            ← 静态资源
├── diagrams/          ← 架构图
└── archive/           ← 归档文档
```
