# Delegation JWT - 验收执行包

## 当前状态

J1—J6平台范围任务、双端claim/端点授权矩阵及R01—R04真实生命周期均有证据。消息内部原生Run子调用的既有403仍为当前组合的兼容限制；Final结果单列于文末。

## 1. 双端测试架构

平台测试使用真实create_runtime_delegation_token；在内存生成token，通过stdin交给Runtime虚拟环境的Python子进程；子进程入口位于API tests/fixtures，导入现有verify_delegation_claims/Runtime auth函数。stdout只返回成功/安全错误类型及必要的非敏感校验结果，不回显token。

固定使用两服务已安装锁定环境；不安装新依赖、不把Runtime作为API生产依赖、不复制校验函数。subprocess设置有限超时和check/returncode断言，输入用JSON结构，不用shell拼token或命令行参数。所有密钥为测试常量，与真实配置无关；子进程环境只传所需测试配置，不加载真实.env。

C01—C05先调用纯校验器；C06—C10调用真实HTTP认证/授权函数及平台路由，mock仅用于数据库/网络边界或已有测试夹具。跨进程测试仍不等于真实HTTP/worker验收。端点授权测试不能只调用verify_delegation_claims然后宣称授权通过。

## 2. 自动化矩阵

| 编号 | 输入/操作 | 断言 |
|---|---|---|
| C01 | plan第4节23项，各有合法scope；五项assistant例外；其余缺assistant | 合法token被真实Runtime接受；非例外缺assistant平台拒绝；23项覆盖数固定，避免漏项 |
| C02 | sub/tenant/project/role空、非字符串、空白、Unicode、129字符；合法128字符 | 非法平台ValueError，合法边界两端接受；不改身份值；permissions字符串容器/非字符串元素拒绝，合法strip/去空/去重/排序保持 |
| C03 | allowed_model_ids空、重复、非法名称；无可用模型策略 | 空列表签发拒绝；策略既有platform:no-enabled-model仍能形成合法token，但不能因此执行任意模型 |
| C04 | tool_overrides True/0/None、129键、JSON4096/4097字节；policy文本空白、100000/100001字符 | 固定边界正确；构造字节边界时先确保键/数量合法；两端一致；不通过截断修复 |
| C05 | scope未知键、数字资源、strip后空串、tenant/project错配；context_hash缺失/错格式/实际context不同 | 平台拒绝非法输入，Runtime拒绝伪造token；真实context含execution_mode/access_policy的摘要和空摘要均一致；编号不进摘要 |
| C06 | user带credential；service account缺/非法credential；有效但凭据属于其他账号；撤销/到期/grant取消 | 格式问题签发前拒绝；归属/状态问题由现有Actor/ACL真实逻辑拒绝；不把UUID格式通过当授权通过 |
| C07 | Gateway初始read/scoped与Catalog用户/服务账号分别签发；连续两个HTTP请求 | 当前身份与凭据准确；jti各次签发不同；无跨请求缓存；结合追踪实现时两个关联claim匹配当前上下文 |
| C08 | 三处签发失败；Runtime401/403/ACL回查503；用户平台token失效 | 签发失败安全503且无业务上游动作；Runtime401按错误专项转502，不清用户会话；授权拒绝不自动重试用户动作，无secret/token原文 |
| C09 | 错签名/算法/issuer/audience、过期exp、未来nbf/iat、非2版本、未知claim；缺/改变kid但有效签名 | 前组Runtime拒绝；kid行为按现状不作为选钥；jti/nbf省略等可选claim记录现状，平台仍总发；底层关闭aud检查的测试不能替代真实authenticate |
| C10 | 原生8项允许动作/错资源/错Thread/错assistant/缺Run目标；自定义15项跨原生访问；无Thread memory/skills和带Thread反例 | 逐行验证资源矩阵；Thread ACL回查拒绝/不可用不放行；自定义token不能访问原生资源；保留message-read接受enqueue现状，内部原生回查冲突单列失败证据 |

每个拒绝用例同时断言没有业务副作用；纯校验失败不得开始Run、创建Thread或写工具资源。原生授权函数可注入受控ACL响应，但应另外用平台现有数据库测试验证真实actor/grant加载。

未知字段由测试使用测试密钥构造，不通过放宽平台签发器制造。契约测试不得新增生产claim、修改Runtime白名单或伪造通过。

## 3. 执行命令与环境

从仓库根目录使用已安装环境；先由实现者创建新测试后执行：

```bash
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_runtime_delegation_contract.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_runtime_delegation.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_runtime_catalog_delegation.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_runtime_thread_authorization.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_service_account_project_grants.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_run_requests.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_thread_acl.py"
"apps/runtime-service/.venv/bin/python" -m pytest "apps/runtime-service/tests/runtime/test_auth.py" "apps/runtime-service/tests/runtime/test_platform_auth.py" -q
```

