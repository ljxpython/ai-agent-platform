# 05 个人对话隔离与共享策略

## 目标

决定 Thread、Run、消息、附件、工作区、成果和分支是项目共享还是个人/协作可见，并给出平台层能否独立完成的边界。它不是把 `access_policy` 字段改名：当前 `review/workspace_write/full_access` 是执行审批模式，不是用户访问 ACL。

## 方案设计

### 5.1 当前事实

`RuntimeGatewayService` 当前通过 `metadata.project_id` 注入项目 scope，`_load_thread()` 获取 Thread 后只调用 `_assert_thread_project_scope()`；搜索、计数也只注入项目条件。当前代码未核查到创建者或参与者授权。

这意味着同一项目成员只要有 `project.runtime.read/write`，原则上可能访问项目内其他 Thread 的列表和详情，具体仍需真实 GraphHarbor 数据验证。不能仅凭前端侧栏隐藏来判断是否隔离。

### 5.2 先决定产品模型

| 模型 | 默认可见 | 可操作 | 优点 | 代价 |
|---|---|---|---|---|
| P0 项目共享 | 项目成员按权限 | 由项目权限决定 | 与现状最接近，最省改动 | 私人草稿、个人记忆、敏感输入暴露 |
| P1 个人私有 + 显式共享 | 创建者可见；受邀/共享对象可见 | owner 可删/改；共享者按动作 | 隐私清楚，默认最小权限 | 需要共享模型、列表过滤和迁移 |
| P2 项目共享 + 私有标记 | 项目共享为默认，用户可标 private | private 只对 owner/显式共享者 | 兼顾迁移与隐私 | 默认共享容易误用；权限组合更多 |
| P3 组织/项目/个人多层 | 继承组织规则并允许覆盖 | 按层级关系 | 适合大型组织 | 本期明显过度，需完整 ReBAC/ABAC 设计 |

推荐 P1：新 Thread 默认个人私有；用户显式共享后才进入项目协作范围。若当前业务强依赖同项目历史共享，再选 P2，但必须有醒目的可见性设置和默认值评审。P0 只适合作为明确的内部协作产品，而不是安全默认。

### 5.3 必须明确的字段与关系

平台层至少需要能表达：

```text
Thread: project_id, owner_subject, visibility(private/project/shared), created_by
Share: thread_id, subject_type(user/project/role), subject_id, actions(read/comment/edit/share/delete?)
Resource: thread_id 继承到 Run、消息、文件、workspace、artifact、checkpoint、fork
```

实施结论（2026-09-22）：ACL 存 Platform DB 的 `thread_access`，Runtime 不保存业务授权。上游 metadata patch 缺少并发版本保障，不适合作为共享撤销的权威来源；查询使用平台计算的授权 IDs。以下为原方案分析背景：

- 若 GraphHarbor 支持按 metadata 过滤并保留字段，Platform 可以在网关注入 owner/visibility、查询时传过滤条件，再对单条资源做二次校验。
- 若上游只支持 project 条件，Platform 无法安全实现个人列表隔离；需要 Platform 自己维护 Thread ACL 索引，或扩展 Runtime/GraphHarbor 契约。用户已限定本专项不改 Runtime Server，因此这类证据应把 P1 标为 blocked/deferred，而不是伪装成平台单层改动。
- 不能把 owner 放在浏览器请求体里作为信任值；由认证主体在 Platform API 生成和覆盖。

### 5.4 访问矩阵示例（P1）

| 主体 | 私有 Thread | 显式共享 Thread | 项目其他成员 Thread | 项目管理员接管 |
|---|---|---|---|---|
| owner | 读、写、删、分享 | 读、写、删、撤销分享 | — | — |
| 被分享读者 | 读 | 读 | — | — |
| 被分享编辑者 | 读、按授予动作写 | 读、按授予动作写 | — | — |
| 普通项目成员 | — | 仅显式共享 | — | — |
| project_admin | 默认不读私有 | 项目策略允许的管理 | 默认不读 | 满足 D18 条件时显式 takeover，并审计 |
| platform_super_admin | 默认不读 | 同上 | 默认不读 | 满足 D18 条件时显式 takeover，并审计 |
| service account | 按 grant 与显式对象关系 | 按 grant | — | 不允许隐式接管 |

