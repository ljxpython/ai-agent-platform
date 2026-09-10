# 首个切片：退役知识库与测试用例平台业务

## 时间与任务

2026-09-10；对应 04 的 S1/S2。先实施不依赖 GraphHarbor 新合同的业务退役，形成可验证切片；S2 的 Operations 全面退役仍待 G5/C5，不标完成。

## 改动

- 删除 71 个受 Git 管理的业务文件：platform-api 的 project_knowledge/testcase 模块、knowledge/interaction_data adapters、专属测试，以及 platform-web 的对应模块、services 和三个 Testcase 平台组件。
- `app/entrypoints/http/router.py` 不再注册两块业务；`core/db/init_db.py` 不再导入知识空间模型；删除专属 Settings、权限码及权限映射。
- `modules/operations/bootstrap.py`、`application/executors.py` 删除文档/用例导出和知识库 scan/clear 执行器及其装配。`application/service.py::_require_submit_access()` 在权限校验后，仅接受仍有实际执行器的目录刷新和 Agent resync，未注册类型返回 `unsupported_operation_kind`，不会持久化任务。旧 Run 协调器由网关内部驱动，未新增公开提交权限。
- 前端删除 knowledge/testcase/testcase-v2 路由、侧栏、项目详情和总览入口、共享类型、权限、图标及国际化条目；Operations 不再链接已退役页面。项目详情的“复制项目 ID”解除误绑的知识库权限，只依赖项目是否存在。
- 删除 openpyxl 和五个图谱专属依赖（graphology、两种布局、sigma、minisearch），更新 uv.lock/pnpm-lock.yaml；锁文件只移除相关依赖，没有升级其余包。
- 两份 Compose、环境示例和本地部署契约删除 Platform 专属外部服务配置；Platform API 不再 depends_on interaction-data-service。独立结果服务和 Runtime/GraphHarbor 执行设施不在删除范围。
- README 更新当前进度；活 handbook/Operations 标准标注旧范式已被重构方案取代，并移除 testcase 开发示例。新 src 目录与新表尚未实现，文档未宣称已完成。

关键行为变化：

```python
# 之前：知识维护注册为通用任务；其他任意 kind 也能提交。
# 现在：权限校验后仅允许现存公开任务，其余提交直接失败。
if kind not in {
    "runtime.models.refresh", "runtime.tools.refresh",
    "runtime.graphs.refresh", "assistant.resync",
}:
    raise BadRequestError(code="unsupported_operation_kind", message="Unsupported operation kind")
```

本次没有新建兼容别名、数据迁移器或空业务框架，没有连接或清空旧业务数据库，没有修改 Runtime 产品代码。修改 Operations 既有未提交文件时只清理本切片相关逻辑，原有项目角色处理等改动保留。

## 测试调整与验证

- 删除三个知识库专属后端测试文件及 Testcase 导出/归一化测试；保留同文件中仍在使用的 Agent resync、网关与 Worker 测试。
- IAM 测试用仍有效的 Agent 写权限验证原有角色矩阵；通用 Worker 重试测试继续使用模拟执行器，kind 改为仍注册的任务名，不删除重试断言。
- 新增 HTTP/OpenAPI 退役路由检查，以及对知识库、Testcase、未知任务的拒绝和零落库检查；前端新增三个退役工作区不再注册的路由测试。
- 后端全量：155 项，151 通过、1 失败、3 跳过，294.314 秒。唯一失败仍是基线中的 `test_refresh_graphs_preserves_static_graphs`，要求生产本地 Graph 配置包含 showcase_demo；未通过修改生产注册绕过失败。外部集成跳过不计通过。
- 前端路由/权限：10 项通过；全量 ESLint、Python compileall 通过。
- uv.lock 更新通过；pnpm 离线首次缺 parse5 元数据，正常联网生成锁文件后，冻结锁文件离线校验通过。未发布任何包。

构建、部署检查的最终结果与完成度统一见 [04 验证记录](../04-service-structure-and-migration.md)。本记录只说明首个退役切片，网关、Agent、新基础和新数据库仍待后续任务。
