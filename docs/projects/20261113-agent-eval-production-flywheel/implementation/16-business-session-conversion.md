# 16｜从Agent平台的业务对话直接生成评测集

> 日期：2026-11-15。两个344c Worktree本地实现，未提交或生产部署。任务状态以[06专题](../06-session-to-dataset-and-ai-authoring.md)为准。

## 为什么改

用户想留下的是Agent平台里已经完成的一整段操作，而不是到评测平台重新描述一遍需求。原来的合成声明、手动授权后再点生成、原始JSON和不准确进度提示让流程显得割裂。本轮保留两个平台的职责，缩短资料交接和首次出题操作。

用户明确允许使用获准业务会话，并澄清“线上”就是Agent平台实际对话。本轮自行构造11月退款核对场景，用真实Agent和获准xiaok DeepSeek完成四轮对话；金额虚构，没有接入生产客户资料。

## 改动覆盖到哪里

路径分别相对于Agent和EvalFlow两个Worktree。

| 位置 | 本轮改动 |
|---|---|
| Agent `apps/platform-api/src/platform_api/modules/evaluation/materials.py` | 业务/合成类别、资料用途确认；授权检查先于源读取；稳定请求身份串起资料、授权和首版生成，网络失败可重试 |
| Agent同目录 `privacy.py`、`workbench_grants.py` | 递归处理常见邮箱/手机号/身份证，拦截密钥；NFKC仅用于标识匹配，不改正文标点、全角文本和代码；业务授权需用途确认；人工编辑拒绝未脱敏标识 |
| Agent `apps/runtime-service/src/runtime_service/observability/evaluation_environment.py` | 初态同时支持业务与合成类别，保留路径、期限、回执和授权保护 |
| Agent `apps/platform-web/src/modules/evaluation/`、聊天顶栏及侧栏调用处 | “转为评测集”、用途确认、管理员自动衔接生成、普通成员只交付资料、失败重试沿用请求编号 |
| EvalFlow `eval_platform/work_items.py`、`evaluation_assistant.py` | 记录真实资料类别和用途；只向整理模型提供获准可见正文，不默认发送推理内容/工具返回；完整题目JSON格式、可读错误、自足文字环境、已有草稿不退回ready |
| EvalFlow `eval_platform/contracts.py`及上述生成格式 | 固定多轮题支持完整逐轮断言或有明确criteria的ConversationalGEval；拒绝无评分标准、部分断言、空criteria。自然语言不再被迫使用关键词硬匹配 |
| EvalFlow `web/src/evaluation-tasks/AuthoringPage.tsx`、`SourceMaterials.tsx` | 可读来源、消息数量、自动首版进度、AI修改建议、发布用途确认；运行中显示运行状态；撤权禁用AI输入；纯语义题增加轮次不塞入空断言 |
| 对应后端与组件测试 | 资料分类、授权、脱敏、幂等、生成、语义标准和撤权界面回归 |

复用现有队列、版本与授权批次，不增加新的题库或身份体系，不改`mlflow/`上游。保留策略标识`local-synthetic-20261114`是已有技术ID，本轮允许其管理获准business类别；资料本身并未伪标synthetic，也没有因此绕过清理。

## 实际走完的链路

1. Agent平台四轮：澄清退款月份口径 → 确认1700/1800 → 追加50元退款更新1650/1750 → 纠正净额/利润与无证据归因。
2. 点击“转为评测集”，确认业务资料用途；来源4轮8条消息进入EvalFlow，自动生成首版。
3. 在EvalFlow提出修改意见，保留四轮题，并增加“退款金额缺失时先追问”题，增补完整对话和证据边界评分。
4. 发布v1并真实执行。两题分别产生4Run/4Trace和1Run/1Trace，均有独立执行Session，源对话未被当作新执行结果。
5. 查看完整Session、逐轮时间线、模型节点及裁判请求/响应。v1总体未达标，其中自然语言断言误伤了同义表达。
6. 修复格式约束，AI修订并发布v2，用当前发布标准重评旧证据。对比Session、Run、Trace和outputs完全相同，旧报告SHA不变，没有重新执行Agent。
7. 专门撤销旧失败工作项的AI用途，重新登录后直达仍显示“资料已失效”，内容隐藏且AI输入禁用。正式验收项保留。
8. 新浏览器标签页重新打开正式工作项，两版题库、原未达标与新通过记录仍可找回，无新增运行。

## 如何找到这次结果

| 对象 | 名称或编号 |
|---|---|
| 正式评测集名称 | **11月退款核对-会话转换验收** |
| 来源Session | `dd5c29ed-fd41-4228-b141-dd27514e60c5` |
| 工作项 | `ce53fafe-b375-5ebb-a932-bb9bcc422c3b` |
| 题库 | `d-e545cd8fb0814e59ace1bc7635ffa53f`，v1/revision3，v2/revision5 |
| v1真实运行 | `41d8fa16-095c-4d76-abe7-56126434a585`，failed |
| v2原证据重评 | `6495ecff-5fa9-4a04-aadd-247ba3c3712e`，passed |
| 四轮执行Session | `669c9111-5d4f-4a7c-aef2-b004e0724dea` |
| 缺金额执行Session | `b6a97b37-8ef2-4b03-b782-37026db118f4` |
| 撤权专用旧工作项 | `3ce0b030-968d-511c-8f0a-b7e9c45d0987`；不要当正式验收入口 |

