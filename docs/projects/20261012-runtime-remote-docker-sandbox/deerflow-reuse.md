# deer-flow 沙箱能力与代码复用评估

> 评估日期：2026-10-12；实施复核：2026-10-13。用户要求本专项补齐相关沙箱能力，适合直接使用的代码优先复制。两个独立模块已原样复制并接入 Node 生命周期锁、输出路径映射，MIT / PROVENANCE / 源 hash 与契约测试已接入；能力验收以 tasks.md / verification.md 为准。

## 源码基线与许可证

参考仓库为用户指定的本地 deer-flow checkout，路径用 `<research>/deer-flow` 表示。固定 HEAD 为 `cc664451f03140b376611f329ae400c313530bdb`；本次核对的 `sandbox/`、`community/aio_sandbox/`、`community/opensandbox/` 和 `docker/provisioner/` 没有未提交代码修改，`config.example.yaml` 有已暂存修改，只作为当前配置示例参考。

本表中的 Harness 源码路径均以 `backend/packages/harness/deerflow/` 为根；上游测试路径以 `backend/tests/` 为根。参考项目根 `LICENSE` 为 MIT，包含 `2025 Bytedance Ltd. and/or its affiliates` 与 `2025-2026 DeerFlow Authors` 版权声明，允许复制、修改与分发，要求保留版权和许可文本。实施复制时还需核对所选文件的独立声明；容器镜像、SDK 和嵌套依赖不因这份根 MIT 许可证而自动完成许可核对。

Runtime 要求 Python `>=3.13`，参考 Harness 要求 `>=3.12`；候选中的 PEP 695 泛型语法可在本项目版本使用。直接复用只选独立标准库模块，不为复制代码引入 `deerflow-harness`、`agent-sandbox` 或 `opensandbox` 依赖。

已采集的来源校验值如下；实施复制时再次核对，源文件变化须重新评估。

| 文件（相对参考仓库根） | SHA256 |
| --- | --- |
| `LICENSE` | `b23dff4d4bac8d17b6efaaa7e88c2b730149c4dda45699ce676b719cfdffe7e1` |
| `backend/packages/harness/deerflow/sandbox/acquire_serialization.py` | `8cfed7b1aa098be5bb376f459247f1d92636606ba45a9902d9d186570147f9d2` |
| `backend/packages/harness/deerflow/sandbox/path_patterns.py` | `09925243e0ef0ccf6380840f4ef55aa6b3f201ccf0989f818e2da6c0b16ec3fa` |
| `backend/tests/test_acquire_serialization.py` | `01c430d8192d28f796b597bc2f9aabd56d5b539b06305f1ca8e1b74459bb29c7` |
| `backend/tests/test_sandbox_path_patterns.py` | `4984a4c728ad6e247d909d2d2a19e1bd69093dde5fd92860dd92f1b6df15e88d` |

## deer-flow 实际拓扑

| 模式 | 控制面 | 命令 / 文件数据面 | 限制 |
| --- | --- | --- | --- |
| 本地 AIO | `AioSandboxProvider → LocalContainerBackend → Docker` | Gateway 通过 AIO Sandbox HTTP SDK 访问容器服务 | 每个沙箱有 HTTP 服务和端口；与本项目临时命令容器不同 |
| K8s AIO | `RemoteSandboxBackend → Provisioner REST → Kubernetes Pod / Service` | Gateway 使用 Provisioner 返回的 NodePort / Service DNS **直接访问 Pod** | Provisioner 不代理所有文件 / 命令；不能把它描述成一个公网入口已覆盖全部业务 |
| OpenSandbox | `OpenSandboxProvider → OpenSandbox SDK / 服务` | execd / filesystem API；`use_server_proxy` 可用于只连得上管理服务的场景 | 需要外部服务与可选 SDK；本地适配器尚无跨进程发现 / ownership |

K8s Provisioner 的用户数据使用 hostPath 或 PVC。`AioSandboxProvider.uses_thread_data_mounts` 默认只有本地 backend 为 true；remote 默认 false，可以在已确认共享存储时显式 true。上传层在非共享模式调用远端同步。本项目选择 **Node 持久目录 + 远端文件 API**，不复制双写 / 双向同步，也不要求每个沙箱开放公网端口。

