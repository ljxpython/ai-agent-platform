# 会话与运行时生命周期任务

- [x] P01 重新规划与人工评审：2026-10-30；用户已批准 GraphHarbor/平台/Runtime 职责边界、30 天活动规则与 Workspace 无额外等待。
- [x] P02 GraphHarbor 通用生命周期实现、源码/候选验证、双包本地发布与 PyPI 冷安装验收（进度详见 GraphHarbor G02-G07）。
- [x] P03 平台活动/策略接入：新会话/存量、主动查看和发送续期、权限、前端精确触发，后台读取不续期。
- [x] P04 Runtime 生命周期钩子与 Workspace：未结事项准入、资源释放、可信立即回收、失败恢复与应用数据矩阵。
- [x] P05 平台记录保留维护：终态/受理恢复/去重保护、origin/event配套保留、有限批次与只读预览。
- [x] P06 Runtime 维护与运维：复用日志/孤儿能力、安全准入、统一维护入口、一套systemd模板与手册。
- [x] P07 三服务隔离链路验证：续期/删除/工作区/迟到回调/并发/失败恢复/鉴权/性能/回退及必要回归。
- [x] P08 最终状态一致与交付：README/plan/tasks/verification/CONTEXT、FEATURES/CHANGELOG、契约同步与经验提案。

状态：已完成（done，8/8 任务；Phase与Final核验通过）。完成日期 2026-10-30；[实现记录](implementation/01-platform-runtime-retention.md) 记录细节，进度以本文件为准。

## Task Completion Cards

### P01 人工评审与边界

- **改动内容：** 固定平台业务规则、GraphHarbor 通用 TTL、Runtime 资源责任，取消 Workspace 七天等待。
- **代码位置：** `plan.md`；本项不改源码。
- **预期结果：** 不在平台重复实现引擎 TTL，不以过期时间直接强删未结资源。
- **验证项：** 2026-10-30 用户明确批准方案和 GraphHarbor 直接发布；已核对两仓规范与隔离环境登记。
- **状态：** `[x]` 已完成 2026-10-30。
- **合规检查：**
  - [x] 方案工作完成；无代码实施项
  - [x] 验证项已执行
  - [x] tasks.md 已更新
  - CONTEXT 已同步；FEATURES/CHANGELOG 跳过（规划项）。

### P02 GraphHarbor 正式交付与锁定

- **改动内容：** 通用生命周期发布 post48；Runtime 使用正式版本及 frozen lock，同步依赖并重启所属服务。
- **代码位置：** `apps/runtime-service/pyproject.toml`、`uv.lock`；GraphHarbor G02–G07。
- **预期结果：** API/Worker 与CLI同版本，使用方不依赖未发布源码。
- **验证项：** 正式四产物hash、冷安装、13项HTTP/恢复探针通过；平台三服务读取正式包验证通过。
- **状态：** `[x]` 已完成 2026-10-30。
- **合规检查：**
  - [x] 接入实现完成
  - [x] 验证项已执行
  - [x] tasks.md 已更新
  - CONTEXT、FEATURES、CHANGELOG 已同步。

### P03 业务策略与主动活动

- **改动内容：** 新会话强制 idle43200、可信tenant；主动发送/查看续期；存量精确委托API登记，前端实际打开/返回触发。
- **代码位置：** Platform `RuntimeGatewayService.create_thread()/record_thread_activity()/_touch_thread()`、`retention.register_missing()`、`tokens.py`；Runtime `auth/platform.py`；Web `useThreadActivity.ts` 及两聊天页面。
- **预期结果：** 后台读取/自动运行/metadata不续期；存量不集中误删；跨项目或越权不能活动/改策略。
- **验证项：** ACL/fork/policy/title55 passed/3 skipped/22subtests；委托契约修复后5 passed/67subtests；Web8 passed；真实栈与浏览器续期矩阵通过。
- **状态：** `[x]` 已完成 2026-10-30。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 已更新
  - CONTEXT、FEATURES、CHANGELOG、delegation-jwt 契约已同步；该契约其他专项门禁未解除，保持draft。

### P04 生命周期与 Workspace 回收

