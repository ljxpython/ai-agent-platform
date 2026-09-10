# 03 Agent、目录与模型配置

## 目标

平台只管理产品配置，部署端提供真实可执行能力；平台镜像不需要 Runtime 源码或宿主机路径。

## 方案设计

### 三类数据，三种所有权

| 对象 | 所有者 | Platform 的动作 |
| --- | --- | --- |
| 部署 Graph、输入/输出/状态/Context schema | 部署端 Graph registry | 只读发现，按需要保存可重建快照 |
| 项目 Agent 名称、启停、默认模型等覆盖 | Platform DB | Agent 管理和授权，不修改 Python 图 |
| 模型连接七字段及加密 API Key | Platform DB | 管理员 CRUD，项目选择默认和允许范围，Runtime 受信读取 |

产品使用 Agent；执行键 `agent_key = graph_id`。新 Agent 表可用 UUID 作为项目配置记录主键，但不能再作为第二个 upstream Assistant ID。只定义当前真实需要的配置字段，不承接旧 profile/config/context 数据。

### 远端发现与 schema

停止 `refresh_graphs()` 扫描本机配置、补建上游 Assistant 的行为；GET 列表无隐式写操作。显式 refresh 只更新有效远端结果，网络错误不能把整个目录标记删除；空结果和发现失败必须区分。界面可显示最后同步时间/不可用原因，不用新“同步平台”实现这些简单状态。

优先采用 Agent Server 现有只读接口和官方 schema。这里存在已查明的前置缺口：当前安装的 GraphHarbor post21 `assistants_search` 只查 AssistantRow；`assistants_schemas` 先按 UUID 查 AssistantRow，未直接接受 graph_id；`state_schema` 还取了 `get_input_schema()`。因此不能简单把 AST provider 改成 GET `/assistants/{graph_id}/schemas` 就宣布完成。

先补通部署端的通用只读 Graph/schema 能力，优先符合官方“已部署 Graph 可按 graph_id 使用”的语义；若扩展不可避免，仅提供一个受控、通用的 registry 读取接口。Platform 只消费它。准确接口与响应在契约试验后冻结，不创建第三套 manifest、注册数据库或基于 Platform 路径的兜底。

schema 获取不得启动 Docker、创建工作区或调用模型。Context schema 只用于允许编辑的参数展示；认证字段、内部 model reference 和 Tool 权限字段不因出现在 schema 中就开放给浏览器。

### Agent 管理

- Agent 创建时验证部署能力存在，项目内 graph_id 唯一；禁用后对新执行及恢复立即应用已确认策略。
- 去除 upstream Assistant 同步概念：resync 接口、假 ready 状态、无效果 delete_runtime/delete_threads 参数、对应异步任务及前端按钮一起退役。
- 新建单一 `agents` 配置表，包含项目、graph_id、名称、启用状态、默认模型和必要公开参数，不再设置一对一 agent_profiles 表。
- 删除 `modules/assistants` 旧导入和 `/api/assistants` 产品别名，前端同步改用新 Agent 契约；官方 SDK 字段 assistant_id 保留在适配边界，它不属于旧产品兼容逻辑。
- Agent 名称、Graph 部署存在性、启用状态、默认模型、项目策略只能各有一个维护位置。

### 模型与 Tools

沿用已确认的模型七字段：provider、display_name、base_url、protocol、model、api_key、enabled。保留 Fernet 加密和短期受信读取，不增加模型代理、Secret Store、配置 revision 平台或动态 Provider 插件系统。

模型不是 Runtime 自动导入的主数据。现有 `/models/refresh` 请求旧 `/internal/capabilities/models` 的链路应退役或改为有明确定义的只读能力探测，不能覆盖管理员录入的连接信息。

模型决议统一优先级：单次允许的覆盖 → Agent 默认 → Project 默认；缺少可用配置明确报错。项目模型权限、默认值校验、token claims 和执行参数必须基于同一决议。新平台统一用模型配置记录 ID 引用连接；provider 和 model 是连接字段，不用 provider:model 等形式猜测记录，不维护历史别名映射。

Tools 仍由 Agent 代码与服务端策略控制。Tools catalog/allowlist 的安全用途不能因旧能力端点不存在而整段删除；明确其真实来源，清除仅为演示硬编码的 `_DELEGATION_TOOL_PERMISSIONS = {"read_reference": ...}` 与实际 Agent 能力脱节的问题。避免建设用户动态编辑 Tools 的新产品。

### 可移植部署