本期目标拓扑仍是 `Runtime → 单个 HTTPS Sandbox Node → 本机 Docker`。Node 统一处理创建、命令、文件、终端和回收；浏览器沿用 Platform API / Runtime 网关，不访问 Node 或容器端口。

## 本次能力补齐清单

“全部补齐”按当前三模式和单节点边界定义。每项必须有本项目的实现与验收证据；deer-flow 的同名接口只作为参考。

| 编号 | 能力与上游证据 | 本项目处理 | 任务 / 验收 | 实施与当前验收 |
| --- | --- | --- | --- | --- |
| C01 | Provider / Backend 分层：`sandbox/sandbox_provider.py`、`community/aio_sandbox/backend.py` | 复用 DeepAgents 现有协议与本地分支；增加共享远端客户端和独立 Node，不更换整个 Agent Harness | T02–T05；U01、U07、I01–I05 | done：三模式 86 项基线与三模式真实模型浏览器、两图公网平台完整链；平台业务代码保持现有契约 |
| C02 | 稳定 ID 与 canonical acquire：`sandbox/identity.py`、`AioSandboxProvider` | 延用现有 tenant / project / thread 的完整 `thread_scope_hash()`，加执行域 / graph / node 绑定；不复制仅 user / thread 的 16 位 token 算法 | T04；U04、I04、I10 | done：PG 唯一绑定/冲突与原 ID 恢复；两个实际 Worktree/caller 公网隔离通过；整机正式 I10 另等维护窗口 |
| C03 | 按 key 串行 acquire / release：`sandbox/acquire_serialization.py` | 优先直接复制标准库 `AcquireSerializer` 及其独立契约测试，在 Node 准备、文件变更、fork / 清理和资源状态转换接入 | T00、T03、T05、T10；U12、I14 | done：原样迁入接线、60 项同 key/不同 key/取消/drain；公网双 task + 上传/原 ID Stop 通过 |
| C04 | 并发使用者租约：`sandbox/lease.py`；跨实例 owner：`community/aio_sandbox/ownership/` | 复用 Runtime DB 绑定 / 后台 lease / fence；Node 单进程集中登记活动资源、短事务和删除互斥，避免子 Agent / 上传仍在使用时回收；不新建 Redis ownership | T04、T07–T11；U05、U10–U12、I09、I14 | done：PG lease/fence 与 TLS 生命周期；公网 Worker 四终态/固定回执/完成续接/Stop、共享文件并发通过 |
| C05 | 取消后的迟到操作收尾：`run_sync_lifecycle_operation()`、AIO acquire serializer | 复用现有有界 `_shielded()` / cleanup、Stop 资源报告和 operation 登记；补反复取消、迟到创建、关闭时有请求的测试 | T03、T07、T08、T10；U08、U12、I12、I14 | done：取消/迟到/有界关闭/Node 崩溃契约；公网响应丢失原 ID 恢复、副作用一次与前台 Stop confirmed |
| C06 | readiness 与启动发现：`wait_for_sandbox_ready()`、`discover()`、`list_running()`、orphan reconciliation | Node readiness 核验协议 / 身份 / 持久记录 / Docker / 镜像 / 磁盘；启动先只读对账，再开放新资源；查询不能顺带创建或删除 | T03、T10；U13、I03、I12、I15 | done：真实公网 readiness、Node 服务重启后的对账/原操作/文件保留，12 次健康采样及依赖拒绝边界通过 |
| C07 | 发现后检查兼容策略：`SandboxInfo.requires_replacement`、`LocalContainerBackend` 检查镜像 / mount / network | 对账受管 ID、所有权、镜像 digest、挂载、UID / GID、network / 权限和限额；不符合策略的资源拒绝接管，不悄悄扩权或重跑 | T03、T10；U13、I15、S03、S08 | done：存量八类反例/真实 execute/PTY 10 项；公网 Node 重启只读恢复，未向共享 daemon 注入破坏性故障 |
| C08 | 完整远端文件 API：AIO / OpenSandbox `read_file`、`write_file`、`download_file`、glob / grep | 复用本项目安全文件处理与 DeepAgents 返回类型；二进制上传下载、原子写入、节点锁内 edit、tree / search 有界；所有工具走同一绑定 | T05–T06；U06–U07、U14、I05–I06 | done：101 项文件链（2 skipped 不计通过）、公网二进制/Office/图片/HTML/ZIP/skills、两图浏览器下载 hash |
| C09 | 区分不存在、空结果、搜索失败与截断：`remote_list_dir.py`、`remote_search.py`、`read_file_contract.py` | Node 返回结构化状态；文件 404 不触发新建沙箱。移植上游反例测试思路，保持本项目外部 DTO / 文本，不照搬 shell 标记或上游默认限额 | T05–T06；U14、I16、S04 | done：missing/空/partial/精确 limit/截断/edit 反例；公网文件和浏览器预览，文件缺失不补空目录 |
| C10 | 读写 / 替换互斥：`file_operation_lock.py` 与 `tools.py` 的 read-before-write | 在 Node 可信 workspace / path 键下锁内完成检查、edit 与原子发布；HTTP 重试沿用同 operation ID；保留既有工具写权限，不引入新用户工具 schema | T05；U06、U12、I14 | done：serializer/edit 竞态/原子发布与本期真实并发；公网双 task/上传、fork/宽限清理保护 |
| C11 | 宿主路径映射：`sandbox/path_patterns.py` | 优先直接复制独立路径输出匹配模块及纯函数契约测试，映射到 `/workspace` / `/skills`；不把输出替换当成路径授权 | T00、T05–T07；U15、S04、S07 | done：原样路径匹配、真实 TLS/公网输出安全投影和两图浏览器，源/许可/安装逐字节一致 |
| C12 | 不继承秘密与按次注入：`env_policy.py`、AIO `bash.exec(env=...)` | 本项目已使用最小 local env 与固定 Docker env，继续保持；Node TLS / token / DB / 模型凭据不进入容器，不复制过滤后继承整份宿主环境的做法 | T05、T07、T08；U15、S07 | done：最小 env/真实 TLS/public timeout/no-secrets；Node/caller/TLS/模型秘密不进沙箱；媒体供应商留 Runtime |
| C13 | 命令 scope 与失效 shell fencing：AIO `execute_command_in_scope()`、`release_command_scope()` | 普通命令保持每次临时容器；PTY 复用现有终端 ID、sequence、offset、instance 与关闭语义。失效终端不重放输入、不按旧 ID 重建 | T07–T08；U08–U09、I08、I12 | done：公网两图受认证 PTY，输入去重/replay/resize/close/旧实例拒绝；不重放旧 ID |
| C14 | 连接池、超时、关闭和代理选择：AIO backend / sandbox、OpenSandbox 独立 transport | Runtime / Node 使用现有 HTTP 库，复用连接、明确 timeout / 上限、禁用系统代理与自动重定向 / 副作用重试；shutdown 关闭连接与线程资源 | T02–T03；U03、U12、I03、I14、S01 | done：连接复用/关闭/config 26 项；公网 mTLS/IP/SAN/token/协议信任矩阵与 Node 重连 |
| C15 | idle timeout / lifetime / warm pool：`warm_pool_lifecycle.py`、AIO / OpenSandbox provider | 落实当前命令 / 终端 / 后台 deadline 与闲置终端回收；全节点 **2 槽硬准入**。不复制允许超过 replicas 的软上限、不引入暖容器池 | T07–T10；U08–U10、I08–I09、P01 | done：真实 idle/lifetime/硬 2 槽；公网 2 PTY + 16 read、第三 429、结束 active 0；不建设预热池 |
| C16 | destroy 与数据存储分离：Provisioner Pod / Service 销毁、hostPath / PVC | 容器删除与持久 workspace 分离，日志 / 回执先确认；保留 Thread 不因 idle 删除；同会话原目录恢复，purged / missing 不伪造空目录；单盘损坏容灾后置 | T09–T11；U10–U11、I10、I13、E06、R04 | done（持久文件/进程边界）：精确 retained/grace/unknown/apply/purged、同 Thread 公网文件/checkpoint/hash/回执/浏览器恢复；正式整机 I10 按用户决定 deferred（F01） |
| C17 | 网络隔离 / 出网策略：AIO `network_proxy.py` | 本期保持 network=none，网络与供应商工具继续在 Runtime 受管调用；不复制 open 默认网络、动态批准 / deny UI 和凭据 broker | T03、T07；S03、S07–S08 | done：固定 network=none/无 publish/socket/秘密和权限策略验证；公网 Docker TCP 不可用 |
| C18 | 审计与资源可查：Provisioner CRUD、AIO ownership / reconciliation | 复用 Runtime 诊断，Node 提供受认证、有界的资源 / 准入 / 清理状态和日志；只暴露安全投影，不新增平台节点管理页 | T03、T10、T13；I12、I15、S02、S04 | done：受认证资源/安全投影/真实 Worker 与 Stop，公网浏览器原 accepted Run/日志、容量 429 与真实撤权六入口 403 |

