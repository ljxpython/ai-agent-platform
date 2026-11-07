# 本地链路验证与缺口修复

更新：2026-11-07。对应 T01–T07；进度仍以 `../tasks.md` 为准。本记录只说明实际改动与阶段证据，不替代 Final。

## 范围确认

用户明确“本地 Docker 若需要这一层测试暂时略过”。因此本地 Docker、依赖 Docker 的 Office reader 和真实远端 Node 部署测试记为 `deferred`；本地 PostgreSQL/Redis、真实 xiaok DeepSeek、Chromium、性能与非 Docker 故障测试继续完成。GraphHarbor 未修改；不新增旧逻辑兼容或存量迁移。

## Runtime

- `apps/runtime-service/src/runtime_service/middlewares/filesystem.py` → `ImageReferenceFilesystemMiddleware`：同步和异步 `read_file` 在公开工具结果前外置图片；复用 `ImageRef`。PDF 等已支持文档复用 `DocumentWorkspace`/`FileRef` 和既有 `extras.runtime_file`，不新增媒体协议；未开放二进制类型明确报错，不能透传 base64。模型请求副本恢复原类型，保留文字，核对 MIME/大小/摘要；文件工具引用不会改变普通用户文档附件的解析路径。
- `apps/runtime-service/src/runtime_service/workspace/image_io.py` → `ImageWorkspace.save`：按内容摘要去重，临时文件写入、fsync、原子 link；校验已存在内容，失败清理临时文件。generated/charts 保持 32hex 路径结构，名字现在是内容键；不涉及历史数据处理。
- `apps/runtime-service/tests/middlewares/test_image_reference_filesystem.py`：同步/异步、并发去重、错 MIME、篡改、缺失/损坏、写失败；真实 compiled Agent + checkpoint + v3 工具/消息事件同时验证图片和 PDF。模型请求可展开，持久状态与公开结果不可含原始媒体。
- 主图和现有 general-purpose 子图复用同一引用规则；文件存储走已有本地/远端分派。远端部署实测按用户决定暂缓。

## Web

- `useTranscriptMessages.ts` 删除“消息条数/首尾 ID 相同就跳过”的判定，同 ID 的内容变化正常刷新。
- `message-alignment.ts` 与 `ChatSession.vue` 删除“更长旧缓存优先”和旧分支拼接。缓存只在控制器没有消息时占位；历史抽屉按需读取。
- `useSessionConnection.ts` 清除被新 run/thread/controller values 取代的恢复快照。页面重新可见时先核权限，再刷新运行并重连；`onVerify(false)` 查当前运行，不等待运行终止。
- `useChatActions.ts`、`ChatMessageList.vue`、`ChatSession.vue`：编辑按需载入检查点时禁用提交，防止快速点击误报找不到检查点；按 newest-first 历史的 parent 链寻找消息出现前的检查点，不能选择仍含旧答复或其他分支的节点。
- SDK 自身 hydrate 的 `getHistory(limit:20)` 用于发现子图，仍存在。报告必须与应用首屏为补当前消息而重复读取 History 区分，不能宣称首屏网络总 History=0。

## API

- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` → `update_thread_state`：预条件 GET state 使用 `read` 委派，写入使用 `thread-edit`，不扩大 token 权限。
- `apps/platform-api/tests/test_thread_state_update_scope.py` 固定两次调用的委派作用域。真实性能夹具 POST state 原先返回 403，修复并重启 API 后成功。

## 验证工具和证据

- `apps/platform-web/e2e/session-image-offloading.spec.ts`：精确检查 xiaok 主机/模型，真实读图、下载哈希、刷新与追问。证据 `../image-e2e-evidence.json`，截图 `../screenshots/xiaok-image-*.png`。
- `apps/platform-web/e2e/session-hydration-lifecycle.spec.ts`：重启持久化、运行中刷新、停止续聊、编辑分支、子图及审批恢复。运行记录中保留失败后修复原因；未通过的场景不得计为完成。
- `apps/platform-web/scripts/seed-session-loading.mjs`：仅本地夹具，生成前后 F1/F2。F1 45 消息、12 组工具、3 张有效 PNG；前后逻辑相同，介质分别 inline/ref。不读取生产凭据，不修改存量会话。
- `serve-session-baseline.mjs`：在独立 Vite 进程使用 Git HEAD 的 4 个水合入口文件作基线，保持工作区完整；不是旧版本生产部署。
- `inspect-session-loading.mjs`：Chromium 网络限速，记录响应头、完整 body、解析、两帧正文绘制和媒体完成；失败保留，补采达到每夹具 30 个有效样本。性能原始数据在 `../performance/`。

## 已执行阶段检查

- Runtime 初轮扩展集：121 passed / 18 skipped（最终需逐项列 skip 原因）；新增媒体测试目前 14 passed。
- Web chat/threads：606 passed / 1 skipped；新增编辑与列表 9 passed；初轮 vue-tsc 退出码 0。
- API 权限/媒体回归：46 passed + 6 subtests；state scope/fork 6 passed。
- 真实 xiaok 图片 E2E：1 passed / 48.6s，下载 SHA/大小一致，History 无 inline，继续追问仍识别 BLUE。
- 曾出现停止 POST 已接受但浏览器显示待确认：后端最终 stopped，复跑实际 202 DTO 校验和自动收敛通过；暂不将该现象假定为 schema 错误。继续保留复跑与恢复证据。
- 编辑首轮失败确认是未等按需检查点加载完成；第二轮修复后编辑正确，子任务失败因 Standard 模式不暴露 task。测试已改为 UI 选择 Pro 模式后实际委派。
- 重启 Worker 与一次 E2E 启动重叠导致发送等待超时；后续等待本地进程就绪再跑，不归类为模型功能通过。

Final 尚未执行，原始命令和最终统计以 `../verification.md` 为准。
