# 来源与上传信任链

2026-10-13；T01–T04。

- `apps/runtime-service/src/runtime_service/tools/knowledge_upload.py::_identity`：原来一律拒绝非空checkpoint_ns；改为比对可信execution_info，root仅允许空或`tools:<task_id>`。子图路径、伪task ID、执行namespace不符、read委托拒绝，保留Plan/offload/原Run和权限校验。
- `apps/platform-api/src/platform_api/modules/knowledge/authorization.py::authorize_operation`：将策略服务导入延迟到函数内；相应测试模型局部加载，避免独立加载时循环依赖。`test_knowledge_mcp_bindings.py`验证单head和既有0006/0007存在，不锁死最终head名。
- `apps/runtime-service/src/runtime_service/runtime/auth.py`：VerifiedDelegation具名构造，保留context_hash、credential_id、callback_context、run_acceptance。首轮误用context_claim字段导致TypeError，已修正并回归。
- `tools/knowledge.py`：v1七字段兼容；v2明确locator DTO、严格整数/1-based/顺序/unknown-null与枚举，额外定位字段拒绝。模型正文/artifact同值；F04保留定位并缩短预览，无宿主路径/Key字段。服务版本由`runtime/mcp_config.py::knowledge_sources_version`固定，loader隐藏模型版本参数，interceptor覆盖版本并拒绝provider静默换版本。默认1，历史v2投影独立于当前请求配置。
- `workspace/attachment_receipts.py`：复用已有安全目录描述符与无符号链接读写，新增images专用目录；五字段ImageRef寻址，原名字和元数据六字段只在私有收据内，首次上传名字固定；无图片收据拒绝。Fork复制两类收据。`http/images.py`经HTTP上传生成收据，校验原名称、实际MIME及长度。
- API image HTTP/service/ports/LangGraph adapters：可选`file_name`query贯通；公开仍五字段ImageRef，回包hash/bytes/MIME/内容地址与请求匹配。
- `tools/mcp.py`：保留外部submit单一`file_ref`参数，模型schema为FileRef或ImageRef；`_file`只在拦截器经收据和原字节读取后转换图片为KnowledgeFileRef。PNG/JPEG可入库，WebP由现有安全码拒绝；生成图、伪六字段图片、篡改和跨Thread禁止。复用HMAC授权、暂存、失ACK只读回查，无新队列或原件副本。

Phase证据：Runtime相关146项、API相关19项+3subtests通过；详见[验证](../verification.md)。后续真实Worker与安全回退通过前不作Final。
