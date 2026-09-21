# 后端成果交付实施记录

日期：2026-09-21。用户已审阅方案并批准实施；本次不提交 Git，不实施前端业务代码。

工作树基线：`4c5753528beb89a0d72c04dbb156d9457dece11b` + 本专项未提交改动。参考 DeerFlow 版本仍为 `44ae750545caff29506906f4b0b1ebf79cb23fa7`。本记录对应 R01—R05、B01—B05；前端 F01—F08 暂未实施，交给前端同事。

## 1. 实际开发内容

| 层 | 文件与入口（仓库根相对路径） | 本次交付 |
|---|---|---|
| Platform 生产代码 | `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py:56`，`_runtime_upstream_message` | 增加 5 行读取 `detail.detail.message`；保持顶层/字符串消息优先、status/code/私有字段脱敏与 fallback |
| Platform 错误回归 | `apps/platform-api/tests/test_runtime_upstream_errors.py` | 2 个测试覆盖嵌套消息、状态码、脱敏、优先级、空值/错误类型兜底；修前实际 2 项失败，修后通过 |
| Platform HTTP 合同 | `apps/platform-api/tests/test_runtime_gateway_workspace.py:146` | 缺项目头 400 且不访问 workspace upstream，422 参数边界、分页透传、响应脱敏 |
| Platform 双服务 | 同文件 `test_dear_artifacts_two_service_http` / `_check_two_service_http` | 复用原 Showcase fixture，新增 Dear；实际 Runtime 子进程、HTTP、委托验签、字节、错误及重启；Showcase Terminal 原回归保留 |
| Platform 流代理 | `apps/platform-api/tests/test_runtime_gateway_sdk_adapters.py:198`，`test_file_stream_limits_and_cleanup` | 正常、坏 MIME、声明超限、无长度累计超限、读取断流和首块后关闭；逐项断言 response/client 释放 |
| Runtime 发布与分页 | `apps/runtime-service/tests/test_workspace_browser.py:210`、`:235` | 实际工具调用、发布前空、版本不可变、同字节不同扩展名、篡改 409、101 项分页、游标失效、发布失败不留半成品 |
| Runtime 内部 HTTP | `apps/runtime-service/tests/test_workspace_http.py:74` | MD/PNG/HTML/ZIP、ETag/字节、静态 HTML、415 降级、400/422/404/409/413、tenant/project/graph 隔离 |
| 真实平台烟测 | `apps/runtime-service/tests/services/dearflow_agent/test_artifact_platform.py` | 显式启用后，真实登录、合成项目 A/B、Dear 模型运行与审批、两份成果、预览/下载摘要、缺头与跨项目/非成员拒绝；保留样本供前端 |

Runtime 生产实现无需修改：现有 `ArtifactWorkspace`、`WorkspaceBrowser`、`http/workspace.py` 已满足合同。没有新增上传/发布 API、成果数据库表、reducer、索引或依赖。

共享 helper 的调用方已核对：SDK error mapper 与 Runtime HTTP client 共用该函数，修在统一入口。修改前嵌套 `{detail: {code, message}}` 的 message 会退化为 fallback；修改后传递真实可读消息，前端仍以 code 做分支。

## 2. 验证记录

全部命令从相应服务目录运行，使用已有 `.venv`。退出码除明确失败的先验复现外均为 0。

