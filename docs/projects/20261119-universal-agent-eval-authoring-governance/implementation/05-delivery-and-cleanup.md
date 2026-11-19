# 主分支交付、合并后验收与资源回收

2026-11-19，用户明确授权经验沉淀、停止所属服务、Worktree提交推送、保留既有功能合并main、main推送、合并后全链路验收和测试资源清理。唯一进度见[Task5](../tasks.md)，本文保存实际Git、验收和清理证据，不另建进度清单。

## 交付前事实与保护范围

EvalFlow主仓 `/opt/mlflow-eval-platform` 位于 `10d400aa35a341b1a149846a6750a939d7f86974`，与origin/main一致，工作区干净；Worktree基于 `f7a087f20c6cb221f90d62c094e51a3201c23b80`。两者只差管理员访问修复 `eval_platform/access.py` 和 `tests/eval_platform/test_access_boundary.py`，本任务不覆盖这些文件。f7a087f的一级评测集和一键发起评测、之前的删除及管理员登录功能须保留。

Agent仓主分支 `da43053e` 与origin/main一致，未提交变更为本项目文档。Mac EvalFlow镜像另有未跟踪 `tests/run_authoring_demo.py`，不属于本次交付，不纳入提交或删除。另一个预算治理Worktree不属于本次清理范围。

本次EvalFlow与Agent均复用生产PostgreSQL；EvalFlow鉴权配置也引用主仓原生鉴权库。没有创建本轮独立PG库、角色或SQLite库，不能删除共享生产库来冒充测试库清理。合并回归将指定本轮临时目录保存pytest数据库，结束后只清理该目录。

私有交付证据固定保存于 `sshmy1:/opt/mlflow-eval-platform/.local-stack/deliveries/20261119-universal-authoring/`；原验证日志、模型批次和预算修复记录归入 `pre-merge-evidence/`，不提交凭据、配置或原始Trace。

## 合并与回归

Worktree提交 `50c2d26cc2dd33fb3dd9c90ee435046ec9ef61d9` 已推送远端同名分支。主仓通过普通双亲合并形成 `0291419199174eb52dbbc3f4f8e985d9baa0b190`，原管理员修复 `10d400a` 与本次提交均为祖先；没有用目录覆盖或重置替代合并。管理员实现/测试、题库API文件哈希、整个web与mlflow树哈希均与合并前一致。

合并后的主仓独立虚拟环境实际导入主仓源码，原扩大范围重新执行结果为 **689 passed、21 warnings、29.60秒**，包含主分支新增的两项管理员权限测试。18份Python语法、脚本语法、增量Ruff 0和上游零改动检查通过；59条未改行Ruff诊断保留。首次提交差异检查发现两份文档末尾空行，收尾时修正后复验，不掩盖首次失败。

完整原始结果保存在交付目录的 `merged-regression.log`、`preservation-after-merge.json` 和 `merged-static-checks.json`。合并版临时服务由主仓Python和cwd启动于5011，使用所属私有state，不覆盖生产任务目录。生产四服务继续运行。

## 合并后的完整业务验收

2026-11-19 13:41（Asia/Shanghai）执行独立Final回读，结果为passed。使用合并后的主仓源码、真实认证ASGI平台入口、实际HTTP Agent API/Runtime/EvalFlow及真实模型，完成合成会话交付、出题、修订、用户委托AI复核采纳、独立发布、历史评分和显式新运行。合成文件为用户消息中内联YAML，不称浏览器文件上传、来源Agent实际推理或独立人审。

文本工作项 `26f59818-5dcb-52fc-90dc-33e193a55c37` 修订3发布为 `d-fa868c9985e14eb0bc4d83b9cf4041cc` v1；文件工作项 `ec9afc3f-9530-570c-9a4e-b0335d793015` 修订2发布为 `d-619ebbc959524305813c3fd6b0709d66` v1。发布均不创建task，候选采纳审计、来源hash、原始用户输入及旧版均回读确认。历史评分时配置仍为不可运行的 `offline_authoring_reference`，文本和文件任务分别为 `87988864-dccc-42dd-b301-5544bf7d65b5`、`72c7ebf7-b76c-480a-afa8-0987e38d4d99`，均passed；两类来源Run前后均为空。