新契约测试按仓库根定位Runtime解释器与源目录；缺环境必须在结果中报明，不能静默skip后记契约通过。Runtime现有测试仅执行，不改文件或依赖；其已有失败按原始基线记录，不擅自修Runtime。

Final运行API完整既有测试及修改文件的现有Ruff检查；不升级依赖、全库格式化或运行迁移测试去更改真实库。数据库测试只用隔离数据/既有测试夹具。版本证据至少含两侧Python/PyJWT及锁定GraphHarbor版本。

## 4. 真实链路验收

前提：已运行的隔离平台/Runtime/worker，现有模型配置、测试项目、user及service account测试身份。无需修改Runtime TTL或观测配置；真实密钥和委托不写入证据。没有环境时记录未验证，不启动带迁移的local-stack start。

| 编号 | 操作 | 通过条件/证据 |
|---|---|---|
| R01 | 通过平台提交执行时间跨过当前委托exp的真实Run，记录接受与后续时间点 | exp后worker仍按既有规则执行，没有因该委托过期自动取消/重发/重签；业务失败另行归因 |
| R02 | exp前建立SSE，观察跨exp；主动断开再经平台重连 | 不新增周期重验/到期定时断流；重连有新请求/新委托、只订阅原Run，不增加Run |
| R03 | 在已授权隔离测试夹具中准备已撤销用户权限/服务账号凭据或grant，再尝试重连、审批、取消 | 新请求被当前权限拒绝；有效权限对照成功；已有Run不因测试拒绝被自动取消；对现有真实账号撤权必须另有明确授权 |
| R04 | 权限有效时真实审批、取消、Catalog读取/刷新；服务账号合法操作对照 | scope/credential正确、恢复关系保持、取消ACK和终态分别记录；服务账号无权的个人memory/Thread创建不放开 |

C10的消息内部回查若在真实环境复现，应单列端点、operation和安全失败结果；不能把R01—R04通过扩写成所有23个operation端到端通过。保持拒绝，不泄露响应原文，不改Runtime去满足本期门禁。

## 5. 版本边界

仅验证新API/当前锁定Runtime组合，不设置旧API、旧Runtime、新旧服务混用或旧产物切回测试。新增字段/operation不在本期；已有两关联claim在当前组合中覆盖有/无两种情况。无数据库操作；已接受Run不因本专项取消、重签或重发。

不增加独立性能压测项目：本期没有新服务或网络查询机制；双端安全契约、权限隔离、HTTP回归及真实生命周期是必需项。若实现引入额外远程调用或后台任务，即越界，应撤回该设计。

## Phase 验证记录

2026-09-26 平台签发阶段：`test_runtime_delegation.py` 18项、`test_runtime_catalog_delegation.py` 15项通过；新增非法输入拒绝、当前请求关联和service account凭据断言。`test_runtime_delegation_contract.py` 1项通过，内部逐项核对23个operation；当前Runtime虚拟环境的现有校验器接受平台token及两个关联claim，耗时23.271秒。Runtime原文件未修改；拒绝矩阵和真实HTTP端点未执行，不能记C01—C10全通过。

2026-09-26：重新静态核对唯一签发器、Gateway/Catalog入口、Runtime claim/scope/principal/policy约束、Thread ACL和自定义资源路径。正常模型策略已有非空哨兵；签发校验差异、Catalog凭据缺口及消息内部原生回查限制已明确。没有运行本专项业务测试。

本轮文档检查：python3 scripts/check_docs.py与git diff --check均通过（退出码0）；JWT及原AI路由8份文档的相对链接/围栏通过；J1—J6均未勾选。AST静态比较确认两端operation集合相同且共23项，文档逐项覆盖。6份既有非文档修改的SHA-256与接手基线一致。上述结果不等于功能测试通过。

后续各Phase记录任务、命令、退出码、版本、实际通过/失败数及限制。

### 2026-09-27 J1 双端基线

- 环境：API Python 3.13.9 / PyJWT 2.12.1；Runtime Python 3.13.9 / PyJWT 2.13.0 / GraphHarbor 0.13.0.post33；两侧既有虚拟环境，无依赖安装。
- `test_runtime_delegation_contract.py` 经API虚拟环境调用Runtime原校验器、`authenticate`、原生及自定义授权函数。23项operation、签名/算法/issuer/audience/时间/版本/未知claim拒绝、实际context摘要、HTTP audience、kid现状均有断言。新增测试没有复制Runtime校验逻辑；真实消息存储和业务执行不由子进程测试代表。

