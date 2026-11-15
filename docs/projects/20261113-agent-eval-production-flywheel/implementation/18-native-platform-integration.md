# 07实施与验证：正式平台入口和页面登录

> 日期：2026-11-16。结论：本地批准范围done；任务进度以[07专题](../07-native-platform-integration.md)为准。用户亲自验收待进行，未提交、推送、合并或生产发布。

## 用户现在可以做什么

在EvalFlow左侧点击“评测集”，搜索并找回已有题目、版本和运行；新建、详情和AI编辑都保留平台导航。刷新、前进后退和复制链接不会跳到另一份资料。未保存修改离开前可选择继续编辑或放弃。

进入原生首页、实验或设置时，使用正式登录页面，不再弹出浏览器HTTP认证窗口。评测集继续用Agent平台账号，原生模块继续用已有MLflow账号。用户批准只调整登录交互、保持现有权限；本地测试密码按授权重置并在会话交付，不写入此文档。

## 实际改动位置

代码位于`/Users/lijiaxin/.codex/worktrees/344c/mlflow-eval-platform`；本Agent仓本轮同步项目文档，没有修改Agent服务实现。

| 文件或模块 | 调整 |
|---|---|
| `web/src/MlflowRouter.tsx`、`common/utils/RoutingUtils.tsx`、`workspaces/utils/WorkspaceUtils.ts` | 注册列表、新建、详情正式路由，保留目标地址与工作空间边界 |
| `web/src/common/components/MlflowSidebar.tsx`及测试 | 接入评测集菜单；从实验返回列表/新建/详情时恢复全局菜单 |
| `web/src/evaluation-tasks/AuthoringPage.tsx`及测试 | 拆清页面状态、历史导航、未保存保护、异步回执与task定位；运行数按任务去重 |
| `web/src/evaluation-tasks/PublishedExecution.tsx`及测试 | 使用内部Link回到指定评测集和运行 |
| `web/src/account/BrowserLogin.tsx`、`auth-utils.ts`及测试 | 原生页面登录、保持回跳、服务端退出；退出失败如实提示 |
| `eval_platform/browser_login.py`、`app.py`及`tests/eval_platform/test_browser_login.py` | 短期内存会话、HttpOnly Cookie、来源校验；浏览器不发Basic挑战，SDK原认证保持 |
| `web/src/experiment-tracking/components/run-page/RunPage.tsx`及测试、中文词条 | 处理GraphQL成功响应却没有Run的情况，显示无法读取，结束无限加载 |

没有侵入`mlflow/`上游，没有修改既有角色或实验权限。当前工作区还有此前专题改动，不能把整个Git差异都算作07新增。

## 自动化证据

下列日志均位于EvalFlow Worktree的`.local-stack/`，不是生产测试。

| 范围 | 结果 | 日志 |
|---|---|---|
| account、evaluation-tasks、MlflowRouter、WorkspaceUtils | 16套166项通过 | `07-final-frontend-passed.log` |
| RunPage | 1套8项通过，含GraphQL无errors但run为null | `07-native-empty-run-tests.log` |
| MlflowSidebar | 1套8项通过，含四个返回目标 | `07-sidebar-final-tests.log` |
| browser_login、authorization_batches、authoring_api | 52项通过，2 warnings | `07-final-backend-passed.log` |
| 主类型/shared类型 | 通过 | `07-final-typecheck-after-run-fix.log`、`07-shared-typecheck.log` |
| 改动范围ESLint | 通过，Browserslist提示保留 | `07-final-eslint.log`、`07-login-final-eslint.log`、`07-run-final-eslint.log`、`07-sidebar-final-eslint.log` |
| 最终构建 | 退出0 | `07-release-final-build.log` |

前端三个测试范围不重叠，合计18套182项；退出3项已包含在166内，不重复相加。新后端及其测试Ruff通过，`make guard`通过，两仓`git diff --check`通过。

复验命令（在EvalFlow相应根目录或web目录执行）：

```bash
# EvalFlow根目录
./.venv/bin/python -m pytest tests/eval_platform/test_browser_login.py tests/eval_platform/test_authorization_batches.py tests/test_authoring_api.py -q
make guard

# web目录
CI=true NODE_OPTIONS=--max-old-space-size=8192 ./node_modules/.bin/craco test --watchAll=false --runInBand src/account src/evaluation-tasks src/MlflowRouter.test.tsx src/workspaces/utils/WorkspaceUtils.test.ts
CI=true NODE_OPTIONS=--max-old-space-size=8192 ./node_modules/.bin/craco test --watchAll=false --runInBand src/experiment-tracking/components/run-page/RunPage.test.tsx src/common/components/MlflowSidebar.test.tsx
NODE_OPTIONS=--max-old-space-size=8192 GENERATE_SOURCEMAP=false DISABLE_ESLINT_PLUGIN=true ./node_modules/.bin/craco build
```