`langgraph_upstream_url` 只用于网络连接。当前只有单 upstream，使用固定逻辑键 `default`，不新增多部署路由表；新 Agent/策略/目录都不使用 URL 作为身份，不做旧 URL 映射与回填。换地址指向同一逻辑部署时身份稳定；指向不同部署时仍需重新核对真实 Graph 能力。

新平台删除 `langgraph_graph_source_root`、本地 langgraph.json 查找和响应中的绝对路径。仅包含 platform-api 代码、数据库连接和远端地址的镜像必须能工作。

## 任务拆分

- [ ] C1：核对部署端 Graph/schema 只读契约，覆盖零 Assistant 记录、graph_id 定位、真正 state schema、鉴权。**已实现并局部验证：** GraphHarbor 启动时注册系统默认 Assistant，目录沿用官方 Assistant search/count；官方 schema 路径接受 graph_id，保留 UUID 项目隔离，修正 state schema。真实 Runtime factory 探测与部署依赖交付仍待验收。
- [ ] C2：将 Graph catalog 改为远端只读快照，去除隐式刷新与 Assistant mutation。**代码已实现：** catalog 与网关 Graph 搜索均分页读取系统默认 Assistant；删除本机配置扫描，非法响应不清空快照。真实部署联调尚未完成。
- [ ] C3：用真实远端 schema 替换 AST provider，迁移 Agent 创建页参数展示。**后端已实现：** 项目授权、委托请求、公开字段筛选；删除源码配置与 AST fallback，保留当前页面 sections 结构。新 Agent 页面和浏览器验收随 C4/C5 完成。
- [ ] C4：实现单一 Agent 表、模型引用与稳定部署键，启用策略落到启动和恢复路径。**范围：** 新 agents/runtime_policies/runtime_catalog、runtime_gateway 决议代码及数据库初始化。
- [ ] C5：退役 resync、旧 model refresh、无效果参数和 Assistant 兼容层；同时迁移前端调用与旧测试。
- [ ] C6：更新 Agent/Models 使用说明和 platform-api README，每部分说明职责、入口和禁止越界的内容。

## 验证要求与记录

- [ ] Platform 镜像中不存在 Runtime 源码、宿主路径挂载，Graph 发现/schema/Agent 创建仍可用。
- [ ] 新环境零 Assistant 产品记录也能列出部署 Graph；目录查询不会 POST /assistants。
- [ ] 上游未部署 Graph 不会因本地文件存在被展示为可执行；不可用时返回明确错误或标注快照陈旧。
- [ ] schema 与真实图的 input/output/state/context 一致，探测不产生外部资源副作用。
- [ ] 同一逻辑部署更换 upstream 地址后，新平台 Agent、模型和默认策略仍保持身份，无凭据覆盖。
- [ ] 用户模型配置可真实执行；刷新能力不会删除配置；凭据只写不读。
- [ ] Agent 禁用、模型禁用、无权限项目和新平台既有 Thread 场景均拒绝不允许的新执行。
- [ ] 前端无 resync、Operations 和旧模型刷新入口；目录刷新直接调用受控 HTTP，不创建异步任务。

2026-09-10：已发现静态目录测试失败及 post21 Graph/schema 查询缺口。该发现来自源码检查，不是端点实测成功。C1–C6 尚未实施。

## 状态

进行中（partial）。C1–C3 后端实现已推进，C4 的稳定部署键已落地；单表 Agent、统一模型决议、旧任务/别名退役与真实联调尚未完成。当前安装的旧 post21 不能因本地源码已修改就视作具备新契约。

### 2026-09-10 远端发现实施

见 [05 远端 Graph 与 schema](implementation/05-remote-graph-discovery.md)。官方文档确认 graph_id 可使用部署 Graph 默认配置；GraphHarbor 在启动时为部署 Graph 注册系统默认 Assistant，平台使用官方 Assistant 查询；自定义 GET /graphs 已撤销。schema 使用 LangGraph 公共 JSON Schema 方法；state 使用包含状态 stream channels 的浅副本生成，不修改共享图，不调用节点。

局部验证覆盖零 Assistant 行、未登录拒绝、UUID 项目隔离、输入/输出/状态差异、读取不刷新、非法响应保留快照与受控字段展示。容器整体验收按用户要求后置。

2026-09-10 用户再次确认：GraphHarbor 只实现 LangGraph Server 通用能力，不增加面向平台业务的接口。完整接口等价性专项后置；本轮仅验收默认 Assistant 发现与 schema 链路。修订见 [06](implementation/06-official-assistant-discovery.md)。
