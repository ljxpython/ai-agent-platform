# 4GB正式连续评测实测与回退

关联Task23，记录日期2026-11-21，时间均为Asia/Shanghai。此文保存证据与取舍，唯一进度在[原任务](../tasks.md#task-23在4gb主机上完成正式自动评测)。

## 为什么追加验证

用户希望4GB主机不扩容也能在正式EvalFlow一次启动自动评测。系统保留512MiB余量，候选评测另需384MiB物理预算；4GiB Swap只作为缓冲，不计入物理入场预算。

| 候选 | 实际结果 | 资源与恢复 |
|---|---|---|
| A：单并发与有限Swap | 原六轮五指标1.0；客观任务缺产物按原标准failed | 原六轮运行最低399.92MiB，结束后609.165秒窗口最低385.00MiB，不满足余量 |
| B：联合收紧，EvalFlow High256MiB | 健康未就绪 | 自动精确回退，不以active替代可用 |
| C：EvalFlow High384MiB | 三任务正常评分；六轮会话0.4，逐轮/产物0 | 841.604秒/168样本，最低329.50MiB，OOM新增0；排空回退，未启动第四条 |
| D：只追加Redis High512MiB | 前三任务正常评分；第四次暖机取证ReadError | 961.055秒/192样本，最低620.22MiB，Swap使用峰3381.08MiB，OOM新增0；09:25回退 |
| D2：相同预算仅复验一次 | 客观正常failed、两轮passed；第三条六轮被物理门槛拒绝，第四条未启动 | 288.297秒/58样本，最低692.39MiB，Swap使用峰2547.77MiB，OOM新增0；09:34回退 |

D/D2共同应用预算：Runtime API High256/Max384/Swap256MiB，Worker384/512/768MiB，EvalFlow384/512/768MiB，单评测scope320/384/256MiB。Redis只改High512MiB，硬上限/Swap/TTL/noeviction及持久化保持，始终原PID1211，未删key或重启。

## 实际执行与证据

D三任务bf6330ef、9846b264、fd6f129a分别为客观failed、两轮passed、六轮正常failed；六轮会话1.0但逐轮/文件0。14 Trace/510 Span完整分页，代表原文200。第四个0a4d715e的Agent两轮已完成，但Trace收集前DatasetRegistry通过本机MLflow读取冻结题库records遇到httpx.ReadError；原任务error和missing_case保持。未观察到同时段服务重启或OOM，未确定完整传输根因，没有新增重试掩盖失败。

D2任务c980600f客观产物0、completion/原件1；eda4b8ff两轮四规则1。3eb8c32e被入场保护拒绝，无Agent Run或原生Run。已执行任务3 Trace/118 Span完整分页和代表原文200。两个候选均核对14旧资产hash及匿名/错误身份401。D2拒绝说明保住512MiB系统余量仍不代表能再分配384MiB评测预算。

D在09:25:11–09:25:34、D2在09:33:55–09:34:15分别排空后精确回退。D2备份内文件逐字节一致，三应用新PID498036/498038/498040及健康200；Redis原PID1211/NRestarts0、High infinity恢复，配置hash保持。未运行主动BGSAVE和最后10分钟通过窗口，因为连续序列前置失败。 生产EvalFlow Git HEAD仍bc26b58，eval_platform/resources.py与deploy/systemd/mlflow-eval.service两份文件已按阶段A备份恢复，属于本轮已知差异，不声称生产树clean。候选尚未推到远端origin/main；后续部署必须核对实际文件和限额，不能仅凭HEAD判断。

安全摘要保存在所属私有部署目录的budget-d-及budget-d2-前缀文件；桌面报告evidence内有带4gb-前缀的白名单副本。带backup的私有快照、回退tar、curl认证文件没有下载或提交。

## 当前容量线索与下一阶段边界

D2回退后的只读INFO记录Redis逻辑用量1,425,267,984字节、峰值1,928,599,248字节，32个key全部为Runtime Run事件流；部分末条data抽样约200–300KB。单key MEMORY USAGE采用抽样，不能相加替代INFO总量。原数据受TTL自然倒计时控制，没有手工清理。

生产post48源码的langgraph_runtime_pg/redis_stream.py显示，put和put_batch同时在Redis及进程内保存事件正文，按2000条限长；Redis滑动过期3600秒。条数边界不能给出字节上界。这是明确的容量贡献，不能直接断言全部历史OOM或ReadError均由它导致。

下一阶段建议先核对重复正文来源、现有持久事件与断线续传协议，再选择保留语义的缓存压缩或字节预算方案。必须覆盖刷新/重连、慢客户端、审批与取消、完成终态及历史回放。当前授权不包含修改此协议、TTL或依赖，尚未实施或部署；不通过清库、截断正文、删指标或无限重试取得通过。

## 浏览器与报告

原桌面HTML增至15案例、37视频/51截图，C14保留D失败、C15记录D2容量拒绝。原9案例规范化内容SHA256为729c6a58c0ab56e403c306ab535cd3287c13ca71cffa0534c17108091ec48640，保持不变。新增4GB11视频完整解码通过且掉帧0，实际浏览器11视频播放进度及19截图加载共30/30通过；获准置前约7.13秒后关闭自建窗口。历史媒体缺口及录屏分段空档保持披露。

## 分支保存与回退收尾

两仓所属fix/evalflow-4gb-20261121分支已推送，Agent资源候选5125702、EvalFlow产品bc26b58及文档6e226eb均有远端读回。没有推进远端main；本仓主工作区原有AGENTS.md修改及并行Checkpoint保持。Worktree作为未完成工作的源码与证据载体保留，没有创建或删除业务数据库。

09:40:24再次读取确认零活动Run/租约/后台任务/评测，8123/5000/9128为200，2142未认证为401；私有回退文件逐字节一致。仅停止所属资源监测单元，自建浏览器窗口已关闭；正式服务与Redis保持运行。本收尾读回不替代容量Final。

## 结论

本轮候选未满足连续容量，Task23部分完成（partial），联合Final未执行。主分支不合入未通过的资源候选；分支与失败证据可供复核。正式Agent保持post48，未部署并行Checkpoint、迁移数据库或清除生产数据。
