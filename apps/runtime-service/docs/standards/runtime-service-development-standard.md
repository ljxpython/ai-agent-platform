# Runtime Service 开发范式与规则

## 以 Showcase Demo 为模板

- `agent.py` 是唯一组合根：校验身份和 Context，获取模型，显式装配 Middleware、工具和子 Agent。
- `prompts.py` 只放提示词和纯渲染函数；不读环境变量、不发网络请求。
- `tools.py` 只放本服务真实业务动作；不返回模拟成功。
- `backend.py` 只处理工作区、资源边界和执行隔离；优先复用官方 Backend。
- `subagents.py` 用声明式角色和最小权限；禁止无边界通用子 Agent。
- `skills/` 是按需读取的资源，不授予权限。
- Graph 入口通过 `langgraph*.json -> graphs -> services/<name>/agent.py` 注册。

## 必须遵守

1. 先查本导航、相关 knowledge、官方 MCP 文档和现有调用者，再改代码。
2. 优先使用 LangChain/LangGraph/Deep Agents 官方能力，不自建 Agent 循环、Tool Registry、Builder 或审批 State。
3. 信任边界必须校验：身份、Context 哈希、tenant/project/thread scope、工具 allowlist 和审批动作。
4. 文件和命令执行必须限制在当前线程工作区；禁止回退到宿主机 shell，禁止把凭据或绝对路径放进 Prompt/Context。
5. 新增能力必须有单元或组合测试；跨边界改动补集成测试和至少一条 E2E 链路。
6. 变更保持最小：不为未来需求预留抽象，不复制旧 Runtime，不新增兼容 Adapter。
7. 影响功能现状时同步 `docs/FEATURES.md`；治理或跨服务改动更新 `docs/projects/` 记录。

## 新功能最短流程

阅读资料 → 复制 Showcase 的边界模式 → 在所属 Service 显式装配 → 编写最小测试 → 本地运行 → 更新文档和变更记录 → 提交评审。