| 验证 | 命令/范围 | 实际结果 |
|---|---|---|
| Runtime 修改前基线 | `.venv/bin/python -m pytest tests/test_workspace_browser.py tests/test_workspace_http.py tests/test_thread_workspace_isolation.py -q` | 39 passed，5 warnings，7.66s |
| Runtime 修改后 | 同上 | 42 passed，5 warnings，10.97s |
| Platform 修改前基线 | `.venv/bin/python -m unittest discover -s tests -p test_runtime_gateway_workspace.py -v` | 2 tests OK，15.034s |
| 嵌套消息先验复现 | 新 `test_runtime_upstream_errors.py`，未修改 helper 时运行 | 2 项失败：nested message 退化；作为修复证据保留 |
| 错误修复回归 | `.venv/bin/python -m unittest discover -s tests -p test_runtime_upstream_errors.py -v` | 2 tests OK |
| SDK/流代理 | 同上，pattern 为 `test_runtime_gateway_sdk_adapters.py` | 16 tests OK，0.354s |
| 双服务与边界 | 同上，pattern 为 `test_runtime_gateway_workspace.py` | 4 tests OK，41.875s；Dear 和 Showcase 均真进程重启 |
| Platform README 全量命令 | `PLATFORM_RUNTIME_INTEGRATION=0 .venv/bin/python -m unittest discover -s tests -p 'test*.py' -q` | 214 tests，207 通过、7 skipped，66.100s；含 files/HTTP matrix/shared mapper 回归 |
| Platform 语法检查 | `.venv/bin/python -m compileall -q src tests` | 通过；不等同 lint/类型检查 |
| Runtime 语法检查 | compileall workspace、HTTP/tools artifacts 与本次测试文件 | 通过；不等同 lint/类型检查 |
| 真实登录/模型/API | `DEAR_ARTIFACT_PLATFORM_TEST=1 .venv/bin/python -m pytest tests/services/dearflow_agent/test_artifact_platform.py -q -s` | 最终 1 passed，52.17s；无身份/目录/模型替身 |

Platform 跳过项为现有显式集成环境门禁（PostgreSQL DSN/清理与迁移集成等），不是本次成果测试跳过。原测试存在 JWT 短测试密钥警告、Runtime 既有 warning；不把这些报告为新生产缺陷。该服务 pyproject 未配置独立 lint/typecheck 命令，没有虚报其通过。

**替身边界：** 双服务测试的 actor/catalog/项目权限方法是替身，Runtime 服务/委托验签/文件 I/O/进程重启是真实的。流异常测试使用 httpx MockTransport 及可关闭流，证明代理逻辑资源释放，不等同浏览器断网。真实账号与模型的证据独立记录于下节；G3/G4 浏览器仍由前端实施。

## 3. 真实平台验收与交接样本

运行命令：

```bash
# 工作目录：apps/runtime-service；会创建合成测试项目/非成员账号并使用已有模型。
DEAR_ARTIFACT_PLATFORM_TEST=1 .venv/bin/python -m pytest tests/services/dearflow_agent/test_artifact_platform.py -q -s
```

测试仅针对本地 `http://127.0.0.1:2142`，不创建/更新全局模型配置，不改已有项目授权。审批只接受两个指定 work 文件的 write_file/present_artifacts。密码和 token 仅在进程内使用，不记录到交接资料。

烟测开发期间暴露并修正两处测试预期，未为迁就测试修改生产协议：

1. 下载缓存头实际为 `private, no-store`，初次断言误写 `no-store`；修正为实际完整值。
2. 真实跨项目线程查找先被 Agent Server 隔离，返回 `404/langgraph_thread_get_failed`、`thread not found`，不会走到 fixture 的 `403/thread_project_denied`。前端同时处理两者；404 不泄露另一项目线程存在性。

两次未完整通过的烟测也保留了合成数据，便于排查；不将其计为烟测通过：

| 次数 | 项目 A / B | thread | 中止点 |
|---|---|---|---|
| 1 | `5bf0ac18-6cbd-4e5f-a8f5-c7622a09e653` / `e723fe73-0509-445b-9467-ec0e66becbb9` | `4dae87a5-bfdc-4504-8658-1c2c003407e4` | 下载缓存头预期；55.75s |
| 2 | `04dc0b00-3894-49da-849c-610aa0e55176` / `67a9011f-58c2-43a4-a8c4-2ad467fca0c5` | `a20774ca-391f-48ab-91ae-7dbef9a42b87` | 跨项目状态预期；54.13s |

最终完整通过的样本：

