# platform-api 项目知识工作台设计稿

## 1. 文档目的

本文说明 `apps/platform-api` 在新默认口径下如何承接 **project-scoped knowledge facade**。

本文同时区分：

- **Current reality**：今天控制面仍围绕项目默认 workspace 工作
- **Preferred future default**：若上游支持 metadata-aware retrieval，平台控制面应透出通用 filter 语义，而不是扩散 workspace 语义

## 2. Current reality

当前 `platform-api` 的正式职责仍是：

- `project_id` 解析
- permission / audit / operations
- `project_id -> workspace_key` 治理映射
- 向 LightRAG 注入 workspace 相关上下文

这条边界不变。

## 3. 默认原则

### 原则 A：平台 API 仍然是 project-scoped

对前端和其他 human-facing consumer：

- 主主语义仍然是 `project_id`
- 不新增 knowledge-space chooser 作为默认主模型

### 原则 B：workspace 继续是私有治理实现

即使存在 fallback multi-workspace，也不应让：

- 前端直接持有 workspace 语义
- runtime 依赖 workspace 规则

### 原则 C：future 透出的是通用 retrieval contract

如果 LightRAG 增加 metadata-aware retrieval，`platform-api` 应优先透出：

- 通用 metadata/tag/filter 查询能力
- 通用 retrieval scope / boost 语义

而不是：

- AITestLab 私有 taxonomy 协议
- 基于 workspace 的业务语义切分 API

## 4. 当前现实下的 API 口径

当前默认链路仍围绕：

```text
/api/projects/{project_id}/knowledge/*
```

且其现实基础仍是：

- 项目级知识空间
- 项目默认 workspace 映射
- 不向调用方暴露 metadata-aware retrieval 为现成能力

## 5. Preferred future default

如果上游可改，建议 `platform-api` 在 query 类接口上保留 project-scoped 外壳，同时为 future contract 预留通用能力位：

- `filters`
- `retrieval_scope`
- `boosts`

但这些字段在文档里必须标成：

- preferred future default
- target state
- gated on upstream LightRAG capability

## 6. Fallback

如果 future 仍不得不启用 multi-workspace，控制面也应遵守：

- workspace 是平台内部映射细节
- 前端默认仍只看 project-scoped 入口
- 如确需内部路由或策略切分，也不应让“项目内多 workspace”成为公开主产品对象，除非另开正式决策

## 7. Rejected option

**Rejected**：把 AITestLab 私有 `domain/layer/module` 作为控制面到上游的协议常量。

平台可以管理自己的 taxonomy，但与上游交互时优先使用通用 metadata/filter 协议表达。

## 8. 结论

在新默认方案下，`platform-api` 的职责不是从 workspace-first 转成 taxonomy-first，而是：

- 保持 project-scoped facade
- 隐藏 workspace
- future 暴露通用 retrieval contract
- 维持 clear governance boundary

## 9. File-level adaptation anchor: `contracts.py`

为把这轮已讨论清楚的适配面真正落到 repo 内，`platform-api` 这一层的 file-level 主锚点明确为：

- `apps/platform-api/app/modules/project_knowledge/application/contracts.py`
- 配套透传链路：
  - `apps/platform-api/app/modules/project_knowledge/presentation/http.py`
  - `apps/platform-api/app/modules/project_knowledge/application/service.py`
  - `apps/platform-api/app/adapters/knowledge/client.py`

### 9.1 Current reality

当前 `ProjectKnowledgeQueryRequest` 只覆盖：

- `query`
- `mode`
- token / top_k / chunk_top_k
- `hl_keywords` / `ll_keywords`
- `user_prompt`
- `enable_rerank`
- `include_references`
- `include_chunk_content`
- `stream`

这意味着：

- `platform-api` 目前还没有正式 metadata-aware retrieval contract
- 任何 file-level 改动设计都必须写成 **target state**，不能写成已实现事实

### 9.2 Preferred future default（target state）

如果 LightRAG 补齐通用 metadata-aware retrieval，上层控制面建议只做 **contract + validate + pass-through**，而不在 control-plane 内实现检索智能：

#### Query contract 扩展位
建议在 `contracts.py` 增加通用字段：

- `metadata_filters`
- `metadata_boost`
- `strict_scope`

但必须保持语义通用，例如：

- `tags_any`
- `tags_all`
- `attributes`
- `weight`

而不是把 `domain/layer/module` 直接写死为上游协议常量。

#### Ingest contract 扩展位
如果上游提供 ingest metadata 能力，这一层需要能承载：

