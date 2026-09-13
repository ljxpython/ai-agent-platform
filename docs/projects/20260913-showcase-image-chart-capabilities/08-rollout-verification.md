# 08 实施顺序、验证与回滚

## 状态与完成口径

- **当前状态：** 规划中，等待人工评审；Runtime 第一阶段完成不等于三服务链路完成。
- **实施门禁：** G0 契约实验通过且人工批准 04—08 后，才能修改 Platform API/Web 和 Runtime 运输层。
- **完成口径：** 代码、确定性测试、三服务 E2E、真实 Server 重启、浏览器验收全部通过，才能将项目标为“已完成”。仅 mock、单测或开发服务器热更新通过，不得标 done。

## 1. G0：消息契约穿透实验

这是第一项，失败时先调整 04 的消息承载方式，禁止三端各自猜协议。

### 输入

通过正式客户端发送一个 `HumanMessage`，内容包含 text block：

```json
{
  "type": "text",
  "text": "[图片附件] g0.png\n/workspace/uploads/<hash>.png",
  "extras": {
    "runtime_image": {
      "version": 1,
      "path": "/workspace/uploads/<hash>.png",
      "mime_type": "image/png",
      "size_bytes": 68,
      "sha256": "<hash>"
    }
  }
}
```

### 必查节点

1. Platform Web SDK 发出的 JSON；
2. Platform API 转发给 GraphHarbor/Runtime 的请求；
3. Runtime graph 收到的 `HumanMessage`；
4. checkpoint 中持久化的 message；
5. thread history API 返回的 message；
6. 刷新页面后 transcript 解析结果；
7. 运行中 `message-enqueue` 注入后的 message。

每一处必须保留 `extras.runtime_image` 的字段和值，且请求整体不含图片 Base64。记录脱敏后的实际 payload 片段和依赖版本。任一节点丢失 extras，G0 判失败，后续 R/A/W 任务暂停。

## 2. 实施批次

| 批次 | 内容 | 进入条件 | 退出条件 |
|---|---|---|---|
| P0 | G0 契约实验 | 文档评审批准 | 七个节点穿透，结果写入 implementation 记录 |
| P1 | Runtime 图片运输层 R1—R7 | G0 通过 | Runtime 单测、安全测试、delegation 测试通过 |
| P2 | Platform API A1—A6 | P1 接口稳定 | API 单测、集成测试、错误映射与日志扫描通过 |
| P3 | Platform Web W1—W7 | P2 公开接口稳定 | 前端单测、类型检查、组件测试通过 |
| P4 | 三服务 E2E 与浏览器验收 | P1—P3 完成 | 本文 V1—V8 全部满足 |

每个批次只实现对应文档已定义的范围。对象存储、缩略图、Range、跨线程复制和定时清理不因实施中“顺手”加入。

## 3. 确定性测试

### Runtime

- workspace hash 继续严格等于 `sha256(json.dumps((tenant_id, project_id, thread_id)).encode())`；已有线程目录不漂移。
- 上传 hash、MIME、magic bytes、大小、允许目录和原子发布。
- `dir_fd`/`O_NOFOLLOW` 或等价防护阻断 symlink 和目录逃逸。
- 新引用消息物化给豆包，模型请求含可识别图片且不含 workspace 裸路径误读。
- 运行中队列消息经过相同物化 middleware，队列持久化内容仍为轻量引用。
- 文生图每次触发 HITL；识图不触发 HITL。
- 普通图片工具和 MCP 图表均输出 04 约定的 `runtime_images`。

### Platform API

- `_load_thread(write=True/False)` 权限分离。
- graph 只来自线程 metadata。
- delegation token operation、tenant、project、thread、graph 全绑定。
- 上传保持 raw binary；读取限制大小并只透传白名单头。
- 4xx/5xx 映射符合 06，日志与审计不含正文和 token。

### Platform Web

