# 文档导航

`apps/interaction-data-service` 当前还处于设计阶段；这里先维护对后续实现真正有约束力的设计稿，而不是空泛愿景。

## 先读这些（当前权威）

1. `docs/service-design.md`
   - 服务职责边界、数据库策略、HTTP 契约、agent/tool 对接方式
2. `docs/usecase-workflow-design.md`
   - 用例生成真实案例：上传、分析、评审、人工确认、落库、CRUD 管理

## 文档约定

- 当前目录只保留仍然指导后续实现的设计文档
- 这里描述的是 `interaction-data-service` 的目标设计，不代表代码已经落地
- 真正开始实现后，当前行为应以代码和后续补充的 `README.md` / `current-architecture.md` 为准
