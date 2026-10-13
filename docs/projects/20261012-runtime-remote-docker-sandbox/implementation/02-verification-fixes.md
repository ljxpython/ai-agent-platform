# 真实验证中的修复与接线

2026-10-13；用户已批准T00–T15，T00–T11 已实施并完成阶段验证；T12–T15 受公网 B01、本地浏览器 B02 阻塞，验收状态见 tasks.md。

- `workspace/node_client.py`：仅可信前置拒绝认定未启动；响应丢失只查原ID，回查拒绝不证明原命令未启动；operation/discover/ready设置5秒读等待。
- `run_control/resources.py`、`run_control/service.py`与迁移0007/0008：提交前登记原node/operation/scope，Worker恢复与Stop按原绑定只读回查/取消，无命令重放；一次处理最老2条并刷新尝试时间。
- `workspace/background.py`：Docker控制并发8槽，按事件循环隔离并及时回收；旧16并发Docker验证通过。前置拒绝存failed/not_required并抑制完成通知，用户文案改为未启动任务。
- 迁移0006–0008拒绝数据库downgrade；回退应用保留head及迁移链，测试不再stamp绕过。
- `tools/documents.py`：remote通过Node检查准备状态，移除本机Path假设；真实Node Office与续读通过。旧本机p5缺reader，使用所属Worktree新镜像验证，不替换共享旧镜像。
- `sandbox_node/storage.py`：descriptor读取区分missing/permission/path/limit；search精确limit与部分失败分开；download_files保留二进制与既有错误类型。
- `sandbox_node/ledger.py`与protocol：跨scope取消不能持久污染原资源；后台resource ID必须等于提交operation ID。
- `sandbox_node/engine.py`：Showcase的固定Office reader也尊重protected只读根挂载。
- `sandbox_node/terminal.py`：真实容器Running确认后返回PTY，启动失败有界清理容量；close与resize职责恢复。
- `scripts/sandbox_node_certificates.py`：离线原CA签发90天叶证书/新token，轮换输出不含CA私钥。NodeConnection隐藏token的repr，避免测试/异常诊断泄漏。
- `apps/platform-web/e2e/runtime-sandbox.spec.ts`：仅新增验收脚本，平台产品代码不改；真实模型上传/execute/read/present、浏览器预览下载与重开记录所属项目证据。

- `sandbox_node/engine.py:reconcile()`：后台 Created 资源未 start 时保留 reserved 容量，避免扫描误判 Exited 后晚启动被拒或第三请求超槽。`service.py` 的管理锁移到生命周期 try 中，第二管理者抢锁失败也关闭 executor、serializer 和文件。
- `workspace/remote_backend.py:RemoteSkillsBackend._read()`：第一次发布技能前幂等 prepare，补齐 Showcase 默认 SkillsMiddleware 先于自定义 workspace middleware 的调用顺序；Node 对 purged / missing 仍拒绝恢复空目录。
- `tests/workspace/test_node_tls.py`：随机独占 Node ID、精确资源 teardown、真实 PG 生命周期与备份/轮换、两图主子技能、10 MiB 与混合 readiness；复用现有 API / Worker fixture 补后台续接/Stop，不新建生产 Harness。
- `tests/services/dearflow_agent/test_tool_error_platform.py`：remote fixture 保留 TLS 注册的 execution host，独占 schema / 数据库迁移冷启动给定期限；非 remote 仍派生独立执行域。`tests/fixtures/run_reliability.py` 的保留文件探针适配远端文件 API，去除测试夹具的本机 Path 假设。
- `deploy/Dockerfile.agent-workspace`：镜像附完整 deer-flow MIT 与 PROVENANCE；Python wheel 同样带来源、固定源 hash 与许可证。两个原样上游模块不格式化。
- sshmy2 正式 systemd 单管理进程 TimeoutStop 180 秒；服务器独占短期 TLS fixture 对真实 execute / PTY / background / reader / fork 与停机后 SQLite + workspace 备份还原通过。正式客户端私钥和 CA 私钥留在 Runtime 信任域。

公网19111目前不能从本机Runtime完成TLS握手（B01）。运维SSH与服务器本机Node测试不代替公网业务证据；本地浏览器提交/审批回查多轮失败为 B02，不能以契约测试替代完整链路。

## 2026-10-13：终端镜像配置与真实应用回退

`sandbox_node/terminal.py:NodeTerminals.create_session()` 原来固定 DearFlow p5 镜像，使配置 v2 的受管节点拒绝远端终端。现在 `workspace/terminal.py:TerminalManager.create()` 与本地终端一样读取 `RUNTIME_WORKSPACE_IMAGE` / `RUNTIME_SHOWCASE_IMAGE`，受限协议 `protocol.py:ARGUMENTS` 允许可选 image，Node 仍通过 `Engine.reserve()` 检查镜像 allowlist；缺省值保留旧调用兼容。平台 DTO 和页面不变。

