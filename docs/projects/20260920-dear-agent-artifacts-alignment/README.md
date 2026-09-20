# Dear Agent 成果：后端实施规划与前端交接

## 项目状态与责任

- **启动日期：** 2026-09-20；结束日期待排期。
- **状态：** 规划中；已完成分层源码对照与交接草案，未修改业务代码、未执行功能测试。
- **本方责任：** Platform API / runtime-service 后续开发、确定性测试、双服务 HTTP、真实平台 API 验证、接口交付文档。
- **前端责任：** 其他同事负责 platform-web 页面/组件/状态/服务封装修改、前端测试与浏览器验收；本方不实施前端。
- **联合责任：** 真实 Agent 发布至页面下载的最终用户链路验收。
- **改动级别：** 链路专项；首批复用现有接口与持久格式，拟修网关错误信息并补后端测试。单独漏项目头属于前端 bug，由前端同事修复。
- **治理边界：** 首批不扩权限、不迁移数据、不开放动态 HTML。增加持久元数据/编辑/动态执行另行评审。
- **估算：** 本方后端 2—4 人天，联合联调 0.5—1 人天；前端排期由接手同事评估，外部依赖等待另计。
- **负责人：** 后端/Runtime及前端接手人均待指定；文档不代表实施批准。

## 阅读顺序

本次升级为多专题模板，每篇自带方案、任务、验证和状态。旧 plan/tasks/verification 只保留跳转入口，不继续维护另一套全局方案和任务事实源。

1. [01 目标、参考源码与分层边界](01-scope-and-reference.md)：400 根因、产品目标、14 项 DeerFlow 文件/函数映射、借鉴/不采用项。
2. [02 Runtime Server 施工](02-runtime-server.md)：实际目录、发布/列表/预览/隔离算法、已有能力与 R01—R05 工作、测试示例。
3. [03 Platform API 施工](03-platform-api.md)：实际目录、授权和代理调用链、错误信息补齐、B01—B05 工作和交付内容。
4. [04 前端独立交接](04-frontend-handoff.md)：后端交付状态、公开接口、完整 JSON/类型/错误样例、Vue 接入步骤、F01—F08 和前端测试责任。
5. [05 后端验证与交付门禁](05-backend-verification.md)：已有测试覆盖与缺口、用例输入/断言、可执行命令、真实 API smoke、G1—G4 验收。

## 文档结构

```text
docs/projects/20260920-dear-agent-artifacts-alignment/
├── README.md
├── 01-scope-and-reference.md
├── 02-runtime-server.md
├── 03-platform-api.md
├── 04-frontend-handoff.md
├── 05-backend-verification.md
├── plan.md                 # 旧链接导航，不独立维护方案
├── tasks.md                # 按责任导航，不独立维护任务
└── verification.md         # 验证导航，不独立维护执行结果
```

实现开始后才创建 implementation/。尚未实现或执行的内容均标“计划/待开始”，不得填假版本、假联调账号或测试通过。

## 已确认事实

1. 成果页 createSessionService 漏传项目参数，授权 fetch 不会自动补；后端项目必填校验不应删除。
2. Runtime 与 Platform 已有正式成果列表和受保护预览/下载，独立页面仍扫描历史消息；首批主要是前端正确接入已有合同。
3. 本期后端有具体补齐项：嵌套 Runtime 错误 message 提取、Dear 专用双服务验证、真实权限 smoke、接口实测证据。
4. 参考 DeerFlow 的显式发布、统一预览、终态刷新；保留本平台哈希产物、项目授权、静态 HTML 隔离。
5. 无业务名称/发布时间/来源 run/Office 专用预览；先交接真实现状，增强另列。不得把计划功能写成已开发。

## 分层进度

| 层/阶段 | 当前状态 | 完成证据位置 |
|---|---|---|
| 范围与参考分析 | 规划内容已整理；业务未实施 | 01 |
| Runtime R01—R05 | 待开始 | 02 + 后续 implementation |
| Platform API B01—B05 | 待开始 | 03 + 后续 implementation |
| 前端 F01—F08 | 交接草案已写；待前端同事开发 | 04 |
| 后端 G1/G2 | 未执行 | 05 |
| 前端 G3/联合 G4 | 未执行 | 04/05 |

后续可以明确记录“后端已完成、前端待接入”；不能因此把整体页面标 done。待 G4 通过才可认定核心用户链路完成。

## 关联事实源

- [Dear Agent 总纲](../20260913-dearflow-agent/README.md)与[成果设计](../20260913-dearflow-agent/04-workspace-sandbox-and-artifacts.md)。
- [W3 历史实现记录](../20260913-dearflow-agent/implementation/18-w3-artifacts-and-multimedia.md)：其“完成”结论不能替代本专项真实接入验收。
- [工作区实现版合同](../20260917-showcase-artifact-workspace/05-frontend-handoff.md)：现有 API 与格式限制的基础。
- [工作区 ZIP 专项](../20260918-workspace-archive-download/README.md)：整工作区打包不等于仅成果打包。