构建沿用关闭全局ESLint插件的本地约定，另做范围ESLint，不声称全仓lint通过。Node22运行，未验证声明的Node24；pytest的未知timeout配置和Starlette WSGI弃用警告保留。

## 浏览器验收：怎么走、看到了什么

使用browser-skill连接用户Chromium。原生登录成功、错误密码提示、退出均通过；直接进入`/experiments`后登录仍回到原目标。此前HTTP认证弹窗真实阻塞操作，改为页面登录后恢复。

| 操作 | 实际结果 | 截图（EvalFlow `.local-stack/`） |
|---|---|---|
| 菜单→评测集→搜索“11月退款核对-会话转换验收” | 显示原样本与2次运行 | `07-final-search-list.png` |
| 进入详情，刷新、前进后退、复制链接新标签 | 2题、修订5、8消息和v1/v2仍在 | `07-detail-wide.png`、`07-final-source.png` |
| 1544px/1044px窗口 | 双列/单列正确展示 | `07-detail-wide.png`、`07-detail-narrow.png` |
| 编辑后离开，继续编辑，再放弃 | 输入可保留；放弃后重新打开原文未变 | `07-unsaved-warning.png` |
| 新建页临时输入后返回 | 提醒放弃或继续；最终放弃，未建立草稿 | `07-final-new-warning.png` |
| 带task地址定位v2→完整Session→单轮时间线 | 展开指定运行；四轮/四Run及真实调用树可读 | `07-session-full-view.png`、`07-final-timeline.png` |
| 原生实验29/Run读取 | 权限仍拒绝；不再无限加载 | `07-native-access-denied.png` |
| 撤权专用样本/不存在UUID | 隐藏受限资料并禁用AI；不存在项明确报错 | `07-revoked.png`、`07-missing-item.png` |
| 登录/退出/保留原目标 | 正式页面处理，不出现Basic弹窗 | `07-native-login.png`、`07-logout-login-page.png`、`07-login-return-target.png` |

正式工作项`ce53fafe-b375-5ebb-a932-bb9bcc422c3b`；v2任务`6495ecff-5fa9-4a04-aadd-247ba3c3712e`。本轮只浏览历史结果，没有重新执行Agent或评分，没有撤销正式样本授权。

`flywheel-reviewer`对平台管理的实验29明确DENY，REST返回403，GraphQL返回`mlflowGetRun:null`且无errors。我们修复页面空结果处理，没有放宽权限。原生结果回跳Link由组件测试覆盖，目标task地址由浏览器实测；不声称该账号成功读取原生结果页并点击回跳。平台账号可在受控工作台读取获准证据。

## 录像和交付

桌面沿用`/Users/lijiaxin/Desktop/评测演示/打开演示.html`，新增“11月16日更新”区域；原16步截图、5段业务录像及可复制输入保留。

- 新视频：`07-平台内导航与登录-20261116.mp4`，1920×886，338.009601秒；录制状态complete，手动停止，402采集帧/335掉帧，不能称流畅30fps录像。
- 覆盖：登录回跳、菜单、搜索、来源、历史结果、完整Session、时间线、新建页未保存提醒。录像止于提醒；之后已放弃临时输入，返回评测集入口时平台登录已失效，页面要求重新登录，没有建立新草稿。
- 8张原始PNG放在桌面`关键截图/`，可点击打开原图放大；细节优先看截图。
- ffprobe确认尺寸/时长；ffmpeg全片解码退出0，无错误。HTML静态本地引用全部存在，保留6个播放器。
- 本次更新后的HTML未再做浏览器播放或file双击自动化；原5段的浏览器播放证据不移作新视频证据。
- 首次短录像备份在EvalFlow `.local-stack/07-navigation-before-empty-result-fix.mp4`，最终视频覆盖本轮同名桌面文件，没有删除用户原业务录像。

## 失败过程与剩余边界

1. 浏览器Basic弹窗阻塞点击：经用户批准改为正式页面登录后通过。
2. 最初历史返回断言未等待异步hash恢复；修正等待后通过。登录测试模拟变量命名失败也已修正。
3. 会话容量测试首次51通过/1失败，原因是假设中间件固定第二层；定位目标中间件后52通过，失败日志`07-final-backend-rerun.log`保留。
4. 无权限GraphQL空结果导致无限加载、返回评测集残留实验子菜单：均已修复并补测试、浏览器复核。

会话最长1小时、最多1024个，凭据仅保存在限时进程内存，退出/重启失效。当前方案仅用于单worker；多worker必须先接共享会话管理，代码有`shortcut:`说明。到期/来源/容量等边界由后端测试覆盖，未等待真实一小时计时试验。未统一身份、未生产部署、未做正式性能/真实CI/独立盲测；原暂缓范围保持。

操作手册已更新到真实菜单位置，并提供“不重跑模型，先用5分钟检查页面整合”的步骤。用户验收结果仍由用户填写。