- 文档 metadata
- tags
- attributes

这里的职责仍然是：

- 校验
- 透传
- 错误映射
- 与项目治理上下文绑定

### 9.3 Not recommended

`platform-api` **不应该**：

- 把 `workspace_key` 暴露成 human-facing 主语义
- 在 control-plane 内实现 taxonomy 推理器
- 用 AITestLab 私有语义替代上游的通用 metadata/filter contract

### 9.4 File-level implementation checklist

当进入实现阶段，建议按下面顺序落：

1. `contracts.py`
   - 扩 `ProjectKnowledgeQueryRequest`
   - 新增 metadata filter / boost model
2. `presentation/http.py`
   - query / stream query 接收新字段
3. `application/service.py`
   - 透传到 upstream client
4. `adapters/knowledge/client.py`
   - 原样发给 LightRAG

这条链路的正式含义是：

> `platform-api` 负责 **项目治理 + 契约承载**，而不是负责“解释什么是底层架构/应用层/组件层”。

## 10. Field-level payload draft（target state）

> 注意：本节全部属于 **preferred future default / target state**。截至当前，下面这些字段还没有在现有正式 HTTP 契约中落地。

### 10.1 Query payload draft

建议 `ProjectKnowledgeQueryRequest` 在现有字段基础上，增加以下通用能力位：

```json
{
  "query": "解释当前项目的存储架构",
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
  "strict_scope": true,
  "include_references": true,
  "include_chunk_content": true
}
```

建议语义：

- `metadata_filters`
  - 硬过滤，决定候选集
- `metadata_boost`
  - 软优先，影响排序或 rerank
- `strict_scope`
  - `true`：严格只查过滤域
  - `false`：允许跨域补充，但优先本域

### 10.2 Contract model draft

建议在 `contracts.py` 抽成通用模型，而不是让 `ProjectKnowledgeQueryRequest` 直接承载 AITestLab 私有 taxonomy：

```python
class KnowledgeMetadataFilters(BaseModel):
    tags_any: list[str] = Field(default_factory=list)
    tags_all: list[str] = Field(default_factory=list)
    attributes: dict[str, str | list[str]] = Field(default_factory=dict)

class KnowledgeMetadataBoost(BaseModel):
    tags_any: list[str] = Field(default_factory=list)
    attributes: dict[str, str | list[str]] = Field(default_factory=dict)
    weight: float | None = None
```

然后：

```python
class ProjectKnowledgeQueryRequest(BaseModel):
    ...
    metadata_filters: KnowledgeMetadataFilters | None = None
    metadata_boost: KnowledgeMetadataBoost | None = None
    strict_scope: bool | None = None
```

### 10.3 Upload payload draft

#### Minimal-change path

如果继续保持当前 binary upload facade，可考虑增加：

- `x-knowledge-filename`
- `x-knowledge-metadata`

例如：

```http
x-knowledge-filename: architecture-overview.md
x-knowledge-metadata: {"tags":["architecture","storage"],"attributes":{"layer":"infrastructure","module":"storage"}}
```

#### Long-term path

更长期更合理的方向是升级为 `multipart/form-data`：

- `file`
- `metadata`

例如：

```json
{
  "tags": ["architecture", "storage"],
  "attributes": {
    "layer": "infrastructure",
    "module": "storage"
  }
}
```

### 10.4 Documents list filter draft

`DocumentsPageQuery` 未来可选补：

```json
{
  "page": 1,
  "page_size": 20,
  "status_filter": "processed",
  "metadata_filters": {
    "tags_any": ["architecture"],
    "attributes": {
      "layer": ["infrastructure"]
    }
  }
}
```

但这不是第一必需项；优先级低于 query payload 与 ingest metadata。

### 10.5 platform-api 的职责边界

即使 future 加了上述字段，`platform-api` 也只负责：

- contract 承载
- validate
- pass-through
- project governance binding

不负责：

- taxonomy 推理
- query strategy 编排
- 物理隔离建模

## 11. `platform-api` 字段命名建议（v1）

为减少 future contract 漂移，`platform-api` 建议直接采用与上游 target-state 一致的 v1 字段：

### Query request
- `metadata_filters`
- `metadata_boost`
- `strict_scope`

### Ingest payload
- `metadata`
  - `tags`
  - `attributes`

### 约束

`platform-api` 不新增 AITestLab 私有别名，例如：
- `domain_filters`
- `layer_filter`
- `knowledge_scope`

如果前端内部想保留更贴近用户语言的本地变量名，也应在 service 层归一化后再发给控制面。
