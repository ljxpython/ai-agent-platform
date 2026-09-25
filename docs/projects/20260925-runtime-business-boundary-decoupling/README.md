# Runtime 与 GraphHarbor 业务边界解耦：平台协作入口

## 项目概述

- **启动日期：** 2026-09-25。
- **级别：** 治理改动，跨 platform-api、runtime-service 和 GraphHarbor；含授权与历史数据迁移。
- **状态：** `partial`。平台 ACL 回查、thread 创建预留/受限 reconcile、可信 project metadata、模型与 tracing 关联已实施；GraphHarbor 已移除旧 SQL scope，公开 post33 已锁定。本机两库归档隔离恢复、单项目业务 run/SSE/HITL 和浏览器文件正向链路已有阶段证据；官方全入口、跨身份故障与回退 Final 仍未完成。
- **当前安排：** 与 GraphHarbor 的[Runtime 流事件保留治理](../../../../graphharbor/docs/projects/20260925-runtime-event-retention/README.md)联合验收；真实缺口以主方案“暂停点与恢复入口”及各专题 Final 为准。
- **主方案：** [GraphHarbor 项目概览](../../../../graphharbor/docs/projects/20260925-runtime-business-boundary-decoupling/README.md)。此跨仓库相对链接要求两仓同级检出；仓库不在同一工作区时，请在 graphharbor 仓库打开相同项目路径。
- **单一事实源：** 任务、验证和评审记录集中在 GraphHarbor 主方案；本入口不复制任务状态。

## 阅读顺序和平台责任

| 专题 | 平台改动 | 主方案 |
|---|---|---|
| 身份与授权 | 复用 delegation、runtime_gateway、thread_access；补原生资源 operation/目标验证、ACL 回调、创建与补偿顺序 | [01](../../../../graphharbor/docs/projects/20260925-runtime-business-boundary-decoupling/01-identity-and-authorization.md) |
| 模型与 trace | tokens.py 的可选 correlation 签发；复用 graph factory、模型引用兑换、Langfuse/OTel | [02](../../../../graphharbor/docs/projects/20260925-runtime-business-boundary-decoupling/02-model-and-tracing.md) |
| Workspace | 复用 workspace/deepagent.py，补安全覆盖；保留现有路径和可信 thread metadata 绑定 | [03](../../../../graphharbor/docs/projects/20260925-runtime-business-boundary-decoupling/03-workspace-and-packaging.md) |
| 迁移与联合验收 | 维护窗口清理旧运行历史、稳定幂等键、Store 客户端清点、worker 快照切换、候选 wheel 和回退 | [04](../../../../graphharbor/docs/projects/20260925-runtime-business-boundary-decoupling/04-data-migration-and-cutover.md) |

## 已确认的边界

2026-09-25 用户明确：彻底解耦，不保留旧业务兼容；候选版本联合验收后维护窗口一次切换，允许直接删除历史 GraphHarbor 运行数据，不做旧业务字段回填。该决定不授权清理未知或生产数据库；平台逐模块适配清单、鉴权层次和 ACL 定义见主方案 README。

1. tenant/project、角色、模型/工具策略、ACL 和 workspace 仍是平台业务能力。GraphHarbor 只执行应用提供的标准 Auth 与通用运行协议。
2. ACL 仍以平台数据库为权威，保留共享、审批与限时 takeover；不采用 owner-only 替代，不复制一套 ACL 数据库。
3. 现有 runtime_gateway 已承担上游调用，不新建旧计划设想的 dispatch 服务；现有 platform:SHA256(project,thread,key) 稳定幂等键继续复用。
4. with_forwarded_headers 合并 headers；x-request-id 不会因换签丢失。平台委托已支持经验证的可选 request/platform trace correlation claims，具体见 02。
5. workspace 本地实现已经存在；不搬用户文件、不改 thread_scope_hash，不恢复 interaction-data-service。

## 评审与验收

跨仓库详细计划与阶段实施进度以 GraphHarbor 主方案为准。用户已批准实施，不代表生产切换或历史数据删除已获准；阶段验收继续覆盖授权回调与平台 operation 映射、创建补偿、任务身份有效期、幂等域、Store namespace 契约及数据回退。平台 AGENTS.md 要求治理改动“方案评审（人工）→批准→实施”，批准记录写在主方案 README。

2026-09-25 阶段验证：Runtime Service Auth 43 passed；Runtime Service model/tool/observability 58 passed；workspace 定向测试 54 passed；Platform API ACL/gateway/delegation 36 passed、3 skipped、335 subtests passed。完整最终联合验收、浏览器和生产数据迁移尚未执行；各专题保留剩余检查项。

