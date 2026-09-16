# P6 记忆与技能治理：实现与集中验证

## 范围及批准

2026-09-15用户批准P6，集中写完代码后统一验证，失败定向复验。仅后端，前端交接，页面deferred。用户明确K23后置。P5多参考图连接异常不依赖本阶段，不阻塞；K14—K16及大文件继续deferred。

## 冻结的实现边界

- 长期事实只存Runtime私有PostgreSQL表，复用现有DATABASE_URI；不双写BaseStore，不访问GraphHarbor私有表。官方Store未承诺CAS，采用方案06已允许的数据库行锁与revision路径。
- 记忆默认tenant/project/user隔离。自动提取只形成有源用户消息的候选，不自动批准；删除／清空通过epoch与墓碑阻止旧候选复活。偏好永远不是授权。
- 自定义技能候选和不可变内容版本归Dear私有模块。审查、评估、发布分开；候选不能自动获得工具权限。启用版本按线程冻结，撤销即时拒绝后续装配。公共资源保持来源哈希及许可证。
- HTTP只做内部授权与边界适配，Platform负责项目权限、短时委托和审计。GraphHarbor继续只管理执行与checkpoint。
- K22保留原预览部署意图，不能以生成ZIP代替真实发布成功；未经精确文件与目标审批不外发。K23不复制／不启用，台账标deferred。

## 逐项记录

下列 Runtime 路径统一以 `apps/runtime-service/src/runtime_service/` 为前缀，Dear私有业务根为 `services/dearflow_agent/`；不是在GraphHarbor或Showcase新增业务。

| 需求 | 代码路径与排查入口 | 后端实现/验收 | 前端 |
|---|---|---|---|
| M02 持久化和作用域 | `services/dearflow_agent/governance_storage.py:connect/lock_scope`、`migrations/002_governance.sql` | 实现完成；真实PG租户/项目/用户隔离、并发CAS通过 | 交接done；页面deferred |
| M03 显式事实管理 | `services/dearflow_agent/memory.py:MemoryStorage.change/read/context`、`tools/memory.py` | 新增/修改/删除/查询、显式工具HITL实现；HTTP/revision通过；跨会话模型待验 | 同上 |
| M04 自动候选 | `services/dearflow_agent/middleware/memory.py:MemoryContextMiddleware` | opt-in结构化提取、来源引用、epoch和幂等完成；确定性测试通过，真实模型提取待验 | 同上 |
| M05 生命周期 | `services/dearflow_agent/memory.py:MemoryCommand/FactInput/propose` | 容量、过期、有界上下文、清空、追加恢复测试通过；无语义索引 | 同上 |
| K-G3 版本治理 | `services/dearflow_agent/skill_governance.py:inspect_package/SkillStorage`、`workspace/backend.py:prepare_custom_skills/ReadOnlySkillsBackend` | ZIP边界、版本/回退/撤销、固定线程、并发装配/只读测试通过；真实发布到新线程待验 | 同上 |
| K17 技能审查 | `services/dearflow_agent/skills/skill-reviewer/`、`tools/skills.py:review_skill_package` | 后端静态审查链路done：候选→审查→报告下载通过。static_only不能证明脚本运行安全 | 同上 |
| K18 技能创建 | `services/dearflow_agent/skills/skill-creator/`、`tools/skills.py:create_skill_candidate/evaluate_skill_candidate/publish_skill` | 创建/打包/候选/文本评估实现；真实链路验证中。上游CLI、脚本对照基准和trigger优化未实现，整体partial | 同上 |
| K19 技能发现 | `services/dearflow_agent/skills/find-skills/`、`tools/skills.py:find_skills/import_skill/read_bounded` | 本地目录、GitHub固定commit导入完成；下载有界测试通过；远端导入真实验收待验 | 同上 |
| K20 偏好引导 | `services/dearflow_agent/skills/bootstrap/`、`tools/memory.py`、官方request_information | 资源/接入完成；真实澄清→保存→新会话验证中 | 同上 |
| K21 技能推荐 | `services/dearflow_agent/skills/surprise-me/`、`tools/skills.py:list_skills` | 目录标记backend_verified/recommendable，只推荐已验收公共能力；真实组合链路验证中 | 同上 |
| K22 预览部署 | `services/dearflow_agent/skills/vercel-deploy-claimable/`、`tools/deployment.py:deployment_package/deploy_preview` | 静态包白名单/审批/摘要幂等实现，默认关闭；真实发布待精确批准，动态框架未实现，partial | 同上 |
| K23 外部桥接 | 不新增目录、工具或外部CLI | deferred：用户明确后置，不再等待改写范围确认 | deferred |

### 跨服务接入文件

