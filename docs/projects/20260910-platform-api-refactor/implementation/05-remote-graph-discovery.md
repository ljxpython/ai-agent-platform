# 远端 Graph 与 schema

> 接口方案已被 [06 官方 Assistant 发现](06-official-assistant-discovery.md) 修订：自定义 /graphs 已撤销，下文仅保留当时实施与测试证据。当前契约以 06 为准。

2026-09-10；对应 C1/C2/C3，整体 partial。

## 实现

- GraphHarbor `libs/langhost/src/langhost/core_api.py`、`server.py`：新增 GET /graphs，只读 GraphRegistry 的部署 ID。无需 Assistant 数据库记录，使用现有 PrincipalMiddleware 鉴权。
- 沿用 GET /assistants/{assistant_id}/schemas；graph_id 直接定位 registry，UUID 继续查记录并验证 tenant/project。input/output/context 使用 LangGraph 公共 JSON Schema 方法；state 使用共享图的浅副本，将输出通道设为状态流通道后生成 schema，避免把输入 schema 错当状态。
- Platform `runtime_catalog/application/service.py`：Graph 刷新改用远端 registry，删除本机配置扫描。合法空数组标记旧 Graph 删除；非法响应或网络异常在写数据库之前失败，保留快照。GET 列表不隐式刷新。
- `adapters/langgraph/graphs_sdk_adapter.py`：网关 Graph 搜索/计数使用相同发现端点，删除通过 Assistant 分页猜测 Graph 的实现。
- `adapters/langgraph/parameter_schema.py`：删除约 300 行 AST 扫描和 fallback；在项目授权后取得远端 schema，仅展示现有公开模型覆盖字段。保留前端 sections 响应形状，不开放私有 configurable、身份、Tool 权限或内部模型引用。
- Agent 服务、HTTP 装配和暂存 Operations 装配接入异步 schema provider；schema 查询要求 project scope。删除 langgraph_graph_source_root 及两份 Compose 对应环境变量。

## 契约与限制

GET /graphs 返回 `{"graphs": [{"graph_id": "agent"}]}`；它是部署端只读扩展，官方 schema 路径保持不变。不修改 Assistant 搜索/计数含义，不执行自动注册或数据库 migration。

GraphHarbor 改动位于相邻源码仓库，尚未发布新包，也未替换 Runtime 当前锁定的 post21。平台没有回退到旧 Assistant 搜索或本机源码；旧部署不支持端点时会明确失败。上线前必须交付配套 GraphHarbor 版本并进行真实 Runtime factory/鉴权联调。

新增与调整测试：GraphHarbor `test_graph_discovery.py`；Platform `test_runtime_catalog_delegation.py`、`test_graph_parameter_schema_provider.py`。测试使用真实 StateGraph 区分 input/output/state，并用节点异常断言保证 schema 查询不执行节点；暂未声称所有业务 factory 不创建外部资源。

另外在 GraphHarbor 现有 Run 创建代码发现未定义变量 policy，属于已有工作区问题，待网关执行链任务修复；因此不将 GraphHarbor 全模块 lint 或真实 Run 执行标为通过。

## 验证

- GraphHarbor Graph 发现和现有 Thread 状态投影：4 项通过（10.94 秒）。覆盖匿名拒绝、UUID 项目隔离、零记录发现与三类 schema。
- Platform schema provider/Graph 搜索：3 项通过（0.226 秒）；目录/schema/既有网关首轮关联测试 35 项通过（4.115 秒）。后续新增授权拒绝断言另行复验。
- GraphHarbor server 与新增测试 Ruff 通过；core_api 存在上述既有 policy 未定义以及原有未使用导入，不虚报全量 lint 通过。
- 本地后端全量：156 项，153 通过、3 跳过，227.150 秒；没有失败或错误。全量启动后新增的两项断言在对应文件复验：schema/搜索 3 项通过、目录/授权 12 项通过（5.607 秒）。未重复执行无新增产品改动的全量测试。
- Python compileall、工程文档链接/JSON 与两仓库 git diff --check 通过。未进行容器、生产数据库或浏览器验收。

结构化记录见 [remote-discovery-verification.json](../evidence/remote-discovery-verification.json)。