2026-09-25 候选复核：从最终 GraphHarbor wheel 安装目录加载平台三份配置，各有 65 条路由；Runtime Service 定向 164 passed，Platform API ACL/gateway 51 passed、3 skipped、335 subtests passed，Web typecheck 通过。隔离平台 API 与候选 Runtime 的真实 HTTP 链路：线程创建 200，同项目另一用户私有读取 403，分享 read/comment 后读取 200、修改 403，撤权后读取 403，所有者读取仍为 200。临时服务已停止；未触及现有平台服务和生产数据库。

Thread 委托复核补充：管理员无 takeover 删除为 403；限时 takeover 后读取 200、绑定 `thread-delete` 删除 200。浏览器治理测试的失败清理改由 owner 经平台网关执行；测试 fixture teardown 只检查是否遗留 ACL 记录，避免 ACL 服务关闭后绕过或误发 Runtime 委托。

2026-09-25 追加复核：服务账号委托签入 `credential_id`，Runtime 将其放入已签名 ACL 批量回查，平台即时核对 token 归属/有效期和项目 grant。隔离 SQLite 的 ACL/gateway 43 tests（3 skipped）通过，Runtime Auth 46 passed；Web typecheck、涉及文件 Ruff 严重错误检查及文档检查通过。隔离平台 API + 候选 Runtime + Web 的治理浏览器文件 10 passed，覆盖服务账号项目共享与即时撤权、operator Graph 目录刷新、管理员接管、子资源拒绝。过期的创建用户 E2E 已对齐当前一次提交表单；临时服务已停止，未执行文件正向操作或业务 run/HITL 联合验收。

最新诊断：现有本机 2142 数据库尚未应用 `20260925_0005`，浏览器 Thread 创建、搜索和计数均返回 500；平台日志显示缺少 `thread_access.provisioning_status`，请求未进入 Runtime。平台 API 现于启动时检查所需列，旧 schema 直接提示迁移；临时 SQLite 旧 schema 生命周期 3 项和 Alembic 空库升级/回退 1 项通过。现有 API 以 `--reload` 运行，热重启后已因旧 schema 拒绝启动；未修改该数据库。通过 `scripts/local-stack.sh start` 启动会先迁移，直接启动前须运行 `scripts/local-stack.sh migrate`。平台源码盘点未发现 GraphHarbor HTTP Store 或注入式 Store 现役调用，但目标库数据和外部消费者仍待核对。

本机 PG17 切换前只读盘点：Runtime 库当时是 `006`，有 57 Threads、324 Runs、6,196 checkpoints、434,742 events；Platform 库在 `20260922_0004`，有 57 Thread ACL、401 run requests。Store 两表均为空，但 Dear memory 3 条和 skills 2 个必须保留；完整计数、备份空间风险与联合清理顺序见主方案 04。旧数据会触发 GraphHarbor `008` 的非空保护，故后续按维护步骤停写、备份和清理。

上述盘点是本机清理前状态。2026-09-25 已停止本机栈并核对无 pending/running Run，将两库分别归档到 `/tmp/graphharbor-boundary-20260925-prewipe-runtime.dump` 和 `/tmp/graphharbor-boundary-20260925-prewipe-platform.dump`；归档目录核对通过，完整恢复尚未演练。旧运行历史、平台 Thread ACL/run requests 已清理，Dear memory/skills 保留；Runtime 升至 `008_remove_business_scope`，平台升至 `20260925_0005`。当前 Runtime 库 11 MB、Thread/Run/Event 为 0，候选包本机栈健康。`apps/runtime-service/uv.lock` 仍锁旧 PyPI wheel，本轮用 `UV_NO_SYNC=1` 保持安装在虚拟环境中的候选包；普通 `local-stack.sh start` 会同步回旧包，正式版本依赖及剩余联合验收见主方案 04。

事件保留候选联调补充（2026-09-25）：独立 Platform API 库 `graphharbor_event_retention_platform_candidate` 升至 `20260925_0005`，独立 Runtime 库升至事件迁移 009；候选双 wheel 的 Runtime API/worker 与平台 API 分别使用 18632/18633。首次平台 Thread 创建返回 500，定位为本地启动脚本未设置 Auth 回查所需的 `PLATFORM_THREAD_AUTHORIZATION_URL`；已在 `scripts/local-stack.sh` 默认注入当前平台端口，`bash -n` 和手工隔离栈实测通过。补齐环境后，网关创建 Thread、读取 Thread/state/history 均为 200，未登录读取为 401。首次 Graph 搜索返回 403：平台超级管理员同时拥有项目角色时，网关签发项目角色，Runtime 拒绝全局助手目录搜索；已在平台网关保留平台级委托角色，整文件 3 项单测及隔离 HTTP 重测通过，Graph 搜索现为 200（4 个图），Thread 创建仍为 200。普通项目角色没有被提升。Web 18634 的浏览器烟测完成登录、会话治理读取与 Graph 目录刷新，控制台 0 errors；页面刷新不保留刚输入的定位 ID，不能算断线续传。HITL/文件仍未验收。候选栈未使用既有业务库或默认端口。

