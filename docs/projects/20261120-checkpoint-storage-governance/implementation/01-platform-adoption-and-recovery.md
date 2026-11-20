# 平台正式接入、消息容量与恢复实证

日期：2026-11-21。关联P02–P07。平台全部产品改动位于独立Worktree，登记`wt_3b7f1734875d`；双库/角色、Redis、Workspace和安装目录独立。未迁移或重启现役生产环境。进度只维护在../tasks.md。

## 接入与边界

Runtime精确组合为GraphHarbor双包0.13.0.post49、LangGraph1.2.24、checkpoint4.3.2、checkpoint-postgres3.2.1、SDK0.4.14、DeepAgents0.7.8。正式四产物哈希与源码范围由[GraphHarbor发布证据](../../../../../graphharbor/docs/projects/20261120-checkpoint-storage-governance/implementation/release-post49.json)维护；平台通过local-stack deps安装，不改site-packages，不依赖引擎源码editable。

Reference Agent和平台助手继续create_agent，仅传DeepAgentState。Dear/Showcase根和实际编译子Agent为Delta50；教学Workflow外层仍为普通BinaryOperatorAggregate/add_messages，本次未迁移，不声称所有图均为Delta。实际compiled断言及原有主子namespace/摘要/队列测试分别覆盖这些事实。GraphHarbor未引入任何平台图名、供应商、工具、Workspace或idle30天常量。

## 真实消息测量

入口：`apps/runtime-service/scripts/measure_message_delta.py`，读取所属登记并校验数据库/角色，在独立schema测量，每个case只回收自身UUID线程。调用公开DeepAgentState的实际compiled消息reducer，和普通add_messages作对照。200轮，每轮Human1KiB、AI工具调用、Tool1KiB、AI1KiB，共800条消息；四组完整消息逐项相同。

| 周期 | 三表逻辑字节 | 读p50 ms | 读p95 ms | 写读总秒 |
|---|---:|---:|---:|---:|
| 普通全快照 | 4,362,489 | 23.494 | 33.121 | 8.268 |
| 10 | 1,573,809 | 35.674 | 62.789 | 9.540 |
| 50 | 1,323,564 | 43.949 | 108.238 | 10.234 |
| 200 | 1,276,373 | 43.369 | 53.294 | 7.836 |

每组20次末尾读取跨不同快照相位；这是本机有限夹具，不是模型端到端延迟或高并发服务SLO。保留周期50减少约70%逻辑字节，但本次读p95高于普通聚合，不能隐藏读取代价或据有限采样宣称50普适最优。100ms预算针对建立Run边界，不能与本表状态读取混用。固定K并永久保留周期全快照仍有O(N²/K)项。

原始数据见[message-capacity.json](message-capacity.json)。引擎维护六组预算、无竞争锁测量及确定性并发屏障见其[容量记录](../../../../../graphharbor/docs/projects/20261120-checkpoint-storage-governance/implementation/01-storage-and-recovery.md)；维护RSS不代表全业务Worker峰值。

## 所属数据库备份恢复

先停栈确认head014、Run为0，再备份。系统pg_dump14连接PG17失败，改用PG17工具。015升级成功后，首次pg_restore --clean被新run_checkpoint_undo到旧baseline的外键阻止，且该次未使用single-transaction，不能宣称原子失败。

随后停止所属栈并读回，确认Run=0、undo=0、head015，只移除确认空的新undo表，以`--clean --if-exists --single-transaction --no-owner --exit-on-error`恢复到014，原审批写入1条保留；再执行015迁移、start成功。专用零Run环境的同库修复不能复制到有业务数据的生产环境。

生产恢复推荐：停写并备份，在独立新目标验证备份与匹配包，再按新迁移前进；失败时恢复独立目标并对账新写入。不得旧包接管新格式、破坏性downgrade或直接--clean覆盖现役。引擎两参数迁移测试另有旧数据、失败回滚、再次转换和逆序恢复证据，平台演练不冒充现役迁移。

## 实际重启与完整链路

所属API/Worker实际子进程来自所属venv，双包post49、head015一致。真实Reference对话成功后分别restart-one API与Worker，两个应用PID均变化；GET state的完整values与重启前逐项一致。随后真实模型续聊正确复述代号，最终4条消息且ID唯一。见[脱敏证据](platform-evidence.json)。

浏览器Reference两轮、刷新、原生edit fork及旧checkpoint保留通过；Dear打开/返回/发送续期且后台读取不续期通过，共2项。三服务保留链1项通过，覆盖30天政策服务端控制、跨项目/未签名回调拒绝、Workspace/ACL删除、文件占用阻止后重试、并发维护及精简墓碑。

截图已实际查看，位于所属私有证据目录；不将含token的Playwright trace提交Git。首次点击发送超时，日志表明悬浮助手按钮遮挡发送；最终使用产品支持的Enter发送，不用force点击，不宣称按钮点击或所有loading视觉已验。

## 故障记录和验证限制

- 原HTTP夹具注册不存在的showcase_graph，首轮3个setup error；按本测试实际图明确只注册dearflow_agent。
- 原夹具Tenant slug与请求的__default不一致，预算鉴权403；修正合成数据，不绕过产品权限。
- 新预算保护拒绝2.5秒硬限下更大的收尾预留；设reserve=0后，硬限又先于图构造完成、模型调用计数为0。改为15秒Run硬限与30秒模型限，使场景真实进入provider等待，最终timeout且仅1次attempt。没有放宽生产门槛。
- HTTP故障首项（工具/模型重试、审批、安全诊断）1项通过；崩溃前后、数据库重试、取消、旧新平台源码重载及硬超时的第二项最终1项通过。旧新源码验证使用同一新正式引擎，不等同旧引擎读取015。
- 宽泛旧P6套件曾43通过/6失败/4deselected，涉及旧Token身份、迁移head与记忆阈值等，未为存储专项修改无关产品或阈值。所需新schema队列独立21项通过；扩大失败仍保留。
- 队列最初20通过/1失败：旧schema模拟未清理新预算触发函数，补原cleanup后21通过。保留链初次删除后activity403断言、并行共用临时项目冲突均修正为真实权限语义与独立项目，最终1项通过。
- 普通单元运行19通过/1个需显式PG开关跳过；随后单独启用PG验证，不把skip算通过。汇总记录见verification和[test-results.json](test-results.json)，重叠套件不相加。
- 严格官方Server逐字段比较仍有既有差异，完整等价、生产负载、任意大Reducer状态和现役切换不在已验结论内。
