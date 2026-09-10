# 文档重建实施

日期：2026-09-10。用户已批准plan，按T2–T5实施，未改产品Python代码、数据库结构或依赖。

## 已实施

- docs活文档收敛到10篇：导航、6篇handbook、3篇standards。复用已更新的架构/开发/使用手册，补真实代码入口与使用顺序；架构图使用内嵌Mermaid。
- 新增configuration/database/runbook，重写权限、审计和网关标准；不继续采用“顶部宣布失效、正文保留旧规则”的形式。
- 服务README缩为安装启动/验证/入口；根README改为指向当前开发规范。
- 归档28文件：9份delivery、6份decisions、1份Operations标准、12个图文件。原分类和历史正文保留，Markdown修复相对链接并注明Archived；12个图文件与原Git内容逐字节一致。archive/README记录每个原位置和替代来源。既有29个历史文件保留，仅修复必要引用。
- Runtime集成历史审查中的两个移动文件引用已更新；既有归档执行单的文件引用同步修复。当前规范不通过归档文件指导开发。
- 旧前端清单中仍需复核的权限、项目生命周期、service/client重复和Chat组件复用，转入原重构工程05交接；不恢复已退役Testcase/Operations待办，不承认旧勾选为本轮浏览器通过。
- `.env.example`删除3个已无Settings字段的Operations参数，APP_VERSION与当前0.1.2默认一致。这是配置示例修订，不修改真实.env。

## 源码核对中澄清的边界

- OIDC当前仅配置边界/视图，不能宣称完整登录能力。
- 审计独立短事务、写失败记录日志，未实现与业务原子提交或可靠重试；query原样记录，不能在URL传秘密。
- ready依据平台数据库，关闭数据库配置也会返回ready；HTTP 200不代表Runtime/Worker可用。
- 服务使用Agent产品名，但权限枚举仍为project.assistant.read/write；不因文档命名而制造另一组权限。
- 20个业务表之外还有Alembic版本表；run_requests是请求关联，不是运行镜像。
- 网关仅20条当前路由，审计解析器历史分支和SDK方法不代表公开能力。

## 验证

完整记录见[verification](../verification.md)和[evidence](../evidence/20260910-docs-check.json)。文档与例子保持简单，未增加文档框架或新测试框架；复用现有检查与33项契约/事务测试。真实PG、Docker和负载证据引用已验收工程，不为纯文档变更重跑模型工具。

本轮未提交或推送Git。全仓文档检查的24个旧问题不属于本工程，已与HEAD逐行确认并单独记录，没有伪报全仓通过。

## 后续授权修复

用户要求消除上述24处问题，已修改13个文档/测试上下文文件的个人绝对路径，保留历史语义。全仓文档检查与diff空白检查通过；原错误清单保留作修复前记录。
