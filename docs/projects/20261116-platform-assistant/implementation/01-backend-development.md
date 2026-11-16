# 后端实施与阶段证据

日期：2026-11-16。范围：当前 Worktree，非生产部署。基线 d8ebfaa 已提交并推送至 feat/platform-assistant。

## 已确认的追加决定

用户批准为无业务项目用户自动创建个人助手项目；全部已接入数据库均可供获准用户发现与读取，不限固定查询。继续保留数据权限分层及数据库只读边界。生产连接不从平台管理员账号隐式继承；数据负责人配置专用只读数据集。

## 当前实现

新增单 create_agent 平台助手及 API bootstrap/read/capabilities/internal-read。复用现有 Thread/Run/checkpoint、模型连接、预算、隐私、中间件与原生审批。新工具没有 Workspace、shell 或执行沙箱。SQL 使用锁定的 LangChain Community SQLDatabase 及 SQL 工具适配器，数据库执行在 API 端，通过 sqlglot AST、只读登录身份、只读事务和有界查询共同限制。

文档支持显式发布清单、版本和行号；源码使用单独清单与研发用户授权。旧日志路径移除匿名放行，所有候选日志复核项目与结构化关联；支持配置 Loki 或当前环境固定日志文件。证据回执用于历史资料撤权校验；普通审计仍保持原有非原子可靠性，并在响应中报告 audit_recorded。

## 实际阶段结果

- local-stack init/deps/doctor/start 成功；环境 wt_3565491667ce，依赖属于本 Worktree。
- API 首轮 33 项测试通过；Runtime 平台助手与注册回归 19 项通过。后续新增逻辑仍在补测，不把首轮数字当最终覆盖。
- 真实 PostgreSQL 独立只读角色读取两个项目过滤视图成功；关联聚合得到 Demo、2 行、cost=4.00，另一项目行未返回。首次连接因未授 CONNECT 失败，已仅为本隔离库专用角色补授 CONNECT 后复验成功。
- 真实 API→Runtime→DeepSeek 模型→文档工具→引用回答链路成功。Thread ed1926f7-da4b-443e-99a1-f852f31aa1ec，Run 900e7642-8763-4277-8740-b3394f2abc14，证据 f5c1e8d2-46d2-4f9e-ae15-6acf627c901e。状态 success，历史含两条模型消息及文档工具结果。
- 当前机器 Docker daemon 未运行；未启动 Docker，不将其误当助手沙箱要求。日志接入继续使用本环境固定文件和独立契约测试。
- 锁定 langchain-community 0.4.2 导入出现 sunset 弃用提示；此次沿已安装包最小适配，未升级生态依赖或隐藏该提示。

## 当时尚在执行（已由后续记录接续）

当前API相关回归99项通过、4项按原夹具条件跳过，另含19个subtests；助手专项含真实PostgreSQL合计39项通过。真实模型已自行读取结构并发出SQL，收到项目范围内的关联聚合结果。继续完成SQL最终回答、多轮重启、审批跨进程恢复、回退和前端交接。当前不是后端整体验收结论，前端代码和浏览器联合验收仍由同事负责。

后续SQL、多轮/重启、审批重放、回退及前端交接已完成本地技术验证，当前结论见[交付证据](02-backend-delivery.md)和原tasks.md；此文保留初期阶段事实。
