# 标题安全边界与同一受管生成器

实施日期：2026-10-09。关联 T01-T03、T05；用户已批准 R1-R5，不实施前端、不发布包、不提交 Git。

## 改动与位置

- `apps/platform-api/src/platform_api/core/security/tokens.py`、Runtime `runtime/auth.py`、API `tests/fixtures/runtime_delegation_verifier.py`：两端接受精确 `title-generate`，要求 Thread/Graph 绑定；不扩大原生资源允许集合。
- API `modules/runtime_gateway/application/thread_titles.py`：严格有界 manual/auto 请求、固定生成结果枚举、已提交根图材料选择、内部 seed 和公开 pending 投影。auto 即使提交 `messages:null` 也拒绝。
- API `application/service.py::summarize_thread_title()`：comment+edit、独立 read/title-generate/thread-edit、沿现有默认模型/reference，生成后再查权限、模型、开关与首轮材料；CAS 比较初始 title 和 seed，409 回读，未知写入 503 对账。
- Runtime `services/thread_titles.py::generate_thread_title()`：同一受管 connection/resolver/build_model，一次直接 ainvoke、max_retries=0、非流式、8s 总 deadline；取消和权限失败不降级。
- Runtime `utils/title_summarizer.py`：去除独立 dotenv/proxy 和微型 Agent wrapper；保留已有 10 字清洗。仅 user/assistant 正文，无 reasoning/tool/reminder/URL/base64/宿主路径；callbacks 为空、nostream、禁用 LangSmith 资料追踪。
- Runtime `http/title_summary.py`：mandatory Bearer、当前 comment+edit ACL、tenant/project/thread/graph/hash 与严格内部 schema；响应只有固定机器态。
- 附件只读当前 scoped workspace，复用 `validate_file_ref()` 与 `DocumentWorkspace.read()` 校验 hash/mime/size；无文字单附件本地 filename、多附件数量，未知归属 skipped，不调用模型。

## 兼容与限制

现有 manual `{}` / `{messages:[...]}`、人工 PATCH title/preview 保留。manual AI 现在要求 comment+edit，人工改名仍沿 edit。preview-only 不清 seed，同名改名也清 seed。

附件原 filename 未独立持久化，沿已提交引用且清洗有界；仅保证当前 Thread 文件归属和内容完整性，不能声称 filename 不可伪造。未增加 PII 治理或辅助调用 Usage 账本。

## 验证

API 定向 38 项通过（337.445s，含跨环境委托、route matrix、model reference、auto、manual 与 fork）。Runtime 首轮 16 项通过，新增附件服务用例及修复后服务 5 项通过（24.37s）。更完整证据、既有失败与真实 HTTP/模型结果持续写 `verification.md`，此记录不代表全项目完成。