“项目管理员能看全部项目对话”是合法产品选择，但必须明示为 break-glass/接管动作、要求原因并记录审计；不能因为角色名称带 admin 就偷偷绕过私有数据边界。

#### 删除、审批与私有内容读取的区别

D08 已确认 Thread 所有者、项目管理者和平台管理员都可以执行删除、审批两类治理动作，但这不等于三者都能浏览私有 Thread 正文：删除按资源 ACL 和动作资格执行并写审计；审批只读取完成审批所需的 Run/请求元数据和待审批内容；读取正文、文件或个人记忆仍须走 D18 的 takeover，不得借审批动作扩大读取范围。

### 5.5 端到端影响面

一旦选择个人隔离，以下入口必须同时过滤，漏一个就是越权旁路：

1. `POST /api/langgraph/threads/search`、`/count`：列表和总数按 owner/share 条件。
2. `GET /threads/{id}`、`PATCH`、`DELETE`、`copy`：单条资源授权；复制的新 Thread owner 由当前主体生成。
3. messages、runs、state、history、stream、cancel、join：继承 Thread ACL，不能只校验 project_id。
4. images、files、workspace tree/content/preview/zip、artifacts：下载和预览统一继承 ACL。
5. terminals、Dear memory、skills 关联：分别确认是否属于 Thread 资源或独立 scope。
6. 审计 target 与导出：记录共享/撤销/接管，不泄露私有正文。
7. 前端历史侧栏、搜索、分页、深链、分叉、刷新和多标签页：服务端过滤是真相，前端只负责体验。

### 5.6 旧数据和默认策略

新 P1 不对已有 Thread 做 owner 推断或隐式迁移。上线前执行一次经评审批准的旧 Thread 清理删除，具体范围以 dry-run 统计为准；删除前保留必要备份/快照，记录执行人、数量、失败项和审计结果。清理不是把旧数据强行归入 P1，而是避免历史数据出现不明归属。

以下迁移策略仅作为被否决的备选记录，不进入本期实现：

- M1 全部视为项目共享：无隐私回溯，但不提供历史保密。
- M2 按可识别 creator 回填 owner：需要确认上游是否保存可信作者；不能猜测。
- M3 全部私有并要求重新共享：最安全但破坏协作，迁移和用户沟通最大。

推荐先做一次只读盘点：统计 Thread metadata 是否有真实创建者、是否有服务账号创建、GraphHarbor 是否支持条件查询；没有证据就不要承诺 M2。

已运行 Run 的撤权规则也要确定：新请求立即按最新 ACL；已建立 SSE 是否断开、Run 是否继续由 Runtime 状态决定。本项目限定不改 Runtime Server，平台只能阻止后续操作或调用已有 cancel；不能宣称能撤回已输出内容。

### 5.7 takeover 的允许条件

takeover 是临时、可追责的治理动作，不是管理员的常规浏览入口。仅允许安全事件调查、合规/法务要求、用户明确授权的故障排查或数据恢复、账号无法操作且业务必须完成的交接。每次 takeover 必须绑定工单或请求号，填写具体原因、目标 Thread、读取/操作范围和有效截止时间；默认只授予一次性最小动作，结束后立即失效。开始、读取、导出、修改和结束事件全部写入审计，审计正文不得记录秘密和完整私有内容。

### 5.8 讨论项

| 编号 | 问题 | 推荐起点 | 状态 |
|---|---|---|---|
| D17 | 默认 P0/P1/P2 | P1；Thread 默认个人私有，沙箱必须挂项目；若业务必须共享再 P2 | 已确认起点：P1 + 项目内个人沙箱 |
| D18 | 管理员能否读取私有 Thread | 默认否；只有安全事件、合规调查、用户明确授权的故障排查/数据恢复等必要情形，才允许显式 takeover；要求工单/请求号、具体原因、最小时间窗、最小范围和全量审计，任务完成后自动失效 | 已确认原则：默认否，例外必须可追责 |
| D19 | 共享动作粒度 | `read/comment/edit/share/delete` 分开；首期按动作存储和检查，不把 edit 隐含为 share/delete | 已确认 |
| D20 | 旧 Thread 如何归属 | 本期不做归属迁移；上线前执行一次经批准的旧 Thread 清理删除，删除范围、备份和结果留审计；不把旧数据混入新 P1 规则 | 已确认：清理删除 |
| D21 | 是否改 Runtime/GraphHarbor | 本期不改。业务 ACL、owner、share、takeover 属于 Platform API 的资源治理；Runtime/GraphHarbor 只接收既有执行协议。只有当上游无法按项目/Thread 过滤、导致平台无法证明不越权时，才将 P1 标记 blocked/deferred，不通过修改 Runtime 偷渡业务语义 | 已确认：不改，能力不足则阻塞 |
| D22 | service account 是否支持对象共享 | 首期不支持个人 Thread 对象级共享；仅允许显式项目 grant + 项目共享，服务账号不能持有个人密钥 ACL | 已确认 |

