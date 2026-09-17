# Runtime 产物发布与沙箱能力

## 目标

让 Runtime 明确区分“Agent 在工作区产生的文件”和“用户可交付的 artifact”，并把发布结果通过流式消息和状态传给 Platform。先完成 Runtime 后端实现和契约测试，再交给 Platform Web 对接。

## Open SWE 借鉴

- Open SWE 的 sandbox 由 thread 绑定，进程缓存只加速，恢复时从稳定 binding 重连。
- 产物不是把任意 shell 输出当成功，而是由显式 artifact 工具发布；HTML 预览在沙箱 iframe 中运行。
- 文件树、终端、变更文件和 artifact 都是独立右侧 surface，由前端统一编排。

## 方案设计

### Runtime 能力

1. 普通文件浏览新增 `workspace/browser.py`；不可变发布继续复用 `workspace/artifact_refs.py` 的 `ArtifactWorkspace.publish/read`，补充列表。具体文件清单见 [04](04-code-change-map.md)。
2. 为 Showcase 增加共享 `present_artifacts` 工具，参数为线程工作区内路径；允许 `work/generated/charts` 发布源，目标固定 `outputs/<sha256>.<ext>`，返回不可变引用。
3. 发布时计算 sha256、检测 MIME/扩展名、大小和文本/二进制类型；拒绝符号链接、路径穿越和不支持类型。
4. 保留现有工具结构化返回和 ToolMessage 链路，引用包含 `artifact_id/path/mime_type/size_bytes/preview_kind`，前端不从自然语言猜路径；本期不强制迁移 `content_and_artifact`。
5. local 与 Docker 后端共享发布逻辑；Docker 继续负责 Shell 隔离，LocalShellBackend 仅限本地开发。

### 首批支持类型

| 类型 | 展示方式 |
| --- | --- |
| Markdown/TXT/YAML/YML/TOML/JSON/CSV/XML | 文本预览、复制、下载 |
| Python/JavaScript/TypeScript/JSX/TSX/Vue/C/C++/Rust/Shell/SQL/CSS/HTML | 语法高亮文本预览、复制、下载 |
| PNG/JPEG/WebP | 图片预览、放大、下载 |
| SVG | 文本预览或下载；第一阶段不直接 inline 执行 SVG |
| PPTX/ZIP/PDF/XLSX/XLS | 文件信息、下载；首期 PDF 和 Office 均不 inline |
| 任意未知二进制 | 普通工作区仅下载，拒绝浏览器 inline；不允许通过发布工具发布 |

本表对应已实现格式。HTML 提供静态安全 iframe，JS/SVG 只作文本；PDF/Office 只下载。XLS 沿用魔数校验，不承诺下载内容无宏。

### `present_artifacts` 修复

原实现只允许 `txt/md/bib/csv/json/html/css/js/zip/pptx`，读取端也使用固定后缀正则，因此 `/workspace/work/payment_openapi.yaml` 会返回 `unsupported_artifact_type`。当前已同步 Runtime 格式、能力声明与平台运输白名单，YAML 两服务发布、列表、下载链路验证通过。

修复方案：

1. 扩展共享 MIME/扩展名表，增加 YAML/YML、TOML、XML、Python、Shell、SQL、TypeScript、Java、C/C++、Rust 等常见文本格式。
2. 发布和读取都从同一张白名单生成扩展名校验，禁止“发布能过、读取不能过”的双重白名单漂移。
3. 文本格式统一按 UTF-8、NUL 字节、20 MiB 上限校验；JSON 额外做语法解析；ZIP/PDF/XLSX/PPTX 复用已有结构校验，PPTX 拒绝宏和外链；XLS 仅检查魔数，不提供执行安全保证。
4. 图片沿用现有 Pillow 校验，仅允许 PNG/JPEG/WebP；不把 SVG 当作可执行 HTML。
5. 工具描述同步列出“文本、PNG/JPEG/WebP 图片、文档、演示文稿、源码归档”，不要再硬编码过时的扩展名列表。

首期不加入 YAML/TOML 第三方解析器；预览按纯文本处理，避免把不可信文件当配置执行。

### 结构化返回与刷新契约

```json
{
  "version": 1,
  "artifact_id": "<64位内容摘要>",
  "path": "/workspace/outputs/<64位内容摘要>.md",
  "file_name": "<64位内容摘要>.md",
  "mime_type": "text/markdown",
  "size_bytes": 1234,
  "sha256": "<64位内容摘要>",
  "kind": "text",
  "preview_kind": "markdown"
}
```

`preview_kind` 是待新增字段，其余沿用现有引用。相同内容和扩展名重复发布返回同一路径；文件修改后产生新摘要。同内容不同扩展名可能共享 artifact_id，因此列表和选中项以 path 为键。第一阶段消费发布工具的结构化结果刷新列表，运行终态兜底刷新，不新增 `artifact.published` 自定义事件。原文件名、来源消息和发布时刻没有持久化索引，本期不作为必填字段。

## 任务拆分

- [x] Showcase 装配 `present_artifacts` 和 Runtime 工具权限
- [x] 完成发布/读取/能力声明/平台运输 MIME 一致性；格式矩阵及 YAML 跨服务下载已通过
- [x] 验证结构化工具结果随现有消息/checkpoint 保存和恢复，补充 preview_kind
- [x] 增加 Runtime 工作区 `list/read` 能力，供 Platform API 构建文件树和普通文件预览
- [x] 补充生成架构图、Markdown、源码 ZIP 的确定性测试
- [x] 评审是否需要独立 artifact 数据库/对象存储（第一阶段不引入）

## 验证要求与记录

- [x] Agent 生成文件 → 发布 artifact → 恢复 Run 后仍可读取
- [x] 重复发布幂等、文件修改生成新 digest
- [x] 未发布普通文件不会伪装成交付 artifact
- [x] artifact 路径和内容不能越过 thread scope

## 状态

后端 done；发布权限/审批、checkpoint 恢复、文件格式与跨服务读取验证通过。在线生成模型和前端页面为 deferred，详见 [验证记录](verification.md)。
