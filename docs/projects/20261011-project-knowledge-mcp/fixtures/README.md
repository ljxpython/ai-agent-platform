# 前端知识结果 fixture

所有JSON为官方Adapter/平台实际产物，未手写ToolMessage。`tool_message.content`和`artifact.structured_content`同值（error没有artifact）。同目录不会包含MCP URL/token、binding、宿主路径或原始raw_data。

| 文件 | 来源 | 用途 |
| --- | --- | --- |
| live-alpha-showcase_demo.json / live-alpha-dearflow_agent.json | 本环境真实API→Worker→DeepSeek→当前K/alpha_v1 | 两同名规范、片段、最终回答、Thread/Run关联 |
| live-beta-showcase_demo.json / live-beta-dearflow_agent.json | 真实beta_v1、独立项目凭据 | 项目隔离及两图同契约 |
| ok.json | 受控HTTP provider→官方Adapter→安全投影 | 两同名文档来源，含编号，无路径/metadata |
| no_hit.json | 同上，受控空命中 | success与空sources |
| error.json / malformed.json | 同上，isError/损坏结构 | 固定safe error，不显示原始provider数据 |
| oversized.json | 同上，额外经过ResultFilesystemMiddleware F04预算800 | JSON字符串、同值artifact、完整字段裁剪/truncated |
| disconnected.json | 官方Adapter，受控provider停止后调用 | 既有tool.upstream_unavailable字符串safe error |

受控fixture不是实际资料召回、实际业务无答案率或生产宕机结果。真实无答案测试中LightRAG仍召回近似片段，Agent明确“资料未提供”；不能把status=ok当问题必有答案。

协议fixture重建：Runtime目录设置 `KNOWLEDGE_FRONTEND_FIXTURES` 指向本目录，运行 `tests/tools/test_knowledge_http_contract.py`。该测试校验无SECRET/PRIVATE/raw metadata，content/artifact及F04合法JSON。live样本由 `tests/e2e/test_knowledge_platform.py` 验证后从私有evidence中只提取ToolMessage/答案/关联ID，绝不导出私有env/test-actors。

浏览器用的Thread/Run以live文件为准；本地证据重跑会生成新的关联。所有语料均为本任务合成Markdown，包括用于展示边界的恶意指令，不是管理员授权。
