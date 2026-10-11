# 知识 MCP 实施记录

2026-10-11，用户批准方案并授权本地源码部署/非前端测试。平台Worktree与知识工程原目录见README；未commit/push/建分支。DeerFlow只读参考，前端源码未改。

## 知识工程

- `pyproject.toml` / `uv.lock`：LightRAG/FastMCP基础查询与UTF-8文本入库独立安装，Docling/RAGAnything置documents extra。本机Intel无Torch2.11 wheel，PDF路径保留并标Block。
- `src/mcp_server.py:create_server()`：FastMCP TokenVerifier、原生ToolResult/ToolError、strict input、lifespan。只读query/list/status均按认证scope，query只有query/top_k。
- `src/knowledge/auth.py`：Bearer≥32、project UUID、tenant UUID或平台既有__default、namespace唯一项目归属；stdio显式有效token，无匿名兜底。
- `project_paths.py:build_knowledge_project_paths()`：单段有限namespace与resolve/symlink防逃逸。
- `publication.py`：POSIX flock读写互斥、signature/manifest/ready门禁。服务持读锁，离线CLI单写，发布后immutable。
- `document_registry.py:_save()`：validate manifest与临时文件原子替换；不是并发事务。
- `schemas.py`：query trim1–2000、top_k严格整数1–8；旧CLI未实现document_ids明确拒绝。
- `citations.py:build_retrieval_sources()`：ready opaque doc locator精确匹配，sources包含source_id/document_id/chunk_id/title/kind/preview/truncated；8条、800字符、12KiB，同名编号，无假页码/下载URL/raw_data。
- `rag_engine.py:get_lightrag()/retrieve()/close()`：每namespace明确LightRAG workspace/cache、pipeline初始化60秒、关闭30秒，初始化失败/取消清理，清理异常仅记类型并保留原初始化错误/取消，多个engine关闭失败也完成其他清理。MCP仅一次aquery_data，不aquery；ingest opaque ids/filepaths并核对processed。
- `ingest_service.py`：md/txt直接文本入库，PDF/Office可选Docling；失败/取消保存failed且不发布。`cli.py`新增publish及finally close，部分index不可发布，accepted=false返回退出1。
- `demo_support.py` / `parser_adapter.py`：重依赖lazy导入，文本无需TEST/VISION；Embedding形状/finite校验；LLM_EXTRA_BODY_JSON复用上游支持参数。DeepSeek抽取关闭thinking后新版本实测成功，未改平台默认模型。
- 测试：stdio/smoke同步、HTTP/security/lifecycle/LLM配置；README/env/接入/运行/能力文档同步。

## Platform API

- `config.py:Settings`：默认空tenant:project→resource mapping，结构/标识/唯一scope验证。`application/knowledge_bindings.py:build_knowledge_binding()`只按可信身份生成现有binding。
- `RuntimeGatewayService.create_thread()`：确定Thread ID后内部签发，保留其他受管binding；fork沿新create重签。不批量改旧Thread、没有知识CRUD。
- `core/runtime_contract.py`：递归拒绝runtime_resource_bindings和__graphharbor_thread_metadata；normalize payload/Protocol入口覆盖。
- `application/thread_access.py:initial_metadata()` / `adapters/langgraph/sdk_client.py:redact_runtime_private_fields()`：阻客户端身份/资源透传，公开Thread/state/history/SSE过滤。
- `presentation/http.py`：现有依赖注入配置，没有新增业务路由。
- `test_knowledge_mcp_bindings.py`及相关回归；`test_execution_budget_projection.py`排除本来公开的agent_plan/auto_title_pending，避免旧全private断言删产品字段。
- 无知识业务表。空库原双head阻止升级，新增 `20261011_0008_merge_runtime_heads.py` 无DDLmerge，隔离PG真实应用。

## Runtime

- Dear生产 `tools/mcp.py`迁到公共 `runtime_service/tools/mcp.py:load_mcp_tools()`，所有已发现调用者和旧测试导入更新；纯配置迁 `runtime/mcp_config.py`，不留双loader。
- connection.scope与binding tenant/project在discovery前比对；跨连接同名取集合，同连接重复/实际重名/保留名冲突/非readOnly拒绝；保留官方0.3.2 Adapter、临时session、allowlist和取消/传输语义。
- `tools/knowledge.py`官方interceptor在Adapter转换前做白名单与大小约束，content与structuredContent同值，原isError固定安全错误。
- `middlewares/filesystem.py`：知识F04按更小预算缩完整preview/条目并同步artifact，极小预算合法JSON error；不写半截JSON引用。
- Dear/Showcase两主图 `agent.py`、`runtime/capabilities.py`、prompts显式接入；defaults/catalog实际tool list一致；schema/offload/Plan/deny不联网，子图不扩权。
- 真实服务账号发现 `runtime/auth.py`原credential_id白名单/VerifiedDelegation字段遗漏及from_user位置偏移，补字段/白名单并用keyword恢复callback_context/run_acceptance；保留已有subject/UUID验证。新回归和真实grant撤权通过。
- 应用迁移双head增加 `0004_merge_runtime_heads.py` 无DDLmerge，实际隔离PG应用。
- 新projection/官方HTTP协议/两图组合/真实平台E2E；标准/envexample/导航同步。

## 本地联调与交接

`scripts/local-stack.sh` 增加knowledge-register/start/stop/restart；登记source/端口、避免其他worktree冲突。进程识别限登记端口+匹配命令+源码归属；destroy有知识监听拒绝。知识单独start/restart也沿现有失败清理回收本次启动进程。四项登记/冲突/归属自检和真实启停通过。其余平台资源仍用既有隔离脚本。

4份真实Worker ToolMessage与6份受控provider→官方Adapter→F04 fixture已采集；无秘密、服务器binding/路径。UI处理同名来源/无命中/error/截断的验收由同事接续。详细结果见verification，未通过的PDF/业务质量不是“全部完成”。

服务配置/Runtime标准、Worktree登记规范和JWT/SSE既有约束同步证据；两跨服务草案保留draft，未因局部文本验证宣称毕业。

## 基线与风险

Runtime全量原17项失败中5项credential问题修复后相关91项通过；其余12项在HEAD快照复现。额外旧Docker fake fixture也复现失败，无实际Docker启动。API全量3fail/3error中委托credential已修复，其余HEAD或HEAD+无DDLmerge复现。未顺手更改其他业务/测试。

扩大API pytest曾为23失败/68通过，全部23失败均在旧 `test_run_acceptance.py`，夹具缺 `thread_id`；用HEAD源码及HEAD测试快照复现同23失败/9通过。剔除这个已确认基线文件后本次相关六文件59项及334个subtest通过；不把unittest未收集到pytest函数的“0 tests”当证据。知识工程最终24项通过。

排查时曾误回显私有模型配置，本轮后来也有本任务测试服务token进入失败输出：测试token已撤旧换新，请求headers repr已隐藏；个人上游模型凭据需用户自行轮换。没有在交接fixture写秘密。经验提案待用户确认后再写lessons，当前未擅自写入。