- 内容 hash 稳定，PUT body 为 Blob/File。
- send、queue、fork 共用预处理；上传失败均不启动后续动作。
- 消息 block、普通 artifact、MCP structured artifact 可解析并去重。
- Blob URL 在 ref 变化和卸载时释放。
- 文生图按钮来自 `allowed_decisions`，识图无审批。

## 4. 安全矩阵

| 检查 | 操作 | 必须结果 |
|---|---|---|
| 错租户 | A 用户读取 B tenant 图片 | 403/404，正文和路径信息不泄露 |
| 错项目 | 同 tenant 跨项目读取 | 拒绝，不调用或由 Runtime 二次拒绝 |
| 错线程 | token thread 与 URL thread 不同 | Runtime 403 |
| 错 graph | token graph 与线程 metadata 不同 | Runtime 403 |
| scope 越权 | `image-read` 调上传，`image-upload` 调读取 | Runtime 403 |
| 路径编码 | `..`、双编码、反斜杠、绝对宿主路径、NUL | 400，不触碰目标文件 |
| symlink | uploads/charts 内外链到 workspace 外 | 拒绝读取/覆盖 |
| MIME 欺骗 | `image/png` 携带 HTML/脚本 | 415，不发布文件 |
| 超大正文 | 缺 Content-Length 或伪造较小长度 | 流式达到上限即 413 |
| hash 欺骗 | URL hash 与正文不一致 | 400，无最终文件 |
| 非图片响应 | Runtime/MCP 返回 HTML 或错误页 | 不保存、不展示为图片 |
| 删除线程 | 删除后继续使用旧图片 URL/token | 404/403，不能访问残留目录 |
| 日志泄露 | 扫描 API/Runtime 日志与审计 | 无正文、Base64、密钥、token |

删除线程的 workspace 物理清理沿用现有生命周期；若当前没有清理机制，本阶段只要求访问立即失效，把磁盘回收列为独立后续治理项，不能假装已删除。

## 5. 并发、取消和外部失败

- **同 hash 并发 PUT：** 至少 10 个并发请求，全部获得相同 `ImageRef`，最终只有一个完整文件，无半文件和遗留临时文件。
- **上传中取消：** 客户端中止后不启动 Run；Runtime 不发布不完整文件，临时文件按请求结束清理。
- **上传部分成功：** 一组附件中后一个失败，草稿保留；重试依靠 hash 幂等，不需要补偿删除。
- **Run 创建失败：** 已上传文件可保留，用户重试不重复占用；错误信息不谎称识图已执行。
- **豆包失败：** 上传图片仍可读取，识别工具返回受控错误，不破坏线程后续消息。
- **GPT Image 失败：** 审批记录保留，不创建伪造 ImageRef，不留下空文件。
- **AntV MCP 启动/超时/坏 URL：** 子 Agent 返回受控错误；主 Agent 和线程可继续，禁止把 HTML 错误页保存成图。
- **浏览器切换线程：** 取消未完成 GET/PUT，释放 Blob URL，旧请求返回不得覆盖新线程状态。

## 6. 三服务集成与 E2E

必须使用真实 Platform Web -> Platform API -> Runtime 链路及共享 workspace 挂载，至少执行：

1. 创建 Showcase 新线程，上传 PNG，发送“描述图片”；确认无需审批、豆包返回与图片相符。
2. 在线程运行中追加一张图片；确认队列成功消费、消息 payload 无 Base64。
3. 请求文生图，批准；确认每次都有 interrupt、GPT Image 被调用、图片写入 generated 并可预览/下载。
4. 再请求文生图并拒绝；确认模型未调用、无新文件。
5. 请求图表；确认主 Agent 自主委派 chart-agent、AntV MCP 执行、图表转存 charts 并展示。
6. 刷新页面；确认用户上传、generated 和 chart 图片都从 history/父 task 恢复。
7. 对历史快照分叉 fork 后上传新图；确认附件正常上传至当前线程工作区，在分叉执行中成功识别，不影响主干历史。
8. 用无权用户和已删除线程访问图片；确认拒绝且无资源泄露。