`tests/workspace/test_node_tls.py:test_real_node_terminal_input_replay_resize_and_close()` 用当前 reader 镜像并核对真实 Docker `.Image`，仍检查输入去重 / 回放 / resize / close；`test_sandbox_node.py:test_terminal_rejects_unapproved_image_before_docker()` 验证非法镜像在准入前被拒且没有资源或会话。服务器 fixture 改为显式 v2，wheel 已重新构建，hash 以 delivery-artifacts.json 为准。

`tests/e2e/test_background_tasks.py:test_disabled_drain_preserves_receipts_and_matching_source_rollback()` 在独占原生 PG / Redis 通过，旧源码携当前迁移链正常执行，0008 head 与历史回执保持；证据写入 evidence/rollback-drain.json，T04 已验收。

## 2026-10-13：TLS 客户端复用与信任边界

`workspace/target.py:NodeConnection.load()` 每次先校验私有文件并计算内容指纹，最多缓存 4 组 SSLContext；同路径更换证书内容会生成新 context。`workspace/node_client.py:_transport_client()` 每线程仅保留一个、单连接的 httpx Client，目标 / context 变化或客户端关闭时重建；请求仍显式设置 5s connect 和原读时限、禁系统代理 / 重定向 / 自动重放。`close_clients()` 接 Runtime 应用 lifespan 与 atexit，用弱引用登记避免测试线程退出后登记累积。

真实 TLS 测试核对两个成功请求使用同一 network_stream、关闭后新建连接，以及证书 / token 轮换后的新连接和旧凭据拒绝；额外覆盖非受信客户端、过期客户端、错误 SAN、非受信服务端与源 IP / HTTPS 拒绝。源 IP 使用实际连接地址，伪造 X-Forwarded-For 不放宽访问。

浏览器验收只选附件不会立即上传：原实现是在发送时 `prepareMessageAttachments()` 执行上传。专项脚本在发送前等待真实模型目录和项目策略响应完成，避免可排队按钮已启用而模型列表仍在加载时触发内部 canSubmit=false；随后按原流程选附件、填草稿、回车并核对 upload 与 commands。审批按钮包含 ✓ 前缀，定位保留文本匹配。只读 Run 轮询的瞬态 502/503/504 继续等待并留痕，不重发提交。临时 composer 诊断代码与文件已移除；完整端到端状态见 verification。

`runtime-sandbox.spec.ts` 下载时对原字节计算 SHA256，与 artifacts 元数据比对。失败记录保留原始异常；fixture 清理失败单独写 `cleanup-failure.json`，不会覆盖已发生的业务断言失败，成功场景中的清理失败仍使测试失败。没有增加命令重试或放宽工具单次计数。

## 2026-10-13：存量安全策略核验收口

`sandbox_node/engine.py:Engine.inspect_facts()` 增加完整 SecurityOpt、16 MiB 的 /tmp tmpfs 与 8 MiB fsize 软硬限制核验。此前只核验存在 NNP，会允许伪造存量容器额外关闭 seccomp；现在与本项目固定创建参数一致，不接管放宽的安全策略。沿用原存量反例用例，增加 seccomp、tmpfs、fsize 三项，连同原五项、真实 TLS execute 与 PTY 共 **10 passed**。没有引入新配置或放宽隔离参数。

最新 wheel 已重新构建、hash 核对并通过服务器现有 uv 重装，sshmy2 六项 smoke 再次全通过；安装 engine 与 wheel 内容一致，正式服务 active，Docker TCP 无监听。首次使用 venv pip 失败（该 venv 未安装 pip），恢复服务后使用已有 uv 完成更新，未增加全局依赖。最新 hash 以 delivery-artifacts.json 为准；容器镜像不运行 Node 对账代码，本次无需重建 reader 镜像。

本地 Docker 浏览器两轮均在真实 parse_document 后到达 execute 审批；第一次等待 30 秒、复验等待 180 秒仍未闭环，伴随只读接口 502、模型目录/权限同步失败。两个 fixture Thread/project 均精确删除，未重复 execute。脚本进一步核对批准后的 commands HTTP 200，保留单次点击与业务断言；结果不标为通过。

最新 local 复验在 commands 提交等待 60 秒超时（1.3m），上传已完成但执行未开始。专项脚本通过 `framenavigated` 尽早记录本测试项目 Thread，避免提交失败后清理遗漏；修正仅静态验证通过，未宣称浏览器复验成功。此前因项目先软删除而 Thread DELETE 404，核实独占 Worktree/测试项目、idle 与无 Run/后台/未决资源后，精确移除此一个 Thread 和文件，绑定留 purged；证据在 `evidence/local/cleanup-status.json`。

诊断命令误输出本 Worktree 委托密钥，已轮换隔离环境两端密钥与私有基线副本，并同步重启所属 Platform API / Runtime API / Worker；秘密值不入证据。local backend 和其他配置保留，未触碰共享基础设施或其他 Worktree。