- `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`：组合治理工具、官方HITL、记忆中间件、自定义技能线程版本；`capabilities.py`登记权限和开关。
- `apps/runtime-service/src/runtime_service/http/dear_governance.py`：internal memory/skills路由与作用域验证；`webapp.py`注册router。
- `apps/runtime-service/src/runtime_service/runtime/auth.py`：新增两个委托operation；`auth/platform.py`禁止此类令牌访问原生Server资源，不能拿治理令牌执行Agent。
- `apps/platform-api/src/platform_api/core/security/tokens.py`：签发白名单同步两个operation。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py:dear_governance`：先检查项目读/写权限、线程与Dear图，签发对应操作的短时委托。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/ports.py`、`adapters/langgraph/runtime_gateway_upstream.py`：既有网关端口与Runtime私有HTTP适配。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`：公开GET/POST `/api/langgraph/threads/{thread_id}/dear/{memory|skills}`；使用现有响应脱敏。
- `apps/platform-api/src/platform_api/modules/audit/http_resolution.py`：治理读/写审计路由登记；不将完整事实或技能内容作为审计摘要。
- 前端不写代码。`frontend-handoff.md`的P6增量说明字段、409处理、用户切换、授权发布与页面待验清单。

### 已知边界

- 事实是最多100条、候选100条、上下文10条/4000字符；每次检索是字面匹配，不宣称语义召回。恢复为显式追加导入，不是覆盖整库。候选只在确认后进入事实；自动提取失败记类型日志，不影响回答，尚无独立持久失败队列。
- 自定义技能每作用域最多50版本；静态审查和2—6条无工具文本评估不等于完整脚本安全评估。候选不会增加工具权限；激活仍须明确授权，当前线程不自动升级。
- K22固定目标为 `https://claude-skills-deploy.vercel.com/api/deploy`，只支持静态网页包。需要逐个批准文件manifest和摘要；未知结果复用外部任务unknown，不盲目重发。未真实发布不能标done。

## 本地部署与回滚

2026-09-15已在本地Runtime配置的数据库显式应用`002_governance.sql`，设置本地`apps/runtime-service/.env`的`RUNTIME_DEAR_GOVERNANCE_ENABLED=1`，重启runtime-api、runtime-worker、platform-api。没有修改生产配置或GraphHarbor代码，部署不放到请求/lifespan。

部署命令（先加载本地环境）：`python -m runtime_service.services.dearflow_agent.governance_storage`。回滚将治理开关设为0并重启两个Runtime进程，保留三张表和用户数据；K22开关继续关闭。不执行DROP或反向破坏性迁移。回滚实际开关链路尚待验证，不冒称已完成。

## 已执行验证

| 证据 | 结果 | 含义 |
|---|---|---|
| `/tmp/dear-p6-runtime.log`：P6 + test_agent + test_context | 首轮23 passed、1 failed，218.74s | 失败为合法治理JWT被operation白名单拒绝，非模型问题 |
| `/tmp/dear-p6-runtime-fixed.log`：`tests/services/dearflow_agent/test_p6_governance.py` | 修复后8 passed，45.13s | 真PG/CAS/作用域、删除竞争、HTTP、版本回退/撤销、并发只读快照、来源幂等与下载限额 |
| `/tmp/dear-p6-platform-adapters.log` | 15 tests OK，1.320s | SDK私有路由适配 |
| `/tmp/dear-p6-platform-matrix-fixed.log` | 1矩阵测试OK，23.920s | 新公开路由与权限矩阵；初轮测试参数缺resource，修复后定向复验 |
| `/tmp/dear-p6-lint-fixed.log` | 新增9文件ruff通过 | 自动修复imports等，不替代行为测试 |
| `/tmp/dear-p6-e2e.log` | K17已通过；K18修复后待复验；K19模型超时；K20/K21通过 | K17真实候选审查链路通过；其余真实模型链路未冒称完成 |

测试代码：`apps/runtime-service/tests/services/dearflow_agent/test_p6_governance.py`、`tests/e2e/test_dearflow_skills.py`、`tests/services/dearflow_agent/skills/platform_batch.py`；Platform对应`apps/platform-api/tests/test_runtime_gateway_sdk_adapters.py`和`test_runtime_gateway_http_matrix.py`。

## 集中验证计划

真实PG隔离schema：并发CAS、作用域、删除／提取竞争、恢复、技能版本切换与固定；确定性包负例；Runtime授权HTTP与Platform网关；真实模型跨会话记忆及逐项技能链路。代码全部写完后一次执行相关批次，不全量跑P4/P5。真实外部服务失败独立标blocked。

### K17真实链路已通过

project=`d515bc03-5919-401d-8b3a-750ca323e22f`，thread=`35f61b7e-bbe6-4a56-8e9b-cc7cb1fea212`，最终run=`c61f6cf8-e4f5-47be-8c1b-644ac7cf628d`。真实工具创建未启用候选、记录静态审查、审批写报告/发布、授权下载并复核SHA256通过；产物摘要`5c6d4d8be12a1705d6582615add3df65fb6005e2425dd848ceeee0475ab7fa79`。这证明静态审查链路，不证明任意脚本安全。

2026-09-15复核更新：K18单项真实平台验收1 passed（613.76s），见[14记录](../implementation/14-p7-production-gates.md)。K19为产物发布之后的模型节点触发本地30秒超时，非技能创建/查询失败；生产预算仍待调整验证。
