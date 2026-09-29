# 系统架构与技术文档

> 这里是理解 ai-agent-platform 的起点。不管你是新加入的开发者、想深入了解某个服务，还是需要评估技术选型，从这里开始。

---

## 文档地图

| 文档 | 内容 | 适合谁看 |
|---|---|---|
| [overview.md](overview.md) | 系统整体架构、服务关系、主链路 | 所有人第一步 |
| [tech-stack.md](tech-stack.md) | 技术栈清单（语言、框架、主要依赖） | 技术选型参考 |
| [platform-web.md](platform-web.md) | 前端服务详解（Vue3/TS、页面架构、设计规范） | 前端开发者 |
| [platform-api.md](platform-api.md) | 后端服务详解（FastAPI、鉴权、API 设计） | 后端开发者 |
| [runtime-service.md](runtime-service.md) | Agent 执行层详解（LangGraph、工具装配、执行流） | Agent 开发者 |

---

## 系统一句话介绍

**ai-agent-platform** 是一个 AI 智能体运行平台，让用户能够在受控环境中部署、管理和执行 AI Agent。

主链路：
```
platform-web（用户界面）
    → platform-api（鉴权/治理/网关）
        → runtime-service（Agent 执行）
```

---

## 这些文档还在建设中

以下文档为待填充状态（骨架已建立）：
- [ ] overview.md
- [ ] tech-stack.md
- [ ] platform-web.md
- [ ] platform-api.md
- [ ] runtime-service.md

如果你在开发过程中补充了某个服务的技术细节，请同步更新这里对应的文档。