C01–C18 为本期沙箱实现/适配与证据结论。2026-10-13 用户本期验收通过，专项 done；I10 正式整机部分/后续独立 Final 和图片相关问题转 [F01–F04 deferred](follow-ups.md)。wawapii 真实生成已通过远端落盘/认证下载 hash，真实编辑两次 unknown，保全原回执且不再购买。受控供应商生成/编辑适配与旧供应商历史 unknown 单列，不替代真实编辑成功。详细证据边界见 verification.md。

## 可以直接复制的部分

优先级是：项目已有实现 → 独立上游模块 → 必要适配。复制必须用于真实调用链；不提前堆放未使用的 vendor 代码。

| 源码 | 实际落点与调用位置 | 可复用程度 | 连同处理的测试与边界 |
| --- | --- | --- | --- |
| `sandbox/acquire_serialization.py`，219 行 | `apps/runtime-service/src/runtime_service/workspace/acquire_serialization.py`；Node workspace / resource 生命周期互斥 | 模块只有标准库依赖，可保留核心代码；默认线程池按节点实际并发显式配置，只有一个 Node 进程 | `test_acquire_serialization.py` 的同 key 互斥、不同 key 并行、锁表回收、取消前后 / 多次取消、close / executor 关闭与 ContextVar 传播；改 import 到 Runtime；上游 trace-context 用例用 Runtime / 标准库 ContextVar 替代 |
| `sandbox/path_patterns.py`，153 行 | `apps/runtime-service/src/runtime_service/workspace/path_patterns.py`；节点输出与 Runtime 安全投影 | 独立标准库模块，可保留核心代码、无上游包依赖 | `test_sandbox_path_patterns.py` 的纯 helper 部分：相似路径前缀不误替换、根路径结尾、标点 / 冒号列表、不同分隔符和动态路径无缓存；涉及上游 LocalSandbox / tools 的装配用例改为本项目调用方测试 |