### 5.9 私人沙箱与 Thread 的关系

用户提出“每个人创建的沙箱独立、每个对话的沙箱也独立”。这需要把沙箱视为 Thread 的子资源，而不是项目共享资源：

```text
认证主体 → 私人 Thread → 独立 sandbox/workspace → Run、文件、成果、终端
```

结合现有网关以 `project_id` 为主要边界，本期推荐每个私人 Thread 仍挂在一个项目下（项目内个人隔离）。完全脱离项目的平台级个人沙箱属于另一种产品能力，必须单独定义平台额度、费用、工具和审计，不能从本节的项目 Thread 规则推导出来。

- 创建 Thread 时由 Platform API 根据认证主体生成 owner 和 sandbox 标识，客户端不能指定其他 owner 或复用别人的 sandbox。
- 一个 Thread 默认只绑定一个独立 sandbox；新 Thread 不复用旧 Thread 的文件、终端和执行状态。分叉默认创建新 sandbox，是否复制文件需单独确认。
- sandbox 的对象 ACL 继承 Thread ACL。项目成员关系只决定能否进入项目入口，不能自动读取个人 Thread 或 sandbox。
- `full_access` 是 sandbox/Thread 上的执行模式，不是对象可见性。私人 owner 可以获得该模式，但被显式共享的读者/编辑者默认不继承终端和 `full_access`。
- 文件、成果、终端、流式 Run、取消和下载都必须使用同一 Thread/sandbox 授权检查；不能只校验 `project_id`。
- 若 Runtime/GraphHarbor 不能保证独立 workspace、owner metadata 过滤或执行资源隔离，本方案在平台层不可安全闭环，标记 `blocked/deferred`，不能用前端隐藏伪造隔离。

本节与 02 D06 的关系是：D06 决定谁能选择高风险执行模式，本节决定该模式作用在哪个独立对象上；两者不能合并成“executor 角色拥有 full_access”。

## 任务拆分

