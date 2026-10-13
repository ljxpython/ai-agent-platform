# 实施方案

状态：本阶段非前端实施与Final验证已完成（`done`）；范围与人工批准见 [review.md](review.md)，结果见[验证](verification.md)。

## 架构与边界

平台成员上传附件 → API 的项目/Thread 权限 → Runtime workspace 原件及私有收据 → Agent root 工具审批 → Runtime 校验原字节/hash与即时授权 → RAG 受管暂存/异步入库/完整候选快照发布 → API 项目级任务/文档读取与 Runtime MCP 检索。

RAG负责解析、去重、排队、受管多模态资产、增量完整候选/CAS和恢复。平台复用既有原件网关、HMAC四用途授权、root HITL、后台任务读取，不另建解析/索引层。支持 MD/TXT/PDF/DOCX/PPTX/PNG/JPEG；图片沿用5MiB附件上限，文档20MiB；WebP聊天继续可用，知识入库按provider能力拒绝。

## 代码改动

1. `apps/runtime-service/src/runtime_service/tools/knowledge_upload.py::_identity`：允许与可信 `execution_info.task_id/checkpoint_ns` 一致的 root `tools:<task_id>`，拒绝子图/伪 namespace/read委托/Plan/offload；保留原Run及撤权检查。
2. `apps/platform-api/src/platform_api/modules/knowledge/authorization.py::authorize_operation`：局部加载 RuntimePolicyOverlayService，解除循环导入；迁移用独立head检查，保留既有身份。
3. `apps/runtime-service/src/runtime_service/tools/knowledge.py`：明确 v1/v2 DTO；v2 `locator={unit,start,end,block_type}`，1-based范围，unknown为null，拒绝布尔/逆序/额外路径字段。全部公开输出仅安全字段，8来源/800字符/12KiB和F04预算同步作用于content/artifact/history/SSE。
4. `runtime/mcp_config.py`、`tools/mcp.py`：服务端配置固定query版本并移除模型可选版本参数；默认请求v1，前端兼容后切v2。关闭v2仍保留历史v2可读。
5. `workspace/attachment_receipts.py`、`http/images.py`：原始图片名、MIME、size/hash保存在Agent挂载外的收据；沿用五字段ImageRef。`file_name`可选query传递，经API/Runtime校验；无名称采用内容寻址名。缺旧图片收据需重传，禁止伪造为FileRef。
6. `tools/knowledge_upload.py`、`tools/mcp.py`：模型工具的 `file_ref` 接受六字段文档FileRef或五字段ImageRef；图片只在interceptor经收据与原bytes校验转换为RAG六字段KnowledgeFileRef。拒绝generated/outputs、跨Thread、篡改或无收据；Fork携带私有收据。
7. `runtime/auth.py`：VerifiedDelegation具名构造，保留 credential_id/callback_context/run_acceptance，避免主线整合顺序错误。

## 上线与回退

实机新增边界：HMAC request签发时间允许固定5秒未来时钟差，仍要求exp>当前时间且exp-iat≤30秒；不对已过期请求增加宽限。Ubuntu比Mac快约0.2秒可在整秒边界触发旧平台403（15次对照中3次）。服务端返回grant仍按自身当前秒签发、30秒到期；不改变签名、IAM或原Run范围。

上传开关默认关闭；版本请求默认1。前端完成capabilities动态门禁、完整附件JSON文本、回执状态与v2定位展示后再开启正式上传/v2。关闭平台上传仅禁止新submit/upload授权，已受理start/activate保留原Run/当前IAM/签名门禁并继续，不停既有任务/检索；RAG项目uploads=off是管理员解析暂停/冻结回退操作，需先排空在途，与平台关闭新提交区分。关闭v2请求不删除历史。新1024维多模态RAG库与旧768维库隔离，禁止混写。正式主工作区合并须保留 Token/后台迁移并对并列heads做显式merge，不能删revision；本worktree现有head无需新迁移。

## 验证

安全、历史/预算、上传网关、真实root审批/撤权及迁移回归由本轮完成。Mac无Docling锁定Torch轮子，真实复杂文档解析在Ubuntu执行；本地专属PG/Redis与local Runtime Worker优先，必要时使用独立Ubuntu测试栈。真实模型用miaomiaoai DeepSeek；embedding沿用新RAG1024配置。失败先保留诊断，不以fixture替代实际Worker验收。

前端只交付文档/fixture；音视频、生产压测/业务问答质量、现役部署不在本阶段范围。
