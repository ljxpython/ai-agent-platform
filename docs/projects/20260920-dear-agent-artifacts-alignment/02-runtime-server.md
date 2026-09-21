# 02 Runtime Server：已有能力、施工方案与验证

## 1. 目标、负责人和交付边界

本方负责本层。仓库实际服务名为 `runtime-service`，本文 Runtime Server 指同一层。交付目标是让 Platform API 能稳定读取真实发布成果，并提供可直接给前端使用的类型、限制和错误事实。

**当前状态：完成。本专项复用既有生产能力，新增回归和真实 Agent 验收；没有改 Runtime 生产逻辑。** 发布、摘要、分页、预览与隔离通过验证，无需重复建设文件服务。新增友好名称等持久元数据延后。

## 2. 当前代码目录（与本专项相关的真实子集）

```text
apps/runtime-service/
├── pyproject.toml                       # Python >=3.13；pytest import mode/pythonpath
├── src/runtime_service/
│   ├── webapp.py                        # include 路由；graph_capability 接口
│   ├── auth/platform.py                 # authenticate：受信平台委托
│   ├── http/
│   │   ├── documents.py                 # _auth_scope / _auth，既有文件接口
│   │   └── workspace.py                 # artifacts/tree/content/preview/zip
│   ├── runtime/capabilities.py          # 兼容导出，真实声明在 Dear 服务
│   ├── tools/
│   │   ├── artifacts.py                 # build_artifact_tool / present_artifacts
│   │   └── images.py                    # ImageWorkspace：受控描述符 I/O
│   ├── workspace/
│   │   ├── scoped.py                    # resolve_thread_workspace / scope hash
│   │   ├── artifact_refs.py             # ArtifactWorkspace / preview_kind
│   │   ├── schemas.py                   # ArtifactRef / ArtifactPage / PreviewKind
│   │   ├── browser.py                   # WorkspaceBrowser / path_parts
│   │   ├── documents.py                 # DocumentError / validate_document
│   │   ├── file_refs.py                 # MAX_FILE_BYTES / 输入文件引用规则
│   │   ├── media.py                     # 图片/PPTX 校验
│   │   └── html_preview.py              # safe_html / HTML_CSP
│   └── services/dearflow_agent/
│       ├── agent.py                     # 发布工具装配与策略
│       ├── prompts.py                   # 写文件后逐个真实发布
│       ├── capabilities.py              # graph_capabilities / tool_permissions
│       └── tools/artifacts.py           # 仅兼容导入共享 build_artifact_tool
└── tests/
    ├── test_workspace_browser.py
    ├── test_workspace_http.py
    ├── test_thread_workspace_isolation.py
    ├── test_image_http.py               # HTTP 用例复用测试签名 token helper
    └── services/dearflow_agent/test_p5_media.py
```

不能新增另一份 `ArtifactRef`、另一条发布工具或 `http/artifacts.py` 绕开当前路由。公共修改写入 `tools/artifacts.py` / `workspace/`，不要改 Dear 兼容文件再留 Showcase 走旧逻辑。

## 3. 当前发布与读取算法逐步说明

### 3.1 发布不是保存一句文件路径

入口：`services/dearflow_agent/agent.py` 装配 `build_artifact_tool(root)`，模型调用 `present_artifacts(file_path)`。

`ArtifactWorkspace.publish()` 当前顺序：

1. 只接受 `/workspace/work/`、`generated/`、`charts/` 来源；拒绝 `..`、反斜杠、控制字符。
2. 用扩展名查 `ARTIFACT_MIMES`；未知类型 415。
3. 通过 `ImageWorkspace.read()` 在绑定工作区读取真实字节，读取不到 404。
4. `validate_artifact()` 检查最大 20 MiB，图片/PPTX 走 `validate_media`，文档走 `validate_document`；允许的源码按文本规则验证。允许发布一种扩展名不等于能理解/执行该格式。
5. 计算 SHA256，目标固定为 `/workspace/outputs/{sha256}.{ext}`。
6. 在 outputs 打开目录描述符，创建 O_EXCL/O_NOFOLLOW 临时文件，写入、flush/fsync；用 link 发布到最终名，已存在则继续读原目标；清临时文件。
7. 再调用 `read()` 校验最终文件并返回引用。目标已被篡改时不能因“文件已存在”假装成功。