### Task F1：Thread 能力与上游证据盘点
- **改动内容：** 只读确认 GraphHarbor 查询过滤、metadata 保留、创建主体、历史数据与 Run 取消能力。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` → `_inject_project_metadata()`、`_load_thread()`、`search_threads()`；对应 SDK adapter 与集成测试。
- **预期结果：** 明确 P1 是否能只改平台完成；不能则记录 `blocked` 边界，不先写假 ACL。
- **验证项：** `apps/platform-api/tests/integration/test_runtime_graphharbor_http.py`、`test_runtime_gateway_workspace.py`、`test_thread_access_policy.py`；真实 HTTP metadata 查询证据。
- **状态：** `[x]` done，2026-09-22。metadata/查询契约真实验证通过；平台子资源授权真实 HTTP 和既有 Runtime scope/工作区契约 6 项通过。未修改 Runtime/GraphHarbor 代码。
- **合规检查：**
  - [x] 平台可行性与真实链路核对完成
  - [x] 验证已执行，日志见本章 Phase
  - [x] 本章任务已更新
  - [x] CONTEXT 已更新

### Task F2：个人隔离实现（条件任务）
- **改动内容：** 仅在 F1 证明平台边界可行且 D17—D22 批准后，实现 owner/share/filter/对象动作。
- **代码位置：** 网关 service、contracts/schemas、前端 chat history/thread services/pages、必要的 Platform 索引与迁移。
- **预期结果：** 所有 Thread 子资源继承一致 ACL，不能由换入口绕过。
- **验证项：** 见 07 的 F 系列安全矩阵；无上游过滤能力时不执行，状态为 deferred/blocked。
- **状态：** `[x]` done，2026-09-22：平台 ACL、共享/接管、分叉归属、引用再授权、独立管理员入口、私有子资源和 SA 项目共享已有单元/契约及专项 9 项真实链路；业务库迁移、旧会话数据库清理、重启持久化、双标签撤权及 201 条实际列表查询性能已验证。全项目 Final 与真实模型审批阻塞见 07。
- **合规检查：**
  - [x] P1 平台实现完成，未修改 Runtime/GraphHarbor 代码
  - [x] ACL、子资源、共享、接管、撤权、迁移/重启与适用性能证据已执行
  - [x] 本章任务与 Phase 状态已更新
  - [x] CONTEXT 已更新

## 验证要求与记录

### Phase 验证记录

2026-09-22 F1：`RUN_LOCAL_GOVERNANCE_CONTRACT=1 uv run python -m unittest tests.integration.test_thread_metadata_filter` → 1 test OK。通过现有签名委托访问真实本机 Runtime/GraphHarbor，创建两个专用测试 Thread，验证 metadata 保留、数组包含过滤、count 与列表一致、更新共享数组后的计数；finally 删除本次测试对象。未删除历史 Thread。测试初次 401 来自空 `allowed_model_ids` 不符合现有 Runtime 校验，修正测试委托后通过，不是上游能力阻塞。

静态补充：安装的 `langgraph_runtime_pg/ops.py` 中 `Threads.search()` 使用 JSONB contains 过滤，Platform 的 `threads_sdk_adapter.py` 支持 metadata、ids、offset/limit。F1 的查询证据已补齐；独立沙箱/记忆 scope 与 F2 对象行为仍须分别验证，不以 metadata 测试冒充整个 P1 完成。

F2 Phase 补充（2026-09-22）：43 项网关/ACL/模型引用/文件/图片/工作区定向测试通过；另 32 项分叉/运行请求/ACL 测试通过。两组存在重叠，不相加作为唯一用例数。具体命令及后续未验证修改见 [实施记录](implementation/01-platform-governance.md)。

补充 Phase 证据：2026-09-22 执行 `RUN_LOCAL_GOVERNANCE_CONTRACT=1 uv run python -m unittest tests.test_thread_acl`，9 项通过，包含真实上游列表/count/私有读取/共享撤销、接管结束和创建失败补偿；日志 `/tmp/governance-acl-real-2.log`。首轮测试夹具及清理连接错误、后续清理结果见实施记录；本次所有新建测试 Thread 已清理。这是 service→真实上游链路，不是浏览器或 HTTP 身份中间件端到端证据。

补充 Phase 证据（2026-09-22）：既有 Runtime scope/工作区契约 6 项通过（`/tmp/governance-existing-workspace-contract.log`），未修改 Runtime 代码。双标签成员撤销 1 项通过（`/tmp/governance-tabs-browser-3.log`）。管理员审批的 IAM/ACL/运行账本契约 1 项通过（`/tmp/governance-approval-contract.log`）：peer 拒绝，平台管理员可审批但不获得私有正文；上游为替身，不是实际模型审批运行。

F2 性能补验：201 条可见 Thread 的真实 Runtime 查询跨三个批次，list+count 五轮中位 371.66 ms、最大 462.55 ms；跨批次最后一页与总数一致，peer 私有对象未混入，全部测试对象清理。`/tmp/governance-runtime-list-benchmark.log`。平台工作区测试改为合理的冷启动等待后，文件/终端/Runtime 重启恢复 4 项通过（250.244 秒，`/tmp/governance-workspace-recovery.log`）；没有改 Runtime 源码。

### Final 验证记录

已完成，统一见 [07](07-implementation-and-verification.md#final-验证记录)；D17 已实现 P1。

## 状态

done：F1/F2 实现及联合 Final 完成，见 07。私人 owner 可 full_access，共享者不继承；管理员读私有内容须限时 takeover。D07 已明确本期仅项目内个人记忆及其入口治理；共享/跨项目记忆 deferred。Thread 分享与 takeover 不改变个人记忆归属。