暂停快照以 GraphHarbor 主方案为准。恢复时先核对候选栈/归档仍存在及两库 revision，再处理可重复安装与完整恢复；业务 Run/SSE/HITL、文件正向链路和官方全入口差分仍是未完成事项，不能将此前的 Thread ACL 浏览器 10 项通过扩大解释为业务全链路通过。

2026-09-25 依赖更新：GraphHarbor 双包 `0.13.0.post33` 已发布到 PyPI，runtime-service 的 `pyproject.toml` 与 `uv.lock` 均锁定 post33。普通 `uv sync --frozen` 已从公开索引安装并替换临时 post32 wheel，`uv run --frozen` 导入检查通过；后续联调不再依赖 `UV_NO_SYNC=1`。完整业务链路和 Final 状态仍按 GraphHarbor 主方案核对。

同版本本机联调：无 `UV_NO_SYNC` 的 local stack 已升级 Runtime 到迁移 009 并全部就绪；runtime-service 定向 99 passed。平台网关创建 Thread/Run、state 和 SSE 成功；向 worker 进程注入 `miaomiaoai` 的 `deepseek-v4.1-flash` 凭据后，真实模型 Run success 且响应非空。`workflow_demo` 人工确认路径完成 interrupted → `command.resume` → success。恢复请求带 `assistant_id` 会按当前平台契约返回 `resume_configuration_override` 400，正确请求仅提交 `command.resume`。跨用户 ACL、文件正向链路与 Final 继续见主方案。

文件正向浏览器补验：post33 本机栈的 `e2e/retired-result-service.spec.ts` 1 passed（1.7 分钟），覆盖 Dear Agent 浏览器创建会话、写文件、发布成果、在线预览与安全下载；测试用例清理自身 Thread 和项目。路径逃逸、重启/HITL/fork 资源绑定、zip/terminal/skills 仍按主方案 03 验证。

两份切换前归档已用本机 PG17 的 `pg_restore --exit-on-error` 完整恢复到独立库，Runtime 旧 revision 006 与 57 Threads/324 Runs/434,742 Events、平台旧 revision `20260922_0004` 与 57 Thread ACL/401 run requests 均核对一致。隔离浏览器治理矩阵第一次重跑为 5 passed、5 failed；失败创建 Thread 403 是 Runtime ACL 回查仍指向主平台 2142，而测试 fixture 是 12142。将回查目标临时切到 fixture 重跑后须恢复主平台地址；本次失败不计通过。

隔离治理矩阵在临时切换 Runtime 回查地址到 12142 后 10 项均通过（29.4 秒），随后已恢复主平台 2142。fixture 关闭时报告遗留 6 条临时 ACL，属于测试清理失败，未写入正式 platform_api；下次需用网关逐条删除或在 fixture teardown 增加失败清单核对，不能把“10 passed”扩大成无残留通过。

2026-09-26 续验：使用完整回查地址 `http://127.0.0.1:12142/api/runtime/internal/thread-authorization` 重跑治理浏览器矩阵，10 passed，fixture `thread_access` 残留为 0；正式 Runtime 地址已恢复为 2142。Runtime workspace/zip/HTTP/browser/terminal/resource-binding 定向回归 54 passed，PG17 restart/HITL/workspace 1 passed，skill snapshot restart 4 passed。skill restart 测试改用本地后端已有 `RUNTIME_SKILLS_ROOT`、`RUNTIME_WORKSPACE_ROOT`，消除 Docker 路径假设；GraphHarbor 边界未改变。完整跨项目故障注入和 Final 门禁仍未完成。

2026-09-26 官方对照续验：GraphHarbor 主方案的同一 identity-only Auth fixture 在官方 `langgraph-api==0.13.0` 与 post33 上通过 12 类 Thread/Run/HITL/SSE 子集对照；完整 OpenAPI 比较仍有 203 处差异（路径/操作 140、组件 schema 63）。该结果不证明平台 ACL 跨身份 Final 或通用 API 全兼容，详见主方案 04。

2026-09-26 创建故障注入：平台网关对 Runtime 已创建而 ready 确认失败、上游 5xx 且探测再次失败的请求返回可对账 UUID；ACL 预留已消失时不报告 ready。五个 ACL/gateway/委托/SDK 测试模块 71 tests、3 skipped，Ruff/format 钩子通过。明确 4xx 后平台数据库清理失败仍可能留下 pending ACL，Runtime 不存在时须人工核对清理；该异常不记为自动补偿完成。相关实现仅在 platform-api，GraphHarbor 不承担业务 ACL。

同日 Web `session.service.spec.ts` 验证 503 与 504 均能保留 pending UUID 并在后续创建前对账，7 passed；pre-commit 的 Ruff/format/eslint/prettier 全部通过。正式本机栈登录后在临时项目创建、读取、删除 Thread 均为 200，临时项目删除 200。此烟测仅覆盖单用户正向路径。
