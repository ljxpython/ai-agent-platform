# 正式接入补验、生产切换准备与资源回收

关联 P07–P09，日期为 2026-11-21。本文记录阶段证据；生产执行和旧专项整体验收仍按各自任务判定。

## 当前修复与补验

GraphHarbor 的 baseline 外键、线程 PATCH 422 与跨 topic 事件误去重已修复，源码 84e9021 的远端 CI44840687787 七项通过。正式双包 post50 已发布；四产物独立下载哈希一致，正式安装真实 PG/SDK/CLI 41 项与三客户端取消 24 场景通过。原失败保留于引擎原阶段记录，不再作为当前未修问题。

平台已通过 frozen 锁文件接入正式 post50。消息/助手审批分进程恢复 6 项通过；消息队列 23 项通过、1 项可选真实模型探针跳过。夹具补齐产品正常读取的 deletion_requested_at 列，没有修改产品生命周期判断。

八类真实浏览器全部通过（50.603 秒）：文本及刷新、reasoning 独立折叠、usage 有无、工具参数分片/失败重试及 call/result 配对、子图局部失败、审批恢复、410/离线恢复、显式 v2。浏览器使用确定性测试模型，经过真实平台网关、正式 Runtime 与 PG；另有真实模型 Reference/fork 验收，不能将两者混称。流分片/usage/子 namespace/审批 ID 夹具自检 1 项通过。

首轮登记工具忽略外部 graph 配置，实际调用真实模型，8 项失败；改为所属栈临时配置并增加图身份断言。第二轮 5 项通过，原审批 Run 为 interrupted 而恢复 Run 为 success，测试错误要求所有历史都 success；另两项 5 秒建会话预算不足。修正断言与启动预算后三项复验通过，随后完整八项通过。原生产图配置已逐字节还原，API/Worker 已更换实际子进程为 57256/57810。来源与脱敏结果见 [followup-post50.json](followup-post50.json)。

引擎官方固定版本与正式 post50 各完成 42 个 HTTP 场景，跨用户资源保持，状态差异逐项记录；新增 8 Worker 同时运行与维护/外部写/竞争 claim/回滚测试通过，完整变更安全套件 18 项通过。范围和限制留在其原安全专项，不称严格官方等价或无限并发容量通过。

## 现役只读预检（切换前历史）

通过现有 SSH 运维入口检查，现役源码为 6165026c，GraphHarbor 双包 post48、LangGraph 1.2.11、Schema 014_thread_retention。Runtime API、Worker 和 Platform API 均 active，NRestarts 为 0；Run 为 success 43、error 3、interrupted 1，没有 pending/running。

实际 Runtime 库为 `graphharbor_acceptance`，约 10,177,697,459 字节。它是现役业务库，名称不作为测试资源证据。最大表 `runtime_events` 为 10,125,402,112 字节；checkpoints 约 14.3 MB、checkpoint_writes 约 12.2 MB、旧 run_checkpoint_baselines 约 2.34 MB。旧 baseline 共 46 条，压缩后单项 projection/checkpoints/writes 最大分别为 12,673/370,338/154,043 字节；压缩尺寸不代表迁移峰值内存。

根盘约余 18 GiB，可用内存约 0.74 GiB，swap 已使用约 0.62 GiB。本次 checkpoint 改造不会自动清空 runtime_events，也不以现役机器运行压力夹具。

生产仓库存在原有两份私有锁文件改动及未跟踪配置、部署脚本。切换不得使用 reset/clean 覆盖它们；需先留存内容及哈希，再制作最小目标变更。

## 切换顺序与后续执行

1. 已完成：锁步正式 post50 的本地/远端门禁、四产物哈希与正式冷安装。
2. 已完成：所属 Worktree 接入正式版本并完成补验；旧 v3 与安全专项在原任务留证。
3. 记录明确的现役目标、短暂停写范围、匹配版本与恢复步骤。优先将备份恢复到独立目标，核对旧数据与匹配 post48/014 可读；再在独立目标演练 015 转换。生产停写、安装、迁移或切换需取得该具体操作授权。
4. 受控排空并停写，执行最终备份后转换；API/Worker 只使用与 Schema 匹配的新包。失败时保留失败目标，切回验证过的匹配旧目标；不直接 downgrade，不覆盖恢复到已有新写入的现役库。
5. 启动后核对真实 PID、导入来源、Schema、旧会话可读/可续聊、权限拒绝及新 Run。记录容量边界，不将短时验证称为长期容量通过。

上述预检后，用户批准独立副本恢复及具体生产窗口；现已完成最终备份、服务端014恢复及现役015切换。固定Runtime源码5d3e2418通过独立post50安装加载，原私有配置/锁/脚本保持；仅用systemd覆盖切换Runtime，现场补消息授权回调。Platform数据库和前端未升级。完整来源、时间与结果见[生产执行证据](production-cutover-post50.json)及[操作单执行结果](../production-cutover.md#本次生产执行结果)。

关键验证1080.765秒，首次暂停新请求260.272秒；旧52个Checkpoint头及pending writes、91组投影/边界头和10,299条undo通过。真实Reference首轮API建立后浏览器续聊/刷新/fork、Dear续期、队列幂等/取消/审批及权限拒绝通过。空白Reference首发仍无请求，不能以续聊替代入口验收。新写入已发生，禁止直接切回014。

生产验收12条删除任务中10条核心数据已清除，3条inbox正文为空；2个空Dear线程与1个远端Workspace仍受保护。缺签名回调阻止after_delete完成，全局补齐又会继续原14条业务删除任务，需先明确范围，不绕过保护。本轮短时资源正常不代替评测Task23或长期容量验收。

## 合并后的清理清单

平台唯一所属环境为 `wt_3b7f1734875d`：runtime/platform 双库及同名角色、Redis、Workspace、PID、日志与私有证据。登记端口为 Web 25044、API 23380、Runtime 27909、Redis 24438。必要补验及合并后回归已结束，所属资源现已回收。

必要脱敏结果保存后，通过原生 local-stack 的 stop 和带准确 ID 的 destroy 回收；确认无所属进程、监听、数据库/角色和 registry 登记。永久项目证据、源码、主工作区 AGENTS 修改和其他 Worktree 资源保留。GraphHarbor 本轮一次性 PG/Redis 随 runner 结束回收，最终另查所属私有日志和临时安装目录。

2026-11-21实际执行stop/destroy并独立核对PG目录、四端口、registry与目录不存在。GraphHarbor本项目约266MiB临时安装/产物和平台浏览器报告/dist已删除；现役三服务active，共享Redis与用户AGENTS/stash保持。脱敏结果见[回收证据](cleanup-post50.json)。
