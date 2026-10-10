# 自动标题CAS与非前端收尾

2026-10-09；关联T02/T04/T05/T07A，沿用户批准R1-R5实施。前端T06/T07B及正式发布B01独立。

## 原子写与未知结果

GraphHarbor新增共享 `thread_metadata.py::patch_thread_metadata()`，普通metadataPATCH使用JSONB浅merge，独立 `threads_metadata_cas()` 要求metadata/if_metadata，授权filters/比较/写入同SQL。`ops.py::Threads.patch()` 与公开HTTP共用，无Schema迁移/业务标题字段；server路由/OpenAPI同步。

平台 `ports.py` 和 `runtime_gateway_upstream.py::compare_thread_metadata()` 走独立URI；旧引擎404/405明确不可用，不允许普通PATCH忽略条件。API比较原title/seed，409回读当前Thread；提交结果未知或不合格确认统一503，前端GET对账。自动合法degraded消费seed且保留规则title，manual degraded不改。

`service.py::update_thread()` 使用真实上游metadata响应，避免生成期间preview请求的旧快照覆盖新title。显式title改名包括同名都清seed；fork/import/旧Thread无自动资格；客户端私有seed/pending递归拒绝，公开只有pending布尔。

## 有界调用与验证

Runtime同步模型构造移入 `asyncio.to_thread`，默认8s覆盖受管连接/构造/调用；超时后不会执行ainvoke，已开始的同步构造线程不能强杀。标题只有一个注入模型的生成helper，callbacks为空/nostream，辅助不占主Run/SSE/Usage。

API27项auto/manual/fork、Runtime6项服务、GraphHarbor4项PG/HTTP及跨解释器委托新增title operation通过。复用已有native服务harness，在隔离PG/Redis启动真实API/Runtime/Worker；8场景fixture与真实qwen-plus受管模型2项通过（91.14s），随后9场景fixture真实ACL撤销扩验通过（79.28s）。候选v2冷安装/哈希与正式post43缺CAS事实分开记录，完整失败/修复证据见verification.md。

前端交接冻结DTO、reason、403局部拒绝、503未知写对账、epoch/manual优先和F01-F10。不是新增values.title订阅，也不新增Middleware/标题表/独立模型配置。

收尾同步方案/活规范/交接：创建时gate关闭不写seed，之后不回填；当前委托矩阵30项、加独立Cron共32项。专项16文件文档规则检查、两仓26文档128个本地链接目标核对及diff --check通过。已清理确认无进程使用的本轮失败测试临时配置。

用户随后同意收尾经验提案，已将旧服务忽略条件字段的风险和独立URI拒绝策略写入[跨服务经验库](../../../lessons/cross-service.md)，同步经验索引与CONTEXT。
