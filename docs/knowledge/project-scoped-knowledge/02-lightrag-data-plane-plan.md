# LightRAG 数据面收口方案

## 1. 文档目的

本文聚焦 LightRAG 数据面，并明确区分：

- **Current reality**：当前 LightRAG / AITestLab 公开契约现状
- **Historical baseline（2026-04-12）**：曾经默认以 multi-workspace 为主路径的数据面思路
- **Preferred future default**：如果可改上游，默认补齐 generic metadata-aware retrieval

## 2. Current reality

### 2.1 当前已成立的能力

当前公开链路中已存在：

- `LIGHTRAG-WORKSPACE` / workspace 物理隔离语义
- AITestLab 侧 `project_id -> workspace_key` 映射
- documents / query / graph 基于项目默认 workspace 的消费链路

### 2.2 当前尚未成立的能力

当前公开 HTTP API **没有** 暴露：

- 文档写入时的通用 metadata/tag 字段
- 查询时的 `filters` / `metadata_filter` / `domain_filter`
- soft boost / hard filter 的 query contract

因此本文后续关于 metadata-aware retrieval 的内容都属于 **target state**。

## 3. Historical baseline（2026-04-12）

此前的默认方向是：

> 把 LightRAG 优先收口成 request-scoped multi-workspace knowledge data plane

这在 2026-04-12 是合理的，因为当时：

- workspace 是现成可用的硬隔离原语
- metadata-aware retrieval 能力尚不存在
- 使用多 workspace 可以快速证明隔离可控

该路径现在被重新定位为：

- **历史已验证基线**
- **fallback**
- **非默认主方案**

## 4. Preferred future default

### 4.1 默认目标

如果可修改 LightRAG，首选补齐以下**通用**能力：

#### Ingest side
- 文档 metadata/tag 写入
- 文本与文件统一承载 metadata

#### Query side
- metadata/tag filter
- soft boost / hard filter
- 面向 references / chunks / graph retrieval 的一致语义

### 4.2 设计原则

1. `workspace` 保持为项目/租户级物理隔离
2. metadata/tag/filter 负责项目内知识域隔离
3. 上游协议只提供**通用能力**，不内置 AITestLab 私有 taxonomy
4. 现有 consumers 不被迫学习 workspace 细节

## 5. 目标能力分层

### 5.1 Metadata write model（target state）

LightRAG 应支持在 ingest 时附带类似结构：

```json
{
  "metadata": {
    "tags": ["architecture", "storage"],
    "attributes": {
      "domain": "architecture",
      "layer": "infrastructure",
      "module": "storage"
    }
  }
}
```

要求：

- 协议是通用的
- tags/attributes 只是例子，不是 AITestLab 强绑定字段
- 公开能力不依赖 AITestLab 私有命名

### 5.2 Query filter model（target state）

LightRAG 应支持类似：

```json
{
  "query": "explain current storage architecture",
  "filters": {
    "tags_any": ["architecture"],
    "attributes": {
      "layer": ["infrastructure"],
      "module": ["storage"]
    }
  }
}
```

### 5.3 Retrieval behavior

至少区分：

- **hard filter**：严格只检索满足条件的候选
- **soft boost**：候选可跨域，但优先本域结果

## 6. AITestLab 对 LightRAG 的要求

AITestLab 对上游的要求应保持通用：

- 支持 metadata on ingest
- 支持 metadata-aware retrieval
- 支持明确的 filter/boost 语义

AITestLab **不应**要求上游：

- 理解 `domain/layer/module` 是平台专有概念
- 内置平台自定义 taxonomy

## 7. Fallback：什么时候退回 multi-workspace

只有在以下情形下，才把 multi-workspace 作为 fallback：

1. 上游不愿提供通用 metadata-aware retrieval
2. 上游可提供，但检索污染在关键场景仍无法接受
3. 某些知识域必须做硬隔离，soft boost / hard filter 仍不够稳

此时 multi-workspace 仍然是可用路径，但应明确标为：

- fallback
- 非默认

## 8. 对后续 MCP 的影响

future runtime-side MCP 仍应围绕：

- `project_id`
- 通用 query filter / retrieval scope

而不是让 MCP 调用方显式管理 workspace 分片策略。

## 9. 结论

本文件的正式结论是：

- 今天的现实：workspace 是现成能力，metadata-aware retrieval 尚未公开可用
- 2026-04-12 的 multi-workspace 路线：历史基线 + fallback
- 未来默认：单 workspace + generic metadata-aware retrieval

## 10. 接口字段最终建议版（v1）

> 目标：给出一版足够稳定、足够通用、同时避免 AITestLab 私有语义泄漏的字段命名建议。
>
> 说明：本节仍然属于 **target state**，不是 current reality。

### 10.1 设计目标

字段命名应满足：

1. **通用**：不绑定 AITestLab 私有 taxonomy
2. **可扩展**：未来可支持更多 metadata 维度
3. **前后端一致**：LightRAG / `platform-api-v2` / `platform-web-vue` / MCP 参数命名尽量对齐
4. **最小惊讶**：不要同时引入 `scope` / `filter` / `selector` 三套近义模型

### 10.2 推荐主字段

#### Query request（v1）

```json
{
  "query": "...",
  "mode": "mix",
  "metadata_filters": {
    "tags_any": ["architecture"],
    "tags_all": [],
    "attributes": {
      "layer": ["infrastructure"],
      "module": ["storage"]
    }
  },
  "metadata_boost": {
    "tags_any": ["storage"],
    "attributes": {
      "domain": ["architecture"]
    },
    "weight": 1.5
  },
  "strict_scope": true
}
```

#### Ingest request（v1）

```json
{
  "metadata": {
    "tags": ["architecture", "storage"],
    "attributes": {
      "layer": "infrastructure",
      "module": "storage"
    }
  }
}
```

### 10.3 字段选择理由

#### `metadata_filters`
选择它而不是 `filters` 的原因：
- 避免和未来非 metadata 的过滤能力混淆
- 直观表达“这是知识 metadata 层过滤”

#### `metadata_boost`
选择它而不是 `boosts` / `preferences` 的原因：
- 语义直观：这是 metadata 层的排序偏置
- 便于和 `metadata_filters` 配对理解

#### `strict_scope`
选择它而不是 `scope_mode` / `hard_filter` 的原因：
- 最小布尔语义，易被前后端和 MCP 共用
- `true/false` 易映射到“严格/偏好”交互

### 10.4 不推荐的字段名

不推荐：
- `domain_filters`
- `layer_filters`
- `module_filters`
- `scope_selector`
- `knowledge_scope`
- `knowledge_space_id`

原因：
- 容易把 AITestLab 私有 taxonomy 写进协议
- 容易和“多 workspace / 多知识空间”语义误耦合

### 10.5 `attributes` 的约束

`attributes` 推荐保持：

- key: `str`
- value: `str | list[str]`

这样可以兼容：
- 单值维度
- 多值候选
- 上游通用 metadata 存储

不建议在 v1 就引入：
- range
- regex
- nested boolean expression

### 10.6 v1 结论

v1 正式建议字段集：

- ingest：`metadata.tags`, `metadata.attributes`
- query：`metadata_filters`, `metadata_boost`, `strict_scope`

这个命名集应作为：

- LightRAG target-state contract draft
- `platform-api-v2` facade draft
- `platform-web-vue` local state / payload draft
- `test_case_service_v2` MCP tool parameter draft

的统一参考口径。
