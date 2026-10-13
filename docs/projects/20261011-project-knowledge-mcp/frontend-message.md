# 可直接转发给前端同事

知识检索的后端、Runtime和rag-anything-use文本模式已经接好并在本地部署。平台改动在6394的ai-agent-platform worktree，前端代码本轮没动，需要你接续联验。

请先看同目录frontend-handoff.md和fixtures/README.md，复用Chat/Dear现有ToolResult.vue、transcript和官方SDK状态。工具叫mcp_query_project_knowledge，结果沿现有SSE/历史传回，没有新的知识API，也不需要知识管理页、上传/选库或MCP配置UI。

已给4份真实两项目×两主图ToolMessage和6份官方Adapter协议fixture。重点看同名来源不合并、preview/truncated、无命中与error区分、刷新/fork快照、Stop/项目切换/撤权，以及深浅主题和1440/768/390。先证明现有组件是否直接满足；有缺口再做共享组件的小适配。

本地Web：http://127.0.0.1:25457；开发账号沿既有规范admin/admin123456。选“知识MCP验收-alpha-f47e5d91”或“知识MCP验收-beta-90eb799f”，分别验Showcase和Dear，新开会话问登录规范。alpha应答/azalea/login、17分钟、错5次锁23分钟；beta应答/ginkgo/auth、41分钟、错3次锁9分钟。配置/知识凭据都在服务端，不放前端。

后端已验真实模型链、两项目隔离、用户/服务账号撤权、Stop无迟到结果、Worker与知识服务重启、fork和禁用回退。请交回必要diff或“无需改代码”证据、测试/F01–F10结果、Thread/Run及无敏感截图。

当前PDF/Office解析和业务语料质量仍缺兼容环境/代表性资料，本轮不要展示格式全支持或准确率承诺。详细Block在README/tasks中。