两个模块已在 T00 固定 SHA256、来源与许可，并在 T03 / T05 的调用处接入及验证；测试导入路径变更是必要适配，不意味着整个上游测试文件可不改即跑。

## 借鉴语义、复用本项目的部分

| 上游文件 | 不整包复制的原因 | 本项目接法 |
| --- | --- | --- |
| `sandbox/identity.py` | user / thread 的 16 十六进制 token 与本项目多租户 scope 哈希不同；替换会让旧工作区失联 | 保留现有完整哈希、 graph / execution host 隔离；补 canonical binding 测试 |
| `sandbox/remote_search.py`、`remote_list_dir.py`、`search.py` | 面向容器 shell / SDK 的文本状态协议，Node 目标实现可复用本机安全文件操作；硬搬会增加 shell 跳转和第二套过滤规则 | 复用 native 文件逻辑，移植 missing / 127 / partial / truncation 反例语义；不引入 `find \| head` 掩盖失败 |
| `sandbox/env_policy.py` | 过滤后仍继承宿主大部分 env；比本项目白名单环境更宽 | 保留本项目最小环境；复用泄密反例测试，核验 SSH agent、PG / Redis URL、TLS key、Node token 不可见 |
| `sandbox/file_operation_lock.py` | 带上游 `Sandbox` import，且仅进程锁，不具备跨 API / Worker 的持久所有权 | 统一在 Node 接入已复制 serializer 与可信 workspace / path 键；保留 DB / operation / fence 的职责 |
| `sandbox/lease.py`，720 行 | 与上游 Provider、run context、warm pool 生命周期绑定；其等待同步操作完成的逻辑不能替代本项目有界取消 | 复用本项目有界清理、resource ledger 和后台 lease / fence，补 sibling 活动与反复取消的测试 |
| `sandbox/sandbox.py`、`sandbox_provider.py`、`middleware.py`、`tools.py` | 返回字符串、路径 `/mnt/user-data`、配置 / 鉴权 / State / HITL 与本项目不同 | 保留 DeepAgents 协议、`/workspace`、审批 / tool policy / delegation 与 checkpoint 边界；只适配内部 transport |
| `community/aio_sandbox/backend.py`、`sandbox_info.py` | Provisioner 模型与 daemon 资源登记不同；活着不代表工作区完整 | 借鉴 create / inspect / destroy / discover / list 接口职责，使用本项目 DTO、持久记录和安全错误 |

