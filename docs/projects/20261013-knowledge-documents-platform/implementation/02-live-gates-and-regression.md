# 真实联验、授权边界和迁移回归

2026-10-13；T05/T06。本worktree原生PostgreSQL/Redis、local Runtime API/Worker，与Ubuntu独立1024维RAG库通过所属SSH通道连接。RAG源码仍main c30e2149，与同事2bd5818功能代码一致，本轮没有修改RAG仓库。

- `apps/platform-api/src/platform_api/modules/knowledge/authorization.py::parse_operation`：固定允许5秒未来iat时钟差，exp必须尚未到期且exp-iat在1..30秒，不给过期宽限。旧实现遇Ubuntu快Mac约0.2秒会在整秒边界拒绝合法start请求（15次对照3次403），PNG first attempt失败且零入库模型usage；修复后重试ready。新增5秒边界、6秒拒绝、过期、长lease测试。
- 同一函数将新增写开关仅作用于upload，已受理任务start/activate继续走签名、原Run、当前IAM、主体凭据及deny校验。旧实现关闭写时阻断全部mutation，不符合批准的“关闭新上传保留已受理任务”。单测先覆盖关闭/撤权；真实暂停builder后关闭两app新上传开关，alpha parsing和beta queued任务仍ready。
- `apps/runtime-service/tests/e2e/test_knowledge_documents_platform.py`：增加显式opt-in真实六格式、成员共享、两图原生review审批、两项目排队/跨Run处理中去重、旧查询/冻结文件、Fork与API/Worker重启、Plan/撤权/跨项目、20MiB/聊天Stop、v1回退/v2历史、冻结版本回退及pending Stop。测试控制只暂停隔离RAG所属builder，由SSH stdin/watchdog释放，不暂停现役或其他环境。私有setup/ops/env留忽略目录，公开证据/fixture进专项。
- `apps/platform-api/tests/integration/test_run_acceptance_migration.py`：当前head同时含completion和acceptance分支；新增nullable origin_ref属于已有completion，保留两分支revision与三张completion表。回退至旧0006仍安全拒绝，旧行/精确acceptance回执保持；SQLite可能已提交no-op merge退回，重新upgrade恢复head不重写事实。数据库URL按Alembic百分号规范转义，PostgreSQL用本worktree一次性测试schema，绝不降级运行库。
- `apps/runtime-service/tests/background/test_repository.py::test_receipt_preserving_migration_round_trip`：保留token_budget/background两历史revision，upgrade后核对真实唯一head，不写死旧0003；随机测试schema迁移往返中原后台receipt仍可重放。真实PG21 passed/5 Docker专项skipped，跳过不作通过。
- `apps/platform-api/tests/test_run_acceptance.py::setup`：补旧测试桩planning read所需Thread ID/state，read委托不更新run-create快照，默认operation按既有run-create处理。Final首轮23失败仅来自测试桩，32项独立复验及API全组223+182subtests通过。
- `apps/platform-api/tests/test_run_completion.py::fixture`：显式`RUN_COMPLETION_TEST_DATABASE_URL`支持本机wt_*_platform且角色同名，保留旧一次性库护栏；每项创建/回收随机schema。全组真实PG运行，8并发callback/dispatch CAS已执行，不因硬编码旧数据库跳过。
- 收尾旧query：旧768 Ollama配置遗漏`EMBEDDING_PROVIDER`，源码`.env`新openai字段被默认加载，`/embeddings`404。仅修本worktree私有knowledge.env显式`ollama`，备份保留，不改RAG源码/索引/维度；旧v1 query两来源、content/artifact同值通过。Runtime/API恢复备份，临时RAG/SSH与本worktree7服务全部停止，PG/Workspace/corpus/原件/冻结版本保留。
- 前端业务源码没有改。交接逐文件列出动态能力、ImageRef原名query/完整正文、错误/审批回执、locator、轮询/权限切换与浏览器断言，官方content块和artifact的真实样本附在fixtures。

RAG119项已在Ubuntu重新执行，含实际supervisor SIGKILL/stdin-watchdog恢复、候选失败/撤权/CAS/腐坏快照与旧reader lease。此类受控故障测试不等同生产崩溃/容量保证。真实RAG进程重启及平台检索/receipt有另份证据。

首轮诊断保留：错误access_policy配置400、tool content数组解码错误、Fork末端历史使模型没有重复submit、跨项目route/header不一致实际400而非测试预设403、两个共享测试同时重启同栈产生临时502、pending Stop无运行实际no_active_run而非confirmed。修正测试输入/顺序/契约后复验，不修改安全边界凑通过；跨机iat与关闭写阻断在途任务是业务实现修复。

最终结果与跳过边界见[verification Final](../verification.md#final-验证记录)。本专项没有新增跨服务draft标准；JWT/SSE保留各原专项门禁，不因知识非前端done自动毕业。
