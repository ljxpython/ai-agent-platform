# runtime-side MCP 边界说明

## 1. 文档目的

本文继续确认一个关键边界：

> future runtime-side knowledge consumption 不通过 `platform-api` 扩成统一程序化 API，而是优先走 **LightRAG MCP**。

在新默认方向下，这条边界不变，只是增加了一条约束：

> runtime-side 未来即使要利用 metadata-aware retrieval，也应仍然保持 `project_id`-centric，而不是泄露 workspace 细节。

## 2. Current reality

当前 runtime-side 事实仍然成立：

- `runtime-service` 只信任 `project_id`
- workspace 细节不应外漏
- runtime-side 消费知识能力优先走 MCP，而不是 control-plane facade

## 3. Preferred future default

如果 future 支持 metadata-aware retrieval，runtime-side 的理想输入仍是：

- `project_id`
- 通用 query / retrieval scope / metadata filter 表达

而不是：

- `workspace_key`
- AITestLab 私有 taxonomy 常量
- 由业务服务自己决定项目内如何分 workspace

## 4. 为什么这条边界要坚持

因为否则会出现两种坏结果：

1. runtime-service 被迫理解 control-plane 内部治理实现
2. workspace 语义在多个服务里扩散，未来更难收口

## 5. fallback

如果最终因为上游能力不足而启用 multi-workspace fallback，也应遵守：

- runtime 调用者不直接硬编码 workspace
- fallback 逻辑应尽量封装在上游/MCP/tooling 层

## 6. Rejected option

**Rejected**：让 runtime-side 为了项目内知识域隔离而直接持有 AITestLab 私有 taxonomy 与 workspace 决策逻辑。

## 7. 结论

这份边界文档的正式结论仍是：

- human-facing path：`platform-web -> platform-api -> LightRAG`
- runtime path：`runtime-service -> LightRAG MCP -> LightRAG`
- future metadata-aware retrieval 也不能改变 runtime 的 `project_id`-centric 原则

## 8. Service landing zone: `test_case_service_v2`

这轮讨论已经把 runtime-side 的适配范围进一步压实：

- 服务落点：`apps/runtime-service/runtime_service/services/test_case_service_v2`
- 具体适配锚点：`apps/runtime-service/runtime_service/services/test_case_service_v2/knowledge_mcp.py`

配套受影响文件还包括：

- `apps/runtime-service/runtime_service/services/test_case_service_v2/prompts.py`
- `apps/runtime-service/runtime_service/services/test_case_service_v2/knowledge_query_guard_middleware.py`
- `apps/runtime-service/runtime_service/services/test_case_service_v2/README.md`

### 8.1 Current reality

当前 `test_case_service_v2` 的正式边界是：

- 只信任 `RuntimeContext.project_id`
- 不学习 `workspace_key`
- 通过私有 MCP 调：
  - `query_project_knowledge`
  - `list_project_knowledge_documents`
  - `get_project_knowledge_document_status`

这个边界本轮**不改变**。

### 8.2 Preferred future default（target state）

如果 future 支持 metadata-aware retrieval，`test_case_service_v2` 的适配应是**最小侵入式**的：

#### MCP tool 层
优先保持工具名不变，只扩参数：

- `metadata_filters`
- `metadata_boost`
- `strict_scope`

也就是说，runtime service 学的是：

- `project_id`
- generic filters

而不是：

- workspace routing
- knowledge space chooser
- AITestLab 私有上游协议

#### Prompt / Guard 层
服务内可以新增策略：

- 当用户明确请求“底层架构 / 应用层 / 某模块”时，优先带过滤条件查询
- 无过滤线索时，再做全项目裸查

这里允许存在 **服务内本地映射**，但它必须只是：

- 本地 query strategy
- 不外溢成上游协议语义

### 8.3 File-level implementation checklist

1. `knowledge_mcp.py`
   - 扩 `query_project_knowledge` 可选参数
2. `prompts.py`
   - 补“有明确知识域时优先带 filter”规则
3. `knowledge_query_guard_middleware.py`
   - guard 从“必须先查知识库”升级为“必要时必须带 domain-aware filter 查”
4. `README.md`
   - 记录服务仍然 `project_id`-centric，不学习 workspace

### 8.4 Hard boundary

`test_case_service_v2` **不应该**：

- 学习 `workspace_key`
- 管理项目内多个 knowledge spaces
- 承担 taxonomy 配置中心职责

正式边界应保持：

> runtime-side 只消费 **project-scoped + generic metadata-aware retrieval**，不消费 workspace internals。

## 9. MCP tool parameter draft（target state）

> 注意：以下内容属于 `test_case_service_v2` 在 future metadata-aware retrieval 能力可用时的最小适配草案，不代表当前工具已支持这些字段。

### 9.1 Tool parameter shape

当前建议保持工具名不变，只扩展 `query_project_knowledge` 的可选参数：

```json
{
  "project_id": "<current-project-id>",
  "query": "请分析当前项目的底层架构设计",
  "metadata_filters": {
    "tags_any": ["architecture"],
    "attributes": {
      "layer": ["infrastructure"]
    }
  },
  "metadata_boost": {
    "attributes": {
      "module": ["storage", "network", "compute"]
    },
    "weight": 1.2
  },
  "strict_scope": true
}
```

### 9.2 Why keep the tool name stable

保持 `query_project_knowledge` 工具名不变的收益：

- 对 `test_case_service_v2` 的 graph 侵入最小
- 提示词、guard、中间件只要适配参数，不必重新组织工具发现逻辑
- 对服务边界影响最小

### 9.3 Prompt adaptation draft

`prompts.py` / skills 未来建议补一条：

- 当用户明确请求某个知识域（如底层架构、应用层、组件设计、某模块）时，优先带 metadata filters 查询
- 没有过滤线索时，才做全项目裸查

### 9.4 Guard adaptation draft

`knowledge_query_guard_middleware.py` 未来建议从：

- “必须先查知识库”

升级为：

- “如果用户任务已显露明确知识域，且上下文已有范围线索，则第一次知识查询必须带 scope/filter”

### 9.5 Local mapping is allowed, protocol leakage is not

`test_case_service_v2` 内部允许做很薄的一层本地映射，例如：

- “底层架构” -> `tags_any=["architecture"]`, `attributes.layer=["infrastructure"]`
- “存储模块” -> `attributes.module=["storage"]`

但这层映射必须保持为：

- 服务内 query strategy
- 不外溢成上游协议内置语义

### 9.6 Runtime hard boundary

runtime-side 未来仍然不应该新增：

- `workspace_key`
- knowledge space chooser
- 项目内多 workspace 路由逻辑

即：

> `test_case_service_v2` 继续学习 `project_id + generic metadata-aware filters`，而不是学习 workspace internals。

## 10. MCP 参数命名建议（v1）

runtime-side / MCP tool 参数建议直接复用同一组 target-state 字段：

- `metadata_filters`
- `metadata_boost`
- `strict_scope`

以及 ingest/写入场景中的：
- `metadata.tags`
- `metadata.attributes`

### 原因

这样 `test_case_service_v2` 的 prompt、guard、tool adapter 可以只学一套名字：

- 对上游协议一致
- 对 control-plane facade 一致
- 对前端 payload 一致

### 运行时边界重申

即使参数新增了这些字段，runtime-side 仍然不应新增：
- `workspace_key`
- `knowledge_space_id`
- AITestLab 私有 taxonomy 协议字段
