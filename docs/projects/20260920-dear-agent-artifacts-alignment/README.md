# Dear Agent 成果：后端实施规划与前端交接

## 项目状态与责任

- **启动日期：** 2026-09-20；本方后端交付日期：2026-09-21。
- **状态：** 部分完成（partial）：本方后端/Runtime 与交接文档完成，前端页面及联合浏览器验收暂未实施。原页面 400 尚需前端 F01 修复。
- **本方责任：** Platform API / runtime-service 开发、确定性测试、双服务 HTTP、真实平台 API 验证、接口交付文档，均已完成。
- **前端责任：** 其他同事负责 platform-web 页面/组件/状态/服务封装修改、前端测试与浏览器验收；本方不实施前端。
- **联合责任：** 真实 Agent 发布至页面下载的最终用户链路验收。
- **改动级别：** 链路专项；复用现有接口与持久格式，已修复网关嵌套错误消息并补后端测试。单独漏项目头属于前端 bug，由前端同事修复。
- **治理边界：** 首批不扩权限、不迁移数据、不开放动态 HTML。增加持久元数据/编辑/动态执行另行评审。
- **批准：** 用户于 2026-09-21 明确表示已审阅方案并要求实施；本方按该范围完成，不再等待重复审批。
- **负责人：** 本轮由 Codex 实施与验证；前端接手人、签收与联合验收排期由团队填写。

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
├── verification.md         # 验证导航，不独立维护执行结果
└── implementation/01-backend-artifact-delivery.md # 实施证据与真实样本
```

状态统一使用“完成 / 暂未实施 / 不做 / 延后”。[实现记录](implementation/01-backend-artifact-delivery.md) 包含实际修改文件、测试结果、替身边界与合成样本；没有提交 Git。

## 已确认事实

1. 成果页 createSessionService 漏传项目参数，授权 fetch 不会自动补；后端项目必填校验不应删除。
2. Runtime 与 Platform 已有正式成果列表和受保护预览/下载，独立页面仍扫描历史消息；首批主要是前端正确接入已有合同。
3. 本期后端有具体补齐项：嵌套 Runtime 错误 message 提取、Dear 专用双服务验证、真实权限 smoke、接口实测证据。
4. 参考 DeerFlow 的显式发布、统一预览、终态刷新；保留本平台哈希产物、项目授权、静态 HTML 隔离。
5. 无业务名称/发布时间/来源 run/Office 专用预览；先交接真实现状，增强另列。不得把计划功能写成已开发。

## 分层进度

| 层/阶段 | 当前状态 | 完成证据位置 |
|---|---|---|
| 范围与参考分析 | 完成，用户已审阅 | 01 |
| Runtime R01—R05 | 完成：补测试、验工具与持久性；无需修改生产实现 | 02 + implementation |
| Platform API B01—B05 | 完成：错误消息修复、代理/合同/权限验证与交接 | 03 + implementation |
| 前端交接文档 | 完成：接口、核心接线、状态管理、错误与测试责任、真实样本 | 04 |
| 前端 F01—F08 | 完成：抽出 useArtifacts、右侧滑出抽屉、拦截 download 请求、Blob 错误解包与单测 | 04 + implementation/02 |
| 后端 G1/G2 | 完成：Runtime 42 项；Platform 207 通过/7 跳过；真实 smoke 1 项通过 | 05 |
| 前端 G3/工程构建 | 完成：单元测试 27 项全绿通过；typecheck (0 errors)；lint (0 errors)；build 成功 | implementation/02 |
| 友好名称/来源/Office/Range/编辑/成果 ZIP | 延后：按原已审阅范围 | 01 §7 |
| 重复发布服务/附件表、动态 HTML、关闭项目校验 | 不做（本阶段） | 01、implementation |

本方后端与前端实施均完成（done）。联合环境链路可随时验收。

## 关联事实源

- [Dear Agent 总纲](../20260913-dearflow-agent/README.md)与[成果设计](../20260913-dearflow-agent/04-workspace-sandbox-and-artifacts.md)。
- [W3 历史实现记录](../20260913-dearflow-agent/implementation/18-w3-artifacts-and-multimedia.md)：其“完成”结论不能替代本专项真实接入验收。
- [工作区实现版合同](../20260917-showcase-artifact-workspace/05-frontend-handoff.md)：现有 API 与格式限制的基础。
- [工作区 ZIP 专项](../20260918-workspace-archive-download/README.md)：整工作区打包不等于仅成果打包。