### 2026-09-27 J2 签发输入收口

- `test_runtime_delegation.py` 新增claim边界：principal类型/空白/ASCII/128/129长度、permissions归一化、空模型、policy文本、scope、false-only工具限制与JSON 4096/4097字节。合法极值及`platform:no-enabled-model`由当前Runtime校验器接受；哨兵不表示可执行任意模型。
- 生产`tokens.py`为接手时已有平台修正，本轮未覆盖或重写。非法输入统一ValueError的行为由平台测试核对。

### 2026-09-27 J3 两处工厂与安全失败

- Gateway初始/scoped与Catalog签发ValueError均变为安全`503 runtime_delegation_not_configured`，测试断言无上游调用且响应消息无内部原文；连续两次HTTP请求的关联值不同，四次签发的jti不同。
- 真实测试service account带项目grant读取Catalog为200，禁用后同一API key返回`401 invalid_api_key`；Catalog刷新200、4项。未输出credential/token。

### 2026-09-27 J4 动作与身份矩阵

- 原生8项的有效动作、错误operation/Thread/assistant/Run目标、ACL拒绝403/不可用503；自定义15项的正确operation、错误operation和资源错配均经过当前Runtime授权函数。ACL HTTP与存储边界使用受控替身，因此是已锁定契约测试，不是完整部署E2E。
- API隔离库测试拒绝其他账号的`credential_id`；现有grant/凭据撤销到期及Thread ACL用例沿用。消息自定义入口token可到达存储边界，但同一token访问内部原生Run时当前Runtime返回403：保留拒绝行为，记为既有跨端点阻塞，不扩权限。

| 编号 | 阶段结论 | 证据边界 |
|---|---|---|
| C01 | 通过 | 23项平台签发→当前Runtime校验；非例外缺assistant由平台拒绝 |
| C02 | 通过 | 平台非法输入及128/129长度；合法128字符由Runtime接受 |
| C03 | 通过 | 空模型拒绝；既有无模型哨兵token由Runtime接受，不代表Run可用 |
| C04 | 通过 | false-only、128/129键、4096/4097字节和policy文本边界 |
| C05 | 通过 | scope错配、空/实际运行context摘要及execution_mode/access_policy变化 |
| C06 | 通过 | service account格式、跨账号凭据、隔离库撤销/到期/grant及现役禁用对照 |
| C07 | 通过 | Gateway初始/scoped、Catalog身份，双HTTP请求关联与不同jti |
| C08 | 通过 | 三处安全503、Runtime401→平台502映射、资源403/ACL503；无原文上游调用 |
| C09 | 通过 | 签名、算法、iss/aud、时间、版本、未知claim拒绝；kid非选钥现状 |
| C10 | 部分 | 原生8项/自定义15项授权函数矩阵通过；消息内部原生Run子调用当前403，未宣称业务成功 |

### 2026-09-27 J5 真实生命周期阶段进度

- 现役本地stack状态：Runtime API/worker、platform-api、platform-web均运行；委托TTL60秒。R01尝试：Run `6b6ee229-42cf-4b83-b9c5-b5ce17f18b26`于02:05:49 UTC接受，Runtime只读记录显示02:05:53已`success`；`after_seconds=70`虽存在于保存的kwargs，却未延迟执行。02:08:15查询到成功不能当作跨TTL证据，R01未验证。
- R02 SSE连接200，观察约61.6秒和90个事件标记；到期后重连200且Run列表仍仅1条。R03专用测试用户禁用后Catalog、SSE重连、取消新请求均`403 user_not_active`；其已提交Run在0.2秒内`error/business_error`，不能证明撤权后的在途执行。R04取消ACK200，独立查询终态`interrupted`；Catalog读/刷新、service account正反例通过。
- R04补充：`showcase_demo`产生真实`write_file` interrupt，按真实ID经平台`input.respond`批准，新Run最终`success`；文件内容读取探针返回400，不记文件验收。
- 后续显式模型预检Run成功；再次提交带`after_seconds=70`的Run并在31毫秒后撤权，新取消请求返回403，但Runtime记录显示该Run在创建后约0.18秒即`error/business_error`。延迟参数保存在kwargs却未生效，不能将该样本记为撤权后在途Run验收。
- 后续只读核对：第二条失败Run的终态事件为`RuntimeResolutionError: runtime.model.initialization_failed`，不属于JWT到期证据。
- R01新样本：隔离Thread `2b3ecf30-be4a-4433-9ff2-60cc7ba56738`经平台审批的Run `5ae46b6f-61ed-4003-88dc-351185977dcf`于02:37:28.797 UTC创建、02:38:37.296 UTC成功，持续68.499秒；`execute`工具持续约59.09秒、退出码0，完成时间跨过60秒TTL。此前短Run仍按失败探针保留。
- R03新样本：专用用户 `e9b07bac-817f-425b-95e8-cf1b9f66eb92`的Run `3dd06ea6-fbd9-46bb-9249-17777ce394a2`于02:40:56.726 UTC创建，02:40:59禁用用户；Catalog和取消新请求均`403 user_not_active`，工具继续执行并以退出码0完成，Run于02:42:03.207成功，持续66.481秒。管理员轮询该用户Thread得到预期ACL 403，终态由Runtime数据库只读核对。
- 未验证：消息内部原生Run子调用在现役部署中的完整业务结果；自动化已复现当前Runtime对该自定义operation返回403。详见[真实链路阶段记录](implementation/03-live-lifecycle.md)。