- **改动内容：** 删除 hook 验证持久任务、未结事项保护、资源释放与host/path绑定；目录/业务payload清理后签名通知平台。
- **代码位置：** `thread_lifecycle.py` → `before_delete()/after_delete()/workspace_unused()`；`run_control/resources.py`、`workspace/locations.py`、`workspace/terminal.py`；Runtime迁移0010。
- **预期结果：** 资源确认后立即回收，失联/占用/unknown持久重试，既有创建入口共享删除屏障。
- **验证项：** Runtime生命周期15 passed，含失联恢复和本地占用；最终相关10文件119 passed/11 skipped；真实手动与TTL删除、占用重试通过。
- **状态：** `[x]` 已完成 2026-10-30。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 已更新
  - CONTEXT、FEATURES、CHANGELOG 与逐表手册已同步。

### P05 平台记录保留

- **改动内容：** 有充分终态再清30天请求快照；详情30天/去重90天，origin/event配套保留；可信删除回调清ACL并审计，迟到不复活。
- **代码位置：** `scripts/maintain_run_completions.py` → `maintain()`；`completion.accept_completion()/_accept()`；`completion_http.receive_thread_deletion()`；`thread_access.remove()`；平台迁移0010。
- **预期结果：** 保留受理恢复/幂等依据，pending/unknown/HITL不误清；默认report、有界apply/预算/互斥。
- **验证项：** completion/delegation/requests83 passed/1 skipped/110subtests；PG completion35 passed，包含迟到、签名、终态保留与并发互斥。
- **状态：** `[x]` 已完成 2026-10-30。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 已更新
  - CONTEXT、FEATURES、CHANGELOG 与数据矩阵已同步。

### P06 Runtime 维护与运维

- **改动内容：** 复用日志和资源对账、24小时删除墓碑后清终态inbox；有界只读入口、同host核实；systemd模板与故障手册。
- **代码位置：** `runtime_service/maintenance.py` → `maintain()`；`messaging/inbox.py` → `prune_deleted_threads()`；`deploy/systemd/`；`scripts/local_stack_worktree.py` 回调配对。
- **预期结果：** 只维护应用事实，默认limit100/预算30秒，不能伪造释放；模板与原生部署账户/路径一致。
- **验证项：** Runtime相关回归119 passed/11 skipped；local-stack2 passed；只读/互斥/预算/owner存活测试通过；模板静态核查，Linux启停不在本次本机范围。
- **状态：** `[x]` 已完成 2026-10-30。
- **合规检查：**
  - [x] 代码与模板实现完成
  - [x] 验证项已执行
  - [x] tasks.md 已更新
  - CONTEXT、FEATURES、CHANGELOG、[运维手册](../../runbooks/session-retention-maintenance.md) 已同步。

### P07 三服务与真实浏览器验收

- **改动内容：** 使用环境wt_5642ffa8be9a执行真实API/Worker/Web、安全并发与恢复验证。
- **代码位置：** Runtime `tests/e2e/test_session_retention_stack.py`；Web `e2e/session-retention.spec.ts`。
- **预期结果：** 关键业务链路有正式包和真实模型证据，回退限制实际验证。
- **验证项：** 三服务1 passed/13检查/57.41秒；浏览器1 passed/5检查/20.4秒；10轮维护2.892–9.084秒；正式包停维护/恢复及旧schema门禁通过。
- **状态：** `[x]` 已完成 2026-10-30。
- **合规检查：**
  - [x] 验收代码完成
  - [x] 验证项已执行
  - [x] tasks.md 已更新
  - CONTEXT 已同步；FEATURES/CHANGELOG跳过（测试项，能力由P03–P06记录）。

### P08 状态、文档与交付

- **改动内容：** 两仓任务卡/Phase逐项、实现记录、契约、发布与故障手册、功能和变更记录对齐；经验提案随交付提出，未擅写lessons。
- **代码位置：** 本项目文档；`docs/CONTEXT.md`、`FEATURES.md`、`CHANGELOG.md`；两份关联标准与运维手册。
- **预期结果：** 清楚区分本地完成、正式包发布、现役未部署及降级限制。
- **验证项：** 最终只读状态/链接/差异及产物一致性核验见Final；验收后已完成Git提交、功能分支推送、main快进合并及专属资源清理，未生产部署。
- **状态：** `[x]` 已完成 2026-10-30。
- **合规检查：**
  - [x] 文档实现完成
  - [x] 验证证据已核对
  - [x] tasks.md 已更新
  - CONTEXT、FEATURES、CHANGELOG 已同步；经验提案等待用户确认才写入。
