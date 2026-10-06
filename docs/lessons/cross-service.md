# 跨服务契约经验库

> 适用范围：Platform API、Runtime Service 之间的 HTTP 契约、Delegation、授权隔离和跨服务测试。
> AI 读取时机：开始处理跨服务契约或 Delegation 改动前按需读取。

---

## [坑] Delegation operation 测试依赖固定数量或索引

- **场景：** 新增或调整 Delegation `scope.operation` 枚举时
- **错误：** 用固定枚举数量、列表索引或连续切片推断测试边界；新增合法 operation 后，旧测试误报或把 operation 分类错位
- **正确：** 按 operation 名称集合和资源白名单断言；新增 operation 同时补充专属隔离测试，避免测试结构依赖枚举顺序
- **日期：** 2026-10-06
