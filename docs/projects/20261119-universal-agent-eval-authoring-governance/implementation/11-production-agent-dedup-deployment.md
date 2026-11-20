# 正式 Agent 采集去重部署记录

用户于2026-11-21要求执行生产部署，让正式Agent加载此前已合main、已在独立环境验证的Runtime采集去重。本轮完成源码快进、受控重载和真实采集验证；不新增产品代码。唯一进度在[Task22](../tasks.md#task-22正式部署并验证-agent-采集去重)，独立[生产Final](../verification.md#整体验收final正式采集加载)与阶段证据分开记录。

## 部署对象与保留内容

目标是sshmy1正式Agent主仓及其原有三个systemd单元。部署前版本`7766173edf259c7d58d8087d492bec56ec4b21c7`，正常Git快进至已验main `0a2f93ca6be4852b0afe7617af139d473708e8fb`。主干增量包含Runtime去重/工具名称兼容及已验证的Platform API来源/网关修复，三个进程须共同重载，避免启动包指纹不一致。

生产已有两个uv.lock改动、私有env、启动包装/备份脚本及未跟踪文件均保留，十份文件SHA前后一致。GraphHarbor及Runtime双包仍为0.13.0.post48，五个注册图保持；未安装依赖、迁移数据库、重建前端或重启EvalFlow/日志容器。原有1个interrupted Run没有被恢复、取消或删除。

私有证据和备份位于正式Agent仓根目录的`.local-stack/deployments/20261121-runtime-dedup/`，目录权限0700。`before.json`保存版本、保留文件摘要及服务身份；`rollback-files.tar.gz`包含原源码和现场配置，权限0600；`worktree-before.patch`和`worktree-before.txt`保存原改动。备份含私有配置，不提交Git。

## 受控更新与回归

只读确认活动/排队Run、有效租约、后台任务、回调、消息与待送预算事件均0后停止入口，再核对无活动任务，停止Worker。Git正常快进成功，Runtime专项16 passed；Platform扩大专项49 passed、2 failed、305子断言通过。两项失败都是缺失文件返回`File not found`，测试预期`Workspace file unavailable`。

脚本首次保护性恢复旧应用源码并启动服务，健康200。使用部署前7766173e原测试、原应用源码和同一环境实际执行，两项文案失败均复现、无跳过；未为过关改测试或错误契约。初次把测试放私有目录导致2 skipped的尝试不计通过。再次排空、恢复main七份应用源码、执行相同回归，仍只有这两项既有失败，确认没有新增失败后完成加载。`deploy-events.json`保留全过程，回退未触及业务数据库。

三个新进程启动于2026-11-21 00:57:22（Asia/Shanghai）：

| 单元 | 新MainPID | NRestarts | 最终状态 |
|---|---:|---:|---|
| agent-platform-api | 178977 | 0 | active/running |
| agent-runtime-api | 178973 | 0 | active/running |
| agent-runtime-worker | 178975 | 0 | active/running |
| mlflow-eval（本轮未重启） | 134216 | 0 | active/running |

正式API返回的Runtime包SHA256为`237f40e3af46eda14384593e89788475865c0200f6b6d138a60bfa68a2fccfc4`，与实际Worker新Trace一致。tracer文件SHA256为`6d25410bfc829c78d1b5f8a5e0a6a83108e4731f2122df04d09003a51f4ac210`，与已验合并版相符，不能只凭磁盘文件判断加载。

## 真实采集与独立验收

先通过正式EvalFlow正常HTTP导入并发布独立两轮合成用例，题库`d-ecabf3e2b9704011a556ffb411bb2357`。任务`555ae0cd-279a-4f8f-8767-e1fca470bac5`在执行前被主机内存保护拒绝：约840MiB可用，低于评测512MiB加系统512MiB门槛；error_code=host_resource_unavailable，completed=0、records为空。该失败保留，没有放宽保护或绕过调度启动评测Worker，也不称该自动任务通过。

随后通过普通平台聊天API验证现有Agent进程，不启动新增评测Worker或裁判。合成会话`2190c6f2-456c-48e2-a458-3b8e4faa4d61`首轮上传12.50/7.25两行CSV，第二轮才补2.25一行CSV，实际各调用一次read_file，结果19.75/22.00，原件SHA保持且没有写文件工具执行。首轮上游504后由原恢复流程继续；验收脚本首次漏识别分块回答，按现有message_text读回，不重跑首轮。

| 轮次 | Runtime Run | Trace | Span | 存储正文（字节） |
|---|---|---|---:|---:|
| 1 | f1872c4b-e9d3-4576-9bae-a421ac9d9713 | tr-c26233bb1f30897641c8b1c5c36b8463 | 37 | 428430 |
| 2 | 41a9c529-dd2f-4d67-adcc-35bc34c9d978 | tr-d8d0cdfc14509c8e35c85f3ca5be2df6 | 36 | 349995 |

完整读取73 Span：64内部CHAIN的输入/输出为小引用，payload_recorded=false；2根、4次成功LLM的输入/输出和2次TOOL原文保持，另1个失败LLM及异常事件保留。原生有界Trace入口认证读取通过；该全局入口不附加Agent连接头，首次错误附加server头的404不算产品通过。

01:10起重新认证、读取全部Span、真实结果和旧资产，独立主机22项/业务16项均通过。四份旧资产hash和三条旧任务HTTP状态保持；Platform匿名/错误Token401、错误项目404，原生Trace匿名/错误凭据401。API、Runtime、EvalFlow5000/9128和Loki健康200；三个新Agent进程及原EvalFlow、四个观测容器身份保持。Runtime旧error=3、interrupted=1保持，success由41增43，活动Run/有效租约/后台任务均0。本轮cgroup与内核日志无新增OOM。

首轮171次采样最低594716KiB、swap468520→551464KiB；第二轮17次最低723192KiB、swap550696→549416KiB。随后60秒61次采样最低689068KiB，swap固定560976KiB。仅为短窗口；首轮增长及主机其他进程影响明确保留，不称长期稳定或全程无swap增长。

## 证据、回退与未覆盖条件

私有目录保留`runtime-regression.log`、两次Platform回归及旧版对照、`normal-chat-ids.json`、两轮state/Run/原件检查、两个原始Span JSON、`normal-trace-summary.json`、资源采样及`production-final-host.json`/`production-final-business.json`。初次Final的状态空白比较、错误LLM代表选择和资源错误码预设失败另存`*-initial.json`；修正验收脚本后重新读取实际内容，不修改产品。所有证据及原失败均保留。

需要回退时先停止新增负载、排空Run并停止三个Agent单元，从备份恢复本次涉及的应用源码，按Runtime API→Worker→Platform API启动并核对健康。保留env、uv.lock、资源保护及数据库。首次保护性回退实际执行并恢复健康，但没有为回退数据库、依赖或前端作验证。源码临时恢复后Git HEAD可能仍为新版本，必须明确记录并通过正常Git流程整理，禁止reset覆盖现场。

本次未重跑完整六轮、长期容量或新增浏览器录屏，原HTML不冒充本轮录像。两项网关错误文案差异、一次模型上游504和新增EvalFlow任务容量拒绝均未修复，不影响已证明的新采集加载，但会影响当前自动评测可启动性和调用时延。后续文档提交只同步记录，不改变应用包或重新重载。