## 本期明确不整包引入的实现

| 实现 | 原因与后续条件 |
| --- | --- |
| AIO provider / local backend / AIO SDK | Provider 约 2,700 行、本地 backend 约 2,000 行，依赖上游配置、用户、skills、端口与 AIO 常驻服务；不是一个可直接替换的远程 Docker 客户端 |
| `docker/provisioner/app.py` | 调用 Kubernetes 创建 Pod / Service、使用 NodePort / DNS 与 hostPath / PVC；不能直接管理 sshmy2 的 Docker。以后选择 K8s 时重新评估 |
| OpenSandbox provider / SDK | SDK 和服务可作为未来节点引擎，但当前适配器是进程内 warm pool、未实现跨进程 discovery / ownership；还要重新接入本项目 reader、PTY、回执和持久 workspace。不会仅靠复制解决当前全部需求 |
| Redis sandbox ownership | 本期只有一个 Node 进程负责资源创建 / 回收，Runtime 已有后台 DB lease / fence；只有增加多个 Node 管理进程或直接多 Gateway 管 Docker 时再选协调机制 |
| warm pool / soft replicas | 本期节点约 3.6 GiB，普通命令按现有 `--rm` 回收。上游记录日志后允许超软上限的行为不适合本项目硬容量准入；只有冷启动实测成为瓶颈时再独立设计同作用域预热 |
| 动态网络审批、egress proxy、Lark broker | 会改变 network=none 的信任边界，并可能要求平台交互 / 新权限；当前不需要。外部网络工具仍在 Runtime 受管执行 |
| VM / browser / VNC、其他云沙箱供应商 | 超出单节点 Docker 专项，且要求新增镜像 / 运行时 / 公开能力；不因为上游存在就迁入 |

## 来源记录与验收方式

T00 已建立 `apps/runtime-service/src/runtime_service/workspace/third_party/deerflow/`，仅存完整 `LICENSE` 和 `PROVENANCE.md`；实现模块放在实际 workspace 调用层，不建新的通用 vendor 框架。已记录上游提交、原文件、源 SHA256、目标文件、目标 SHA256、改动原因和迁入测试，版权提示引用完整许可文本。wheel 与本地/sshmy2 v2 镜像已核验这两份记录随产物分发，证据见交付产物记录。

复制后分别验证独立模块契约和实际 Runtime / Node 调用链，不能用上游测试存在代替本项目运行证据。上游 pytest 文件依赖其 conftest / Harness 的部分只提取相关测试；本项目 T13 还需三模式回归、真实公网、主 / 子 Agent 并行、上传与回收竞态、Stop / 重启与文件 hash 核对。

能力矩阵中 C01–C18 全部有任务与验收归属；`tasks.md` 记录进度，`verification.md` 分开记录评估、Phase 与本期用户验收收口。G00/G01 已于 2026-10-12 获用户批准，2026-10-13 G06 用户本期验收通过并授权 Git 交付/精确清理；T00–T15 本期收口，B01/B02 解除。原正式 I10 整机部分与后续独立 Final 未执行、转 deferred，不以复用矩阵冒充这些测试通过。