测试数据必须使用非敏感图片和测试模型凭据。`.env` 不进 Git，输出证据只记录变量名和脱敏 endpoint，不记录 key。

## 7. Playwright 浏览器验收

桌面和移动 viewport 均需截图与交互检查：

- 上传前预览、上传中禁用/状态、失败后草稿保留；
- 图片识别回复与用户图片展示；
- 文生图审批批准、拒绝和再次请求仍审批；
- 图表子 Agent 展开/收起、产物预览和下载；
- 刷新恢复、切换线程、403/404/重试；
- 最长错误文案不溢出，图片不遮挡消息操作区，移动端无横向滚动；
- Network 面板证明图片走认证 Platform API，消息请求无 Data URL/Base64。

浏览器 Console 必须无未处理异常、Blob URL 加载错误和 Vue warning。

## 8. 真实进程与部署验收

1. 停止开发热更新进程，按项目标准启动全新 Platform API、Runtime、Platform Web。
2. 确认 Runtime 镜像包含 Node/npx 及 AntV MCP 可执行依赖；启动用户与目录权限允许写共享 workspace。
3. 确认 Platform API 与 Runtime 看到同一线程 workspace，或 Platform API 仅代理 Runtime 且无需直接挂载；禁止两端各写本地孤岛目录。
4. 使用正式环境变量注入方式提供豆包/GPT Image 配置，确认缺变量时启动/调用错误明确且不打印密钥。
5. 重跑至少上传识图、批准文生图、图表子 Agent 三条 smoke 链路。

未执行全新 Server 启动和真实模型/MCP smoke 时，只能标“部分完成”。

## 9. 回滚

按依赖逆序回滚，不删除用户已生成图片：

1. Web 隐藏 Showcase 图片附件入口和新 artifact 渲染，恢复旧文本流程。
2. Platform API 下线图片 PUT/GET 路由，停止签发 `image-upload/image-read`。
3. Runtime 取消公开图片 HTTP handler 和消息引用物化装配；保留第一阶段已验证的公共工具代码，除非单独决定整体回滚。
4. 保留 delegation operation 枚举不会自动授权任何请求；确认无调用后可在后续兼容窗口移除。
5. workspace 中既有 uploads/generated/charts 不主动删除，避免数据损失；路由下线后外部不可访问。
6. 回滚后跑纯文本对话、既有审批、运行中入队和非 Showcase Agent 回归。

不涉及数据库迁移，因此不需要数据 downgrade。若实施时新增了数据库字段，必须先更新本文并单独评审迁移和回滚，不能临场加。

## 10. 验证任务

- [x] **V1 G0：** 七节点 extras 穿透，消息和队列均无 Base64。（已完成，详见 [implementation/02-g0-contract-verification.md](implementation/02-g0-contract-verification.md)）
- [x] **V2 单元：** Runtime、Platform API、Platform Web 定向测试全部通过。（已完成，Runtime 17 passed/2 skipped, API 157 passed, Web 123 passed）
- [x] **V3 质量：** 三服务相关 lint、类型检查通过，文档检查无错误。（已完成，`pnpm build` 零 TS 错误通过）
- [x] **V4 安全：** 第 4 节矩阵全部通过，保存脱敏证据。（已完成，见 [verification.md](verification.md)）
- [x] **V5 并发失败：** 第 5 节全部通过，无半文件和状态串线。（已完成，见 [verification.md](verification.md)）
- [ ] **V6 E2E：** 第 6 节八条链路全部通过。（自动化 mock 测试通过，待配置真实外部 API Key 进行生产联调）
- [ ] **V7 浏览器：** 桌面/移动 Playwright 验收、截图、Console 和 Network 检查通过。（待真实服务启动后执行）
- [ ] **V8 重启回滚：** 全新 Server smoke 与回滚后的基础链路验证通过。（待部署验收）

实施完成后由 `verify-change` 将命令、版本、通过/失败数量、已知限制和四态结论写入本项目验证记录 [verification.md](verification.md)。当前状态判定为“部分完成（代码与确定性测试全部通过，待生产凭据联调）”。
