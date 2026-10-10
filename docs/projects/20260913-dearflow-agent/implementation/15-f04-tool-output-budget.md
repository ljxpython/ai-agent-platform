# F04 官方能力补齐

## 时间与范围

2026-10-09；对应 15 专题 R01-R05，用户已批准实施。进度以专题任务表为准，本文件只解释实现。

## 生产改动

- `apps/runtime-service/src/runtime_service/middlewares/conversation_offloading.py::ConversationOffloadingMiddleware.__init__`：从未传 args 压缩参数，改为官方 `truncate_args_settings`，trigger/keep 分别为输入预算的 85%/10%，max_length=2000；只改模型 request，checkpoint 保留原参数。
- 同模块 `resolve_tool_output_limit()` 及 `middlewares/__init__.py` 导出：复用受信主/备模型输入预算最小值，`max(1, min(20000, B // 16))`。不新增容量查询、Context 或用户配置。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py::_build_agent`、`services/demo/showcase_demo/agent.py::_build_agent`、`services/demo/showcase_demo/subagents.py::build_subagents`：受管执行且上下文开关开启时，根和已有子角色共用阈值；schema-only/关闭时维持原装配。
- `apps/runtime-service/src/runtime_service/middlewares/filesystem.py::ResultFilesystemMiddleware`：继承官方 Filesystem，并保持同名替换。只在超限结果的原外置目录下加正文 SHA256，官方仍完成写入、head/tail、身份元数据和失败处理。每次处理使用浅副本，不修改共享 middleware；旧路径继续由原 backend 读取。

## 碰撞修复依据

锁版本 DeepAgents 0.7.8 以 sanitized call ID 作为文件名；StateBackend.write 覆盖同键，官方 task 会复制并回传 files。同 call ID 的父/子结果会令父预览对应的文件变成子正文。只拒绝已有键无法防并行子图从空快照写同键。正文摘要作为路径片段使不同结果分离，同正文重放保持确定性；不改变公开 API/schema、namespace 或存储结构。

该薄扩展依赖锁版本内部方法，依赖升级必须复验。它不提供公共 files 私有化、客户端禁止改写或完整 shell 日志捕获；这些是既有明确延期边界。

## 验证与测试适配

- `tests/middlewares/test_conversation_offloading.py`：预算与 provider 标准/OpenAI/Anthropic 序列化；模型 request 变短、原 state 不变。
- `tests/middlewares/test_tool_output_budget.py`：官方外置与薄扩展对照、分页/重建/hash、主子同 ID/并行子图、多模态 Command 保真、失败/异常/取消不重跑原工具、容量矩阵。
- Dear/Showcase 装配测试增加阈值断言；维护 Workspace 测试补当前 config 参数；Showcase timeout 测试按现有“只主图软提醒”规范校正断言，未改生产 timeout。
- API 三个测试只修过时 fixture 和增加公共 files 现状契约断言，无 API 生产改动。
- 隔离 HTTP/PG/Redis/Worker fixture 复用已有栈，不注册到生产 graph；合成模型签名适配官方异步调用、read_file调用ID每次独立、子图注册名使用general-purpose。Showcase受控execute保留成功回执并计入hash，Thread策略通过现有PATCH更新，不能依靠Run context提升权限。每次恢复验证真实Run终态；PG成本记录blobs/writes/checkpoint JSON三种口径。

非前端验证完成：干净锁环境102 passed/1 skipped，隔离HTTP整链1 passed（PG子测试1 passed，真实模型3 passed），API契约/Workspace/策略授权均通过；16文件lint/format与diff检查通过。命令、成本实证、范围外失败及未验项在15的独立Phase区及evidence记录；前端和整个F04 Final尚未执行。未修改依赖、API生产代码或前端业务代码。
