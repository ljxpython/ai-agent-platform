# 项目级知识库交付路线图

## 1. 文档目的

本文只回答一件事：

> 在当前已澄清边界下，这个知识库平台化能力应该按什么顺序推进。

## 2. 当前锁定的总顺序

主顺序固定为：

1. **先冻结 AITestLab 侧正式设计与术语**
2. **再收口 LightRAG request-scoped workspace 数据面**
3. **再接 AITestLab 的 human-facing project knowledge control plane**
4. **最后交付 `platform-web-vue` 正式知识工作台**
5. **runtime-side LightRAG MCP 放后续阶段**

## 3. 阶段清单

### Phase 0：文档与口径冻结

- [x] 完成 deep-interview 需求结晶
- [x] 明确 human-facing path 与 future runtime path 的双链路
- [x] 明确第一阶段不做 assistant 绑定
- [x] 明确多知识库 / 共享知识库属于后续阶段
- [x] 在 AITestLab 内创建正式文档目录

### Phase 1：LightRAG 数据面收口

- [x] 统一 workspace 请求解析
- [x] 引入 workspace manager / registry
- [x] 让 documents / query / graph / status 真正按 request workspace 生效
- [x] 补多 workspace smoke test
- [x] 明确平台 service auth

### Phase 2：platform-api-v2 项目知识控制面

- [x] 新增 `project_knowledge` 模块
- [x] 新增 `adapters/knowledge`
- [x] 落 `project_knowledge_spaces` 轻量模型
- [x] project 权限、审计、operation 接入
- [x] human-facing knowledge APIs 跑通

### Phase 3：platform-web-vue / Documents

- [x] 新增 knowledge 模块目录与 service
- [x] 路由接入 `documents`
- [x] 上传 / 分页 / 状态 / 删除 / 清空
- [x] 对接 operation / loading / empty / error

### Phase 4：platform-web-vue / Retrieval

- [x] query 页面
- [x] 引用 / 上下文展示
- [x] 权限与空态校验

### Phase 5：platform-web-vue / Graph

- [x] label search
- [x] graph display
- [x] 属性面板
- [x] 第一阶段默认按只读交互收口

### Phase 6：platform-web-vue / Settings + 文档补完

- [x] 默认知识空间摘要
- [x] workspace 映射说明
- [x] 服务状态/运行说明
- [x] 文档与验收清单回填

### Phase 7：后续阶段（非当前第一阶段）

- [ ] 多知识库绑定
- [ ] 共享知识库
- [ ] 更重的知识资源 / 绑定模型
- [ ] LightRAG MCP 正式化
- [ ] runtime-service 通过 MCP 接项目知识

## 4. 当前推荐的最小上线顺序

如果按最小可见业务价值排序，建议按这个 release ladder：

1. LightRAG 多 workspace 真隔离
2. platform-api-v2 project knowledge facade
3. Documents 页面
4. Retrieval 页面
5. Graph 页面
6. Settings 页面

## 5. 现在不建议做的并行动作

- 不要在 LightRAG 数据面没稳时提前做复杂前端
- 不要在 first-phase 里把 assistant 绑定一起做掉
- 不要为了 future runtime consumption 提前把 platform API 扩成大而全
- 不要在 first-phase 就把 multi-knowledge / shared knowledge 一起落地
