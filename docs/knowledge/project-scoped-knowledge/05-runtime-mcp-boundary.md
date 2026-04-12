# runtime-side MCP 边界说明

## 1. 文档目的

本文专门记录一个容易被误解但已经确认的边界：

> future runtime-side knowledge consumption 不通过 `platform-api-v2` 扩一套统一程序化 API，而是优先走 **LightRAG MCP**。

## 2. 为什么要单独写这份文档

如果不把这个边界单独写清楚，后续很容易出现两个误区：

1. 为了让 runtime-service 用知识能力，反过来把 `platform-api-v2` 变成一个重 runtime facade
2. 为了图省事，让 runtime-service 直接硬编码 `workspace_key` 或绕过项目治理语义

这两条都不符合当前仓库范式。

## 3. 当前仓库已有先例

`test_case_service` 已经采用私有知识库 MCP 工具装配方式，而不是把知识检索能力写成 platform control-plane 的一部分（`apps/runtime-service/runtime_service/services/test_case_service/DESIGN.md:66-127`）。

这里至少说明两件事：

- runtime-side 通过 MCP 消费知识能力在当前仓库并不陌生
- 这条路线比“再扩一个统一平台 runtime API”更贴近当前架构边界

## 4. 正式边界

### 4.1 Human-facing path

```text
platform-web-vue -> platform-api-v2 -> LightRAG
```

这条链负责：

- 项目知识工作台
- 文档管理
- 检索验证
- 图谱浏览
- 设置页
- permission / audit / operations

### 4.2 Future runtime path

```text
runtime-service / other services -> LightRAG MCP -> LightRAG
```

这条链负责：

- agent / service 在运行期程序化查询项目知识
- 作为 tool / MCP resource 被 runtime graph 消费

## 5. 这条边界带来的后果

### 好处

- `platform-api-v2` 继续专注 control plane
- runtime-service 不需要为了工具调用去适配 control-plane 页面协议
- LightRAG 可以把 HTTP facade 和 MCP facade 建在同一数据面能力上

### 风险

- 后续仍要明确 `project_id -> workspace_key` 的 MCP 内部解析来源
- 如果 future shared knowledge / multi-knowledge 进入范围，MCP 输入协议也要同步升级

## 6. 当前结论

因此：

- Phase 1 不做统一 runtime consumption API
- Phase 1 只把 human-facing project knowledge workspace 做稳
- Phase 2 再把 LightRAG MCP 作为 runtime-side 正式接入面
