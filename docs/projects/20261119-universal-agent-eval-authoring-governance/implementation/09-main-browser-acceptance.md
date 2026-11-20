# 合并版浏览器验收与报告（Task14）

日期：2026-11-20。当前为阶段证据；唯一任务进度在原tasks.md，最终浏览器验收尚未完成。

## 合并与版本

Agent正常合并提交dbc656a9；EvalFlow远端正常合并69d0584。EvalFlow原有7d3cb7f和0a5b89b并行修复均为合并版祖先，未覆盖产品目录；Agent主仓AGENTS.md原有改动逐字节保留且未提交。Runtime所属Worktree已同步main，API／Runtime及Web使用登记环境wt_644e8a066eac，Web27968／API25075／Runtime26631。EvalFlow所属5011通过9138访问；正式生产进程没有重启。

Mac前端构建同步到所属远端的生成目录mlflow/server/js/build，不改上游跟踪源码。HTTP页面实际返回main.bf3f6555.js，asset-manifest SHA256为983521c386d184edbe156d5ca9ae564aa70af3d0ae7f6e88a5355b81877506f1。

## 合并版回归

- EvalFlow原57套后端清单重新执行：756 passed，27 warnings，25.79秒。
- Runtime工具流式专项：7 passed，2 warnings，5.95秒。
- 前端4套41 passed；类型检查通过。默认build因既有全局lint失败；DISABLE_ESLINT_PLUGIN=true后的编译通过，两者不混称。
- 来源修复关联回归：157 passed、2 skipped、499 subtests passed；另2项工作区缺文件错误文案断言失败。临时使用HEAD原源码及相同身份夹具重跑，两项仍以相同“File not found”与“Workspace file unavailable”差异失败，修复源码已按哈希恢复。不是本次新增失败，不改无关错误文案。

## 来源长会话转换问题

浏览器打开六轮会话77761538-99f1-4da8-b0bf-ceb9d2e8cd17并点击转为评测集。POST在17:48:29返回202，约60秒后的Runtime读取401，通知明确显示转换未完成。页面直接读取同一会话为200。

调用核查发现：后台复用get_runtime_gateway_service产生的网关。大部分state/history已逐次签发，但_load_thread、list_thread_runs及get_thread_execution_evidence的原生Run读取仍使用初始委托。补测试令旧upstream凭据过期、只有重新签发的upstream可读，原源码先失败，最小修复后通过；同时确认无权用户在签发前拒绝。复用_thread_upstream，不增JWT claim／operation，不延长有效期，不放宽Runtime校验。图片／文件测试补核对先read、再用途委托；真实双服务测试延续原锁定身份夹具。

## 客观用例首次尝试与漂移保护

浏览器新建b7978d95-81c1-41fc-b90f-e3076fbecb6b，材料通过产品粘贴文本资料逐一添加六表；原生文件选择自动化被CDP拒绝，未称上传通过。完整配置导入已冻结的objective-case，保存修订2，三规则分别是completion、artifact_correct、protected_unchanged，没有模型裁判或动态模拟。主动授权发布题库v1，页面显示已发布尚未运行，然后显式点击运行。

任务ab32aebe-d8d8-486d-a987-7b7299d5b2fb、Session9d366044-3bf3-4762-88c0-8f8982e3dc24已真实运行。此时为修复来源问题修改API源码，工具write_file恢复前被target_configuration_changed阻断；停止回执no_active_run／not_required。该次不是业务通过证据，原失败保留；修复合入、重启并冻结产品源码后另发完整验收。全屏Trace窗口、退出和原始错误展示实际可用。

## 媒体与剩余验证

用户选择桌面独立目录。已保存5段MP4，均complete／user_stopped、0 dropped frames；ffprobe确认H.264及有效时长。视频包含首次来源失败、六表材料配置和发布、漂移保护与全屏结果回看。长运行分段，录屏间隔如实标明，不能称连续全程。

待完成：来源修复浏览器复验；冻结版本后的客观任务、固定澄清／计划／分轮材料、同证据重评及失败检出；逐例HTML、截图／录像播放检查；最终任务摘要、Git与服务身份核对。