因此原 `work/report.md` 改写不影响已发布副本；同内容同扩展名复用同路径，内容变更生成新路径。当前没有原文件名映射，也没有发布事务/来源审计索引。

参考 D01 的 `present_files` 更新 state 路径列表；我们保留更强的真实字节校验和哈希引用，不复制该 reducer。

### 3.2 列表不是再次运行 Agent

```text
GET /internal/threads/{thread_id}/artifacts
  -> http/workspace.py:artifacts
  -> _call -> documents._auth -> resolve_thread_workspace
  -> asyncio.to_thread(ArtifactWorkspace(root).list_artifacts)
  -> WorkspaceBrowser.list_directory('/workspace/outputs', artifacts_only=True)
  -> ArtifactPage response_model
```

列表只读目录元信息，筛选“64 位 hash + 已支持扩展名”的普通文件，隐藏目录/软链接/特殊文件。按文件名排序，不按发布时间排序；`sha256` 从文件名取值，下载/预览才重新计算摘要。不要给前端承诺“列表已经逐个验过文件内容”。

分页：limit 默认 100，HTTP 范围 1—200；cursor 编码 path/after/revision，revision 取目录 mtime_ns；目录变化返回 409 `workspace_directory_changed`。cursor 为不透明值，前端不得拼接或跨线程复用。缺少工作区或 outputs 时成果列表正常返回空。

### 3.3 读取、预览和资源上限

`WorkspaceBrowser.read_file()` 遇 outputs 哈希路径交给 `ArtifactWorkspace.read()`；验证 path 形状、读取、20 MiB 限制、SHA256 与格式。普通工作文件仍允许工作区浏览，但不作为正式成果列表来源。

`WorkspaceBrowser.preview()` 当前先读取文件再分发：

| preview_kind | 返回 | 上限/行为 |
|---|---|---|
| text / markdown | JSON，包含 text、truncated、mime_type、sha256 等 | 前 256 KiB；使用增量 UTF-8 decoder 避免截断半个中文字产生替代字符 |
| image | PNG/JPEG/WebP 字节 | 校验实际图像格式；不返回 base64 消息 |
| html-sandbox | safe_html 净化后的 text/html | 超 256 KiB 拒绝 413；CSP meta 与响应头同时存在 |
| download | 不返回可预览内容 | preview 请求返回 415 workspace_preview_unsupported；content 下载仍可成功 |

Runtime 当前 HTTP 使用 `Response(data)`，文件先在内存里读取；Platform 再按流转发。**不要把后者写成全链路磁盘流式读取，更没有 Range 承诺。** 本期维持既有上限。

### 3.4 工作区归属和内部授权

Dear 工作区默认推导结构：

```text
${RUNTIME_WORKSPACE_ROOT:-.runtime/workspaces}/dearflow_agent/
  <sha256(json.dumps((tenant_id, project_id, thread_id)))>/workspace/
    uploads/      # 输入
    work/         # 中间处理/可修改源码
    generated/    # 生成图片等，按需要出现
    charts/       # 图表，按需要出现
    outputs/      # 固定哈希产物
```

前端只看到 `/workspace/...`；不得返回上述宿主绝对地址。Showcase 有自己的旧根 `RUNTIME_SHOWCASE_WORKSPACE_ROOT`，不擅自迁移。

`documents._auth_scope()` 校验 authenticate 结果中的 operation/thread_id，以及 tenant/project/assistant 非空，再 resolve；文件读取 operation 为 `workspace-file-read`。graph 能力读取由 `webapp.graph_capability` 提供。前端不得持有/签发内部委托 token。

## 4. 本期应该怎么写

### R01 核对生产工具装配，保留单一发布入口

- 检查 `agent.py` 是否按当前项目策略装入 present_artifacts；用既有配置下真实 Agent 运行证明，不能仅用直接调用 publish 证明工具已开放。
- `prompts.py` 已要求逐个发布，不新增“把任何文本路径自动认作产物”的逻辑。
- 若模型已生成文件但发布被策略拒绝，报告工具/策略依赖，不向列表塞假数据。本专项不绕过审批或扩大工具授权。

### R02 给 ArtifactWorkspace 补精确回归

已修改 `tests/test_workspace_browser.py`，新增 `test_published_versions_and_tampering` 与 `test_artifact_pagination_and_failed_publication`。下方保留设计示意；实际可执行用例以上述文件为准：

