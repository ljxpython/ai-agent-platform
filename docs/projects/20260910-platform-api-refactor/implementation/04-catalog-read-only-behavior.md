# 目录查询只读化

## 改动时间

2026-09-10

## 相关任务

- C2：目录查询不隐式刷新
- C5：去除 Assistant mutation

## 改动内容

`list_graphs` 不再因本地目录为空而隐式调用 refresh；目录查询只读取平台快照。`refresh_graphs` 不再通过 `POST /assistants` 为静态 Graph 创建上游记录，刷新只消费上游返回并更新快照。这样 GET 不产生写操作，也不会把平台目录逻辑越界成上游 Assistant 管理。

## 验证

- `tests.test_runtime_catalog_delegation`：11 项通过。
- 现有静态 Graph 保留测试继续通过；完整远端 Graph registry 合同仍待 C1。
