# 看得清、找得到的验收演示

日期：2026-11-15。关联：06 Task6.12交接优化、Task6.9执行定位展示。状态：本轮整理与局部修复已完成（done）；用户亲自验收尚未代填，生产未发布。

## 用户这次需要什么

旧交付在桌面散落很多长视频，大页面缩小录制后字段难以辨认。用户确认保留一个简洁HTML，播放清晰录像并展示关键截图；还要能进入真实平台自己操作。此次只整理交付材料，并修复录制中发现的一个布局问题，没有重设计业务流程。

## 现在怎么用

双击 `/Users/<name>/Desktop/评测演示/打开演示.html`。

- 12步截图各有“在哪里、怎么做、看什么”，支持切换、每10秒自动播放及完整原图。默认是忠实裁剪的操作区域，按原始像素显示，可以滚动查看。
- 3段MP4总计718.535秒，约11分59秒。尺寸均为1384×902，没有标成1080p，也没有通过放大旧视频假装恢复细节。
- “我自己试一次”提供两轮算式需求、AI修改意见和真实平台入口；复制失败时选中文本提示用户按快捷键复制。演示页本身不发API请求，不替用户创建、授权或运行。
- 第1、2段为本轮新建与运行。第2段保留原片前131秒，完整原片在工作区保存；第3段先看修复后的本轮时间线，再查看已有来源与复杂结果。没有将历史查看包装成新运行。

## 新运行的实际结果

评测集：`06清晰演示-两轮算式-20261115`。

| 标识 | 实际值 |
|---|---|
| 工作项 | `2fd55bc6-7f99-4da2-a1e1-aa1412f26e26` |
| 任务 | `56c1ac12-c9b9-4ad5-b125-39511f919676` |
| 执行Session | `0721571f-18e0-4e08-b624-afeeb987f013` |
| 第一轮Run | `fdbc29a2-dd93-4349-ac5a-260369bfd4dc` |
| 第二轮Run | `4cfc5521-cfe7-4303-a2aa-b13c754ac563` |
| 第二轮Trace | `tr-83333e29a3f49f54534761b79e51088e` |

实际回答55、45；逐轮预期2/2、零工具规则通过。发布后先显示“尚未运行”，再显式启动，结果保存在题库v1的运行历史中。browser-skill点击演示页的样本链接后，新页显示正确名称、任务编号与“通过”。授权到期后应新建样本，不能修改旧期限绕过限制。

复杂结果仍如实保留：B04任务`fed53969-129c-4834-9fde-bdc963fefd3d`先写出1800/300/1500报告，再请求未授权execute而失败；文件正确不改变总体error。B03任务`10822d5b-2c6f-4b61-899b-ca887558fcd8`的裁判记录可展开。第三段只查看这些旧结果。

## 时间线布局修复

文件：EvalFlow Worktree `web/src/evaluation-tasks/ExecutionSession.tsx`，`timeline-${prefix}`容器。

原容器只有固定高度与margin，原生Trace查看器使用flex布局时向外溢出，覆盖下方评分。为父容器补上`display: flex`、`flexDirection: column`和`overflow: hidden`，让内部查看器在固定区域内滚动。没有修改执行、评分、鉴权或上游`mlflow/`源码。

复验截图：[时间线与评分分开](phase06/readable-07-定位本轮执行时间线.png)、[实际模型节点](phase06/readable-08-定位实际模型节点.png)、[演示页布局](phase06/readable-player-review.png)。第2段原片包含修复前排查，桌面版本截到131秒，修复后的时间线操作见第3段，避免把旧布局当成现状。

## 实际验证与限制

| 验证 | 结果 |
|---|---|
| ExecutionSession组件测试 | 1套4项通过，16.697秒；不是再跑先前的18项全套 |
| 类型与范围ESLint | 通过；日志仅有既有Browserslist提示 |
| 前端构建 | `node scripts/compile-i18n.js` 后执行 `GENERATE_SOURCEMAP=false ./node_modules/.bin/craco --max_old_space_size=8192 build`，exit0，Compiled successfully；保留旧Browserslist和体积建议 |
| 上游与格式 | `make guard`通过，`mlflow/`无修改；两个Worktree的`git diff --check`通过 |
| HTML与素材 | 所有静态资源存在；12原图与12局部图齐全；3个视频ffprobe可读，ffmpeg全片解码无错误 |
| browser-skill实际界面 | 截图下一步/选择步骤/自动切换及暂停可用；复制提示“已复制”；样本跳转打开正确工作项与真实结果 |
| 视频浏览器检查 | 三个视频元数据与首帧加载正常；初次未激活标签页导致立即暂停，切回Agent窗口内的演示标签页后，逐段实际播放，currentTime推进且paused=false、无媒体错误。全长无损坏由解码检查覆盖，没有声称逐秒人工看完 |
| 本地文件打开 | browser-skill拒绝自动导航file URL，因此使用临时本机HTTP服务验证同一HTML。相对路径和内联脚本不依赖服务器；手动双击播放仍由用户验收 |

没有重跑未修改的后端全套测试，没有新增生产部署、CI、性能或独立盲测结论。原06联合验收证据不被此次演示替换。临时预览服务只监听127.0.0.1，验证后停止；两套业务服务保留运行。

## 桌面清理与恢复

先逐个核对旧视频SHA256，才按白名单移动：26个旧MP4，277,880,377字节；另有2个被替代的旧HTML。全部进入 `/Users/<name>/.Trash/评测旧录像-20261115-204727/`，没有永久删除或清空废纸篓。

34份旧截图、说明与回执移到Agent Worktree `.local-stack/acceptance-presentation/历史截图与回执/`；其余16项桌面文件或目录的大小和修改时间核对未变。桌面本任务只剩`评测演示/`，旧播放器标签页可能仍显示缓存，应重新打开新入口。

服务收尾检查：Agent四个进程及Redis运行、ready通过；EvalFlow前端9138返回200，后端5011鉴权探针返回401，已登录浏览器能正常读取真实工作项。

`评测演示/清理记录.json`逐条记录原路径、恢复路径、大小和SHA256，工作区另存`cleanup-result.json`。新素材清单见[readable-demo-manifest.json](phase06/readable-demo-manifest.json)；旧`video-manifest.json`仅是清理前的历史清单。

本轮原图、完整原片、生成脚本、浏览器观测和素材探测保存在Agent Worktree `.local-stack/acceptance-presentation/`。前端测试、类型、lint、构建日志位于EvalFlow Worktree `.local-stack/acceptance-presentation-*.log`。README、06任务/验证、人工手册、回放说明、CHANGELOG及两仓CONTEXT已更新当前入口，不把旧路径继续作为交付承诺。