### 2026-09-27 J6 交接与代码质量

- API全量：在`apps/platform-api`运行`rtk proxy .venv/bin/python -m pytest -q tests`，退出码0，299 passed、15 skipped、606 subtests passed（5分24秒）；修改后重跑契约/Catalog定向测试，退出码0，21 passed、46 subtests passed。
- Runtime只读：在`apps/runtime-service`运行两个现有鉴权测试，退出码0，46 passed；未改Runtime文件。
- `uvx --offline ruff check`与`ruff format --check`对两份新增测试文件通过；相关8文件的`E4,E7,E9,F`检查通过。完整Ruff检查这8文件仍有148条，主要是既有FastAPI默认参数B008、导入排序等基线；没有按本专项范围全量格式化。
- `python3 scripts/check_docs.py`与本专项文件的`git diff --check`退出码0。全工作树`git diff --check`退出码2，告警来自无关的`apps/platform-web/patches/@langchain__langgraph-sdk@1.10.2.patch`制表符缩进；未改该文件。
- 首轮直接调用`rtk pytest`/`rtk ruff`因系统可执行文件不在PATH未启动；改用现有虚拟环境解释器与离线`uvx`成功重跑。相关文件曾检出Catalog缺失`Mapping`导入，已补齐并重验。

## Final 验收记录

### 2026-09-27 Final

**完成度：`partial`。** J1—J6平台范围任务均已完成；本专项当前组合的消息内部原生Run回查仍有已复现的403兼容限制，消息业务全链路未验证，不能宣布23项operation全部端到端通过。该限制需要另行处理Runtime内部调用契约；本期禁止改Runtime/GraphHarbor或扩大`read`权限，因此未作越界修复。

**状态核对：** README为部分完成，tasks.md的J1—J6均为`[x]`，Phase分别有J1—J6六项记录，CONTEXT的JWT行仍为partial。plan.md保持v2、平台侧和简化生命周期范围；四处状态与此Final一致。

**单元及契约：** API全量`299 passed, 15 skipped, 606 subtests passed`，退出码0；最后修改后契约/Catalog定向`21 passed, 46 subtests passed`，退出码0。Runtime两个只读鉴权文件`46 passed`，退出码0。C01—C09通过；C10的原生8项/自定义15项授权矩阵通过，消息自定义operation进入内部原生Run读取时当前Runtime返回403，单列为兼容限制。

**真实集成与端到端：** R01真实工具Run持续68.499秒并成功，越过60秒委托TTL；R02 SSE连接跨TTL且重连只订阅，Run数未增加；R03专用用户撤权后Catalog/取消新请求均403，已接受的工具Run持续66.481秒并成功；R04审批后恢复Run成功、取消ACK后终态为`interrupted`、Catalog读/刷新及service account正反例通过。前两次`after_seconds=70`探针未形成长Run，不计入R01/R03。真实消息业务子调用未验证，不能以受控授权函数结果替代部署链路。

**质量与边界：** 两份新增测试文件完整Ruff和格式检查通过；相关文件`E4,E7,E9,F`检查、文档检查及本专项范围`git diff --check`通过。完整Ruff检查8个相关文件仍报148条现有文件基线诊断，主要为FastAPI默认参数B008；全工作树diff检查因无关Web SDK patch制表符告警失败。未改Runtime/GraphHarbor源码、配置、依赖及数据库结构；未执行迁移、部署、Git提交或分支操作。未引入新服务/远程调用/后台任务，专项方案不要求独立性能压测；没有部署变更，回滚演练不适用。

**剩余阻塞：** 若要求消息业务全链路通过，需另行批准Runtime内部原生Run回查与自定义operation的契约处理，并在新范围内做真实端到端验证；当前403拒绝保持原样。其余J1—J6范围内任务无未完成项。