单列混合证据任务 `0f629cd9-d29c-4a3c-bd20-db338d011a49`：ConversationalGEval=1.0/pass，ToolCorrectness因缺tools为missing_evidence/error，整体error准确表示不完整；没有因此重跑来源。随后显式切换支持的dearflow目标并单独发布运行版，新任务 `bbd5de5b-83bc-4082-8a67-3f5247fd5f1c` passed，ConversationalGEval=1.0，回答正确说明周日不提供人工服务。

| 新运行证据 | 独立接口回读结果 |
|---|---|
| Session | `9ba13aa9-34fb-43b7-8617-ff1edee77de3` |
| Runtime Run | `c3f4912f-da46-44e7-a59c-715edcddf497`，success |
| Trace | `tr-5955bc9da47cfab4515c599e447a448b`，OK，21 Span，complete=true |
| 目标身份 | spec、Agent/资源/配置hash、部署包、项目、图、模型、Session及Run一致 |

Final另核对原开发资产及旧版hash保留，18份源码/测试hash从出题到运行结束保持冻结。真实原生管理员访问200、匿名访问401；管理员实现和测试、题库API、前端树均保留，既有删除接口测试包含在689项回归内，一键发起沿用的发布/显式运行链已实际验证。没有把代码保留等同于重跑浏览器全部交互。

原第12批十题质量证据按相同源码复用，不把本轮两条集成样本加入其分母。保留三类本轮过程记录：单checkpoint导致来源历史不完整，通过正常state update生成第二checkpoint后重新交付；AI修订反馈把文件限制带入纯文本标准，复核仅删除两处无来源文件条件后再发布；清理前首次本地远端跟踪ref缺失，在任何删除前退出，随后通过ls-remote核实远端真实分支hash。均未改产品以迎合检查，也未伪造来源完整性。

新证据位于交付目录 `acceptance/complete-e2e/`：`operations-summary.json`、`delivery-final-summary.json`、两类发布与历史结果、混合证据结果、`final-runtime-run.json`、`final-session-trace.json`。初始不完整来源及修订记录保留在 `acceptance/e2e/`。原失败不覆盖。

## 服务与测试资源回收

先验证369份原Worktree非缓存证据与归档哈希一致，再按PID/创建时间/cwd停止主仓临时验收进程。5011、9138均无监听；原45011专属隧道已停止。四项生产服务身份及NRestarts与交付前完全一致，EvalFlow仍MainPID2115014、NRestarts0，生产5000健康200。

在工作区干净、实现分支已推送且为main祖先后，已通过git worktree remove回收 `/opt/worktrees/evalflow-universal-authoring-20261119`，仅清除其登记；独立虚拟环境随目录回收，远端实现分支保留。其他Worktree不在本次范围。

合并回归指定的 `pytest-temp/` 内10个SQLite测试库及整个临时目录已删除，没有保留数据库副本。本轮未创建专属PostgreSQL库；共享生产 `evalflow_db`、共享原生鉴权库和生产资料保留，不能删除它们冒充测试库清理。私有日志和Trace保留在受限交付目录。清理事实见 `cleanup-summary.json`、`worktree-remove.log`、`registry-clean.log`。

## 交付边界

本次没有新增产品修复，因此合并验收后只更新文档，不机械重跑模型或回归。实现分支50c2d26已推送，普通合并0291419后，最终文档提交 `9373c1e4d74173d0fe7bf0218c3044c9215e1364` 已推送EvalFlow origin/main，远端主仓干净。Mac镜像已快进至该提交，用户原有未跟踪 `tests/run_authoring_demo.py` 哈希不变；Agent仓同步项目、摘要和获准经验，不改产品代码，随本次文档提交推送。最终两仓同步及清理状态再以Git/服务实际回读确认。

未重启生产以部署新版；本轮通过的是主分支源码的所属临时服务。未重跑完整浏览器交互、独立人审/盲评、大规模压测或数据库回滚。未配置预算策略的警告仍保留，出题更高输出/超时上限可能增加等待与开销，十题单模型结果不保证任意Agent的普遍质量。本项目没有需要毕业的新增标准草案。
