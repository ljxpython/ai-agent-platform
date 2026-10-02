# DearFlow Agent 接入 Jina Reader 网页深度提取与双通道容灾支持

## 项目概述
- **时间：** 2026-10-02 至 2026-10-02
- **目标：** 为 DearFlow Agent 的 `fetch_page` 工具引入 Jina Reader API（`r.jina.ai`），形成“Tavily 负责语义搜索（search_web）+ Jina 负责 Markdown 正文阅读（fetch_page）”的黄金组合；同时保留对 Tavily Extract 的自动降级（Fallback）容灾与 SHA256 证据落盘能力。
- **负责人：** @laowang
- **模板类型：** 标准模板
- **状态：** 已完成 (done)

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** `runtime-service`
- **改动级别：** 服务内工具增强与能力升级
- **预计工作量：** 0.3 人天

## 关键决策
1. **职责分离组合拳：** `search_web` 继续保持 Tavily 高权重语义搜索与结果重排序；`fetch_page` 默认升级为 Jina Reader 高保真无头渲染与 Markdown 正文清洗，大幅削减 Tavily 额度消耗并提升复杂 SPA 页面阅读质量。
2. **平滑降级（Graceful Fallback）双通道：** `fetch_page` 执行时优先调用 Jina Reader；若遇到 Jina 超时、5xx 错误或缺少 Key，自动无缝降级走 Tavily Extract 兜底，确保调研链路绝不因第三方单点波动而中断。
3. **证据链与 SSRF 防护 100% 继承：** 无论是 Jina 还是 Tavily 获取的内容，统一经过现有的 `public_url` 拦截网检验，并统一由 `_evidence` 函数计算 SHA256 哈希原子落盘到 `/workspace/sources/{hash}.txt`，挂载 `ToolMessage.artifact`。
4. **多命名 Key 兼容：** 代码支持 `JINA_API_KEY` 与 `JINA_KEY` 自动识别兼容，并从 `~/.my_best/.env` 导入配置。