当前工作台地址：`http://127.0.0.1:9138/#/authoring/ce53fafe-b375-5ebb-a932-bb9bcc422c3b`。授权到期后按当前权限重新授权或新建，不延长旧授权绕过保护。

## 结果为什么不能只看绿色

v1四轮题的“缺乏证据”字面要求未命中“无数据支撑”，逐轮断言只有3/4通过。修复的是题目格式和评分选择能力，历史失败原样保留；v2不再强制这类自然语言字面断言，也没有降低0.8阈值。

v2缺金额题ConversationalGEval为1.0；四轮题为0.8，明确指出**第一轮本应只澄清，Agent却提前计算净额**。后续金额正确不抹掉该错误，达到当前阈值不等于每轮完全正确。

仍有AI裁判局限：通用BusinessFacts/EvidenceBoundary/RecommendationGrounding读取拼接的多轮输出，有的理由把早期1700/1800当作最终回答的冗余/过时内容。本轮未重做通用裁判证据组织；多轮判断应结合专门的ConversationalGEval和逐轮原文，不把裁判理由直接当根因。独立校准仍暂缓。

## 分阶段检查

| 任务 | 验证范围与实际结果 |
|---|---|
| 6.13 | Agent资料/授权/反馈55 passed；Runtime初态5 passed（5条既有warnings）；真实业务用途转换、撤权重新访问拒绝 |
| 6.14 | EvalFlow相关后端77 passed/2 warnings；Agent转换组件2 passed；修复首次生成错误后，真实自动首版成功，不自动发布运行 |
| 6.15 | 语义标准及生成/工作项61 passed/1 warning；前端3套19 passed；来源、运行中、撤权状态与语义题编辑验证 |
| 6.16 | 下游API/结果/Session/模拟边界/执行25 passed/1 warning；真实四轮链路、原证据重评、新标签页找回、录像和截图交付检查 |

这些测试范围有重叠，不能相加宣称唯一测试数量。两端类型与构建通过；Agent API范围Ruff、EvalFlow范围Ruff（E4/E7/E9/F/I）和范围ESLint通过；`make guard`确认上游0侵入。

首次直接Jest未加载CRACO配置，3套未运行；随后使用项目实际CRACO入口，19项通过。错误启动日志保留。Node22与EvalFlow声明Node24不一致，未验证Node24；构建有包体积等既有警告，不称全仓零警告。

## 日志和媒体在哪里

Agent `.local-stack/business-conversion-agent-final.log`、`business-conversion-agent-build.log`。EvalFlow `.local-stack/`下：

- `business-conversion-final-backend.log`、`business-conversion-semantic-checks.log`、`business-conversion-final-regression.log`。
- `business-conversion-final-ui-craco.log`、`business-conversion-final-eslint.log`、`business-conversion-tsc-final.log`、`business-conversion-eval-build-final.log`。
- `business-conversion-results-summary.json`、`business-conversion-original-report.sha256`：原证据与旧报告一致性。

录屏及PNG在Agent `.local-stack/business-session-demo/`。桌面只保留`评测演示/打开演示.html`一个入口，配套16张原始PNG和5段1920×1016录像，总1712.701秒（28分33秒）。视频1包含第一次转换失败，视频2从修复后的正式转换继续，不伪装成一次无错演示。登录在正式录屏之外。

前一版桌面3段视频和24张图收回该目录的`previous-desktop-录像`、`previous-desktop-关键截图`，完整备份为`previous-desktop-demo`；未动无关桌面文件。媒体尺寸/时长/hash见桌面`本轮素材清单.json`。历史额外失败视频只留Worktree，不堆到桌面。

全片解码检查退出0，但第1/3/4段输出到ffmpeg null muxer时有重复DTS警告；原片保留，不声称无警告。浏览器媒体加载尺寸正确，无解码错误；5段各10%/50%/90%共15个跳转均成功，5段短时播放均时间推进。初版临时HTTP服务缺Range支持导致seek回0，改用已有Starlette StaticFiles后通过，未重写媒体。后台仍可能暂停；file双击未自动化。证据为同目录`browser-media-checks.json`。

## 本轮边界

未调用生产接口，未启用自动采样，未改变平台角色，未提交/推送/合并代码。原停止无效循环、正式性能、CI、独立盲测/校准、网关硬上限说明、Grafana/通知及生产部署仍暂缓。未重新做生产灾备；已有隔离恢复证据继续适用。用户亲自验收表仍留空。
