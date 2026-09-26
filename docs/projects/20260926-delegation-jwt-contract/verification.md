# Delegation JWT - 验收执行包

## 当前状态

实现未开始。本轮仅静态源码核查和文档检查；本专项自动化、HTTP集成、真实worker/SSE跨到期点及回退均未执行。以下测试入口中标“新建”的文件当前不存在。

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
| R05 | 后续获准在隔离环境切回前一API产物 | Runtime不变、在途Run不重发/重签；旧API既有操作可用；已知旧签发缺陷如实记录，无DB回滚 |

C10的消息内部回查若在真实环境复现，应单列端点、operation和安全失败结果；不能把R01—R05通过扩写成所有23个operation端到端通过。保持拒绝，不泄露响应原文，不改Runtime去满足本期门禁。

## 5. 兼容与回退门禁

必须验证新API/当前Runtime以及旧API/当前Runtime两组合；历史Runtime未测不承诺。新增字段/operation不在本期；已有两关联claim有/无均覆盖。仅回退API产物，无数据库操作，不取消/重签/重发已有Run。

不增加独立性能压测项目：本期没有新服务或网络查询机制；双端安全契约、权限隔离、HTTP回归、真实生命周期与回退是必需项。若实现引入额外远程调用或后台任务，即越界，应撤回该设计。

## Phase 验证记录

2026-09-26：重新静态核对唯一签发器、Gateway/Catalog入口、Runtime claim/scope/principal/policy约束、Thread ACL和自定义资源路径。正常模型策略已有非空哨兵；签发校验差异、Catalog凭据缺口及消息内部原生回查限制已明确。没有运行本专项业务测试。

本轮文档检查：python3 scripts/check_docs.py与git diff --check均通过（退出码0）；JWT及原AI路由8份文档的相对链接/围栏通过；J1—J6均未勾选。AST静态比较确认两端operation集合相同且共23项，文档逐项覆盖。6份既有非文档修改的SHA-256与接手基线一致。上述结果不等于功能测试通过。

后续各Phase记录任务、命令、退出码、版本、实际通过/失败数及限制。

## Final 验收记录

未开始。业务实现及C01—C10、R01—R05尚未验证；缺环境或Runtime既有阻塞必须单列，不得以文档完成或基础token校验通过标记全部功能done。