- 项目 A：`bac27f9b-ac91-414c-a452-c4172a61802d`；项目 B：`f654bf74-a485-4e15-b310-7010d0747f7a`。
- thread：`71e93b45-86c7-45c1-97c7-f7859e8e8958`；模型沿用已启用的 `DeepSeek-V4-Flash`。
- run 顺序：`331d3080-8bc2-459b-b449-343a1db49c21` → `ae8d9fbe-7a3b-4acd-92ef-eaedbcc7aa9c` → `55257898-08fc-4d05-90e5-96f26b07c399`；前两段按受限工具审批恢复，最终 success。
- MD：9 字节 `# report\n`，SHA256 `d2f56516fd6c35644826ae6f1876a47870b7fa19acedac3e52fb6f2a94aa2624`。
- CSV：20 字节 `name,value\nsample,1\n`，SHA256 `1760a6c53e823ca2878437a5eaf5cb3ede6984f742fa77ad6de132adaa56fe88`。
- 非成员账号：`artifact-nonmember-2be07a90e2`；无平台角色/项目成员关系，随机密码未保存。
- 成功列表有两项，预览摘要、附件内容 SHA256、attachment/nosniff/private-no-store 通过；去头 400、跨项目 404、非成员 403。路径与负例 request_id 已交付到 [04 §11](../04-frontend-handoff.md#11-可直接用于联调的真实样本)。

### 本地部署重启复核

模型 run 结束后，按仓库正式脚本执行（工作目录为仓库根）：

```bash
bash scripts/local-stack.sh restart-one runtime-api
bash scripts/local-stack.sh restart-one platform-api
```

两条均退出 0：Runtime API ready（8s），Platform API health ready（2s）。未重启/验证 worker 任务恢复，不宣称对此有新增证据。

随后用平台 `.venv` 的 httpx 真实登录并带 A 项目头，重新 GET 上述 thread 的 artifacts；断言两项摘要集合不变，逐个 GET workspace/content 并重新计算 SHA256，两项均一致。没有重新 seed/publish，证明实际部署的已发布产物在读取服务重启后仍可用。

重启后的 Platform 加载本次 helper 修复；请求 `/workspace/work/no-such-artifact.md` 实测 404，原始 `error.code` 与 `error.message` 都是 `workspace_file_unavailable`（修复前 message 会是通用 fallback）。request_id：`44b77b911d2d41088ca924e40f53f1b9`。没有关闭项目校验或改写 404 为成功。

## 4. 交付边界、回滚

- **完成：** 后端合同与必要修复、Runtime 回归、真实工具发布、双服务重启、接口交接文档。任务明细见 02/03，验收结果见 05。
- **暂未实施：** F01—F08 前端代码、组件/浏览器验证与 G4 联合页面验收；负责人及签收日期待前端团队填写。页面漏 `x-project-id` 的修复仍由 F01 完成，不能宣布页面 400 已解决。
- **延后：** 友好名称、发布时间/来源 run、Office 专用预览、Range/大文件、草稿预览、编辑、仅成果 ZIP，沿用已审阅范围。
- **不做：** 本阶段重复发布服务/reducer/结果域附件表、动态 HTML 执行、关闭项目校验、以 history 正则作为正式成果源。

无数据库/文件格式迁移。回滚只需回退本次错误 helper 代码；不删除/覆盖 outputs 或用户数据。真实 smoke 创建的合成项目保留作为前端联调材料；不自动删除。新增非成员账号使用随机密码且无项目成员关系，不授予平台角色；不将其当作可共享登录账号。

## 5. 文档与收尾检查

10 份项目 Markdown、39 个本地相对链接检查通过；5 段 JSON 示例可解析；MD/CSV 两组实测样本摘要重新计算一致。`git diff --check` 通过，未改任何前端 Vue/TS 文件，未执行 Git 提交。仓库 README、FEATURES、专题任务状态与兼容导航已同步：本方后端完成，整体 partial，前端及联合浏览器暂未实施。