```python
def test_published_artifacts_are_real_and_immutable(tmp_path):
    import hashlib
    import pytest
    from runtime_service.workspace.artifact_refs import ArtifactWorkspace
    from runtime_service.workspace.documents import DocumentError

    (tmp_path / "work").mkdir()
    source = tmp_path / "work" / "report.md"
    source.write_bytes(b"# report\n")
    store = ArtifactWorkspace(tmp_path)
    assert store.list_artifacts()["items"] == []
    first = store.publish("/workspace/work/report.md")
    assert store.publish("/workspace/work/report.md") == first
    source.write_bytes(b"# changed\n")
    second = store.publish("/workspace/work/report.md")
    assert second["path"] != first["path"]
    assert store.read(first["path"])[0] == b"# report\n"
    assert hashlib.sha256(store.read(first["path"])[0]).hexdigest() == first["sha256"]
    target = tmp_path / first["path"].removeprefix("/workspace/")
    target.write_bytes(b"tampered")
    with pytest.raises(DocumentError) as error:
        store.read(first["path"])
    assert (error.value.code, error.value.status_code) == ("artifact_hash_mismatch", 409)
```

已有 `test_text_artifacts_persist_and_publish_idempotently` 覆盖的参数化幂等逻辑不再复制一套；实施时合并重复断言。只新增当前缺失断言，避免用几十个镜像用例膨胀测试。

### R03 内部 HTTP 契约补齐

- 扩充 `test_signed_workspace_http`，继续参数化 Dear/Showcase。
- 复用 `test_image_http._make_token`，只签测试 SECRET；修改 operation/thread/graph 等维度，断言拒绝，不调用线上授权。
- 用 `httpx.ASGITransport(app=app)` 检查真实序列化：ArtifactPage 字段、next_cursor null、preview Content-Type、缺路径/limit 越界 422。
- 图片、Markdown、HTML、二进制下载分别验证；未知 binary 普通文件能下载，不代表允许 publish。
- 不修改 `PreviewKind` 或添加显示元数据来让测试好看。

### R04 确定性样本和持久性证据

- 使用临时 scope 建 MD/CSV/小图片/HTML/ZIP，并通过 publish 生成引用，不手写 outputs hash 文件冒充正常发布。
- 样本与生成逻辑优先放既有测试 fixture；不新增常驻 seed API。
- 持久性由 05 的真实子进程重启验证；`ArtifactWorkspace(tmp_path)` 重建对象仅能证明对象无内存依赖，不算进程重启。

### R05 只有失败证据才改生产实现

若 R02/R03 抓出问题，按来源修改 `artifact_refs.py`（发布/摘要）、`browser.py`（分页/读取）、`workspace.py`（HTTP 映射）对应函数。修前加复现，修后同时跑 Dear/Showcase；不重写 workspace root、不迁移旧文件、不扩展输入上传白名单。

## 5. 任务与验证

| 任务 | 状态 | 必需验证 | 给下游的交付物 |
|---|---|---|---|
| R01 发布工具链核对 | 完成 | 真实 Dear run 有两次成功 present_artifacts 回执，MD/CSV 可读 | 实现记录与 04 样本 |
| R02 发布/摘要/分页缺口回归 | 完成 | 真文件、101 项分页、同 hash 不同 ext、篡改 409 | Runtime 42 项通过 |
| R03 内部 HTTP/隔离回归 | 完成 | scope、422/404/409/413/415、各 preview 类型 | test_dear_artifact_types_errors_and_scope |
| R04 重启与样本交付 | 完成 | Dear/Showcase 真 Runtime 子进程重启后原 path/sha256 一致 | 05 与实现记录 |
| R05 证据驱动修复与收尾 | 完成 | 回归未发现 Runtime 生产缺陷，无需改生产逻辑 | 实现记录；新增持久元数据延后 |

验证命令、前置环境和用例覆盖细表见 [05](05-backend-verification.md)。输出给前端的正式公开接口通过 Platform API，内部 HTTP 不作为前端交接地址。

## 6. 当前状态

完成（done）：单元/内部 HTTP、Dear/Showcase 双服务重启与真实模型工具发布证据见 [05](05-backend-verification.md) 和 [实现记录](implementation/01-backend-artifact-delivery.md)。不包含前端浏览器验收。真实模型测试位于 `apps/runtime-service/tests/services/dearflow_agent/test_artifact_platform.py`，默认跳过，显式开启才创建合成测试项目、非成员用户并调用现有模型。
