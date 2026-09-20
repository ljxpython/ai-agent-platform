# 05 后端验证、分批交付与联合验收

## 1. 目标与责任边界

本方独立完成 Runtime/Platform 的代码、单元测试、内部 HTTP、双服务 HTTP 和真实平台 API smoke；不以“等前端写完”为理由跳过后端验证。前端同事负责组件测试、浏览器自动化与界面实现；完整成果页体验由双方联合验收。

四个门禁分开报告：

| 门禁 | 执行方 | 完成定义 | 不代表什么 |
|---|---|---|---|
| G1 确定性后端合同 | 本方 | R02/R03、B01/B02/B04 通过，临时文件/签名/错误真实可测 | 不代表真实登录/模型配置可用 |
| G2 后端可交付 | 本方 | Dear 双服务 HTTP、进程重启、真实平台账号 scope API smoke，交付 04 的实测资料 | 不代表前端 400 已修 |
| G3 前端接入 | 前端同事 | F01—F08、组件/类型/构建/页面接口通过 | 不替代后端隔离/持久性验收 |
| G4 完整用户链路 | 双方 | 真实 Dear run 发布→成果页→预览→下载 hash→刷新恢复→跨项目拒绝 | 不包括明确后置的增强功能 |

真实模型步骤可由本方先通过现有聊天/API 执行，结果交给前端浏览；若工具/外部网络阻塞，标记具体阻塞。直接调用 publish 不能替代真实 Agent 工具装配验收。

## 2. 环境准备与测试隔离

1. 两个服务 Python 均要求 >=3.13；使用各自 `.venv` 与项目依赖，不临时全局安装。
2. Runtime pytest 的 pythonpath/import-mode 已在 pyproject.toml；Platform 现有 README 使用 unittest，优先沿用，不为这次验证新增 pytest 依赖。
3. 单测文件系统全部用 tmp_path/TemporaryDirectory；委托使用测试 SECRET/issuer/audience；不可读取真实用户 outputs 或把真实 token 写日志。
4. 确定性 HTTP 用 ASGITransport；双服务测试允许其已有 fixture 启动临时端口/子进程，测试结束只清理由该 fixture 创建的资源。
5. 真实联调栈按 `docs/quickstart/local-dev.md` 和 local deployment contract，用 `scripts/local-stack.sh` 检查/启动；测试 fixture 临时进程不作为另一个开发环境启动方式。
6. 真登录 smoke 至少准备项目 A/B、拥有 A 读取权限的用户及受限用户、Dear 可用目标和样本线程。身份治理不可全部 monkeypatch 后宣称完成 G2。

## 3. 先核对已有用例，再补缺口

| 已有用例 | 已有覆盖（源码核查） | 要补/要实测的缺口 |
|---|---|---|
| Runtime test_tree_pagination_mutation_and_unsafe_files | tree 分页、变动游标、坏路径、symlink/FIFO | artifacts_only 的 101 项分页，明确不包含 work |
| Runtime test_preview_download_and_limits | 文本预览、UTF-8 截断、binary 降级、超大小 | published outputs 的同类边界与 HTTP 错误码 |
| Runtime test_text_artifacts_persist_and_publish_idempotently | 扩展名参数化、同内容幂等、改源再发布 | 旧版本仍可读、目标篡改 409、相同字节不同扩展名均在列表 |
| Runtime test_generated_images_and_type_mismatch | 真 PNG/JPEG/WebP，错扩展名拒绝 | HTTP 返回类型、平台代理字节一致性 |
| Runtime test_html_has_no_active_navigation_or_script | 脚本、导航、外链、iframe、事件属性净化 | 真实浏览器不执行由前端 G3/G4 补；字符串断言不是浏览器证明 |
| Runtime test_signed_workspace_http | Dear/Showcase 参数化、委托 scope、列表/读文件/静态 HTML | 各 4xx、参数 422、101 成果/游标冲突 |
| Platform test_routes_scope_paths_and_capability | workspace 路由、非法路径、跨项目、目标限制 | 缺头原始 envelope、同 code 不同客户端包装、全部 preview 分支 |
| Platform test_real_two_service_http | 真 Runtime 子进程、I/O、下载 hash、重启；身份/catalog 为 fixture | Dear 专测、真实平台登录 API smoke；不照搬全部 Terminal 场景 |

以上不是本次已通过记录。实施时先运行基线，保留结果；已有覆盖通过就不重复写相同测试。

## 4. Runtime 用例施工表

| 编号/建议用例 | 输入准备 | 必须断言 |
|---|---|---|
| R-T01 发布闭环 | work/report.md 9 字节示例 | 发布前空；发布后 hash/path 正确；可原字节读取 |
| R-T02 版本固定 | 改写源再发布；单独篡改 outputs | 旧 hash 原字节不变；新 path 不同；篡改 read 409/artifact_hash_mismatch |
| R-T03 去重范围 | 同字节的 .txt/.md | artifact_id 相同、path 不同，两项都可见 |
| R-T04 artifacts 分页 | 101 个不同内容源逐一 publish；limit=100 | 第一页100、第二页1、next_cursor结束；合集无丢重，顺序按名 |
| R-T05 目录更新 | 首页后新增产物再请求旧 cursor | 409/workspace_directory_changed；不能返回错页 |
| R-T06 scope | 相同 thread 字面值，tenant/project/graph 不同 | 各根/数据隔离；委托 wrong operation/thread 拒绝 |
| R-T07 文件类型 | 小真图片、恶意 HTML、MD、ZIP、空/损坏文件 | 按实际格式策略验收，拒绝不是假空成果；download 类型 preview 415 |
| R-T08 容量与路径 | 20 MiB+1、HTML256KiB+1、穿越/symlink/FIFO | 对应 413/拒绝；无宿主字节泄漏 |
| R-T09 HTTP schema | ASGITransport 请求内部 artifacts/preview | ArtifactPage 模型、next_cursor null、参数422、Content-Type/CSP |

发布失败不得遗留可列出的半成品；测试检查输出目录没有不完整 hash 文件。原子发布强度按现有实现验收，不凭 fsync 文件就声称掉电级目录事务已保障。

## 5. Platform 用例施工表

| 编号/建议用例 | 操作 | 必须断言 |
|---|---|---|
| B-T01 缺头 | 用已认证 fixture 调 artifacts，不带项目 | 400/error.code=project_id_required，不到 workspace upstream |
| B-T02 越权 | A 用户+B项目头，或 A头+B线程，或目标 graph 禁止 | 403，对应服务 code；Runtime 文件读取未发生 |
| B-T03 嵌套错误 | create_runtime_upstream_error 收 detail.code/message | status/code/消息保留；空/坏类型有 fallback；私有字段已脱敏 |
| B-T04 参数 | limit0/201、坏 cursor、无 path、过长 path | 422或既有400，按 route/service 所属层断言，不混为一种 |
| B-T05 类型转发 | JSON preview/image preview/HTML preview/content | Content-Type 正确、no-store/nosniff/CSP，下载 attachment与ETag |
| B-T06 坏上游 | 不支持MIME、声明超20MiB、无长度超限、途中失败 | 提交前502或提交后流终止；response/client最终关闭 |
| B-T07 Dear 双服务 | 真 Platform HTTP→真 Runtime进程 | 参数、委托、目录、字节、错误往返真实；写明 identity/catalog fixture |
| B-T08 重启 | 停同测试拥有的 Runtime，再原根启动，不seed | 原引用列表与下载hash不变；不是仅重新new对象 |
| B-T09 真账号 smoke | 已配置本地栈真实登录及A/B项目 | 真项目权限与线程归属生效、资源可以获取、跨scope拒绝 |

错误消息回归最小示例（拟放现有 SDK adapter 测试或独立 unittest）：

```python
def test_nested_runtime_message(self):
    from platform_api.adapters.langgraph.sdk_client import create_runtime_upstream_error

    error = create_runtime_upstream_error(
        status_code=409,
        detail={"detail": {"code": "workspace_directory_changed", "message": "Directory changed"}},
        fallback_code="langgraph_upstream_request_failed",
    )
    self.assertEqual(error.status_code, 409)
    self.assertEqual(error.code, "workspace_directory_changed")
    self.assertEqual(error.message, "Directory changed")
```

在改 B02 前运行此例应暴露 message 退化；必须确认真实 baseline 失败结果，不能把文档推断记录成已跑失败。

## 6. 可执行的确定性检查示例

以下从 `apps/runtime-service` 目录执行，依赖该服务环境。只在临时目录发布并读取，不写真实用户工作区；用于理解 I/O，**不能代替 HTTP/权限测试**：

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
from runtime_service.workspace.artifact_refs import ArtifactWorkspace
from runtime_service.workspace.browser import WorkspaceBrowser

with TemporaryDirectory(prefix="artifact-contract-") as directory:
    root = Path(directory)
    (root / "work").mkdir()
    data = b"# report\n"
    (root / "work" / "report.md").write_bytes(data)
    store = ArtifactWorkspace(root)
    assert store.list_artifacts()["items"] == []
    ref = store.publish("/workspace/work/report.md")
    assert ref["size_bytes"] == 9
    assert ref["sha256"] == hashlib.sha256(data).hexdigest()
    assert store.list_artifacts()["items"] == [ref]
    assert store.read(ref["path"])[0] == data
    preview, mime = WorkspaceBrowser(root).preview(ref["path"])
    assert mime == "application/json"
    print(ref)
    print(preview.decode())
PY
```

当前文档里的样本 hash 是计算样例，不是该命令本轮已执行通过的记录。

## 7. 正式验证命令

### Runtime：工作目录 apps/runtime-service

```bash
.venv/bin/python -m pytest "tests/test_workspace_browser.py" "tests/test_workspace_http.py" "tests/test_thread_workspace_isolation.py" -q
.venv/bin/python -m compileall -q "src/runtime_service/workspace" "src/runtime_service/http/workspace.py" "src/runtime_service/tools/artifacts.py"
```

若动图片/PPTX 校验再追加 `tests/services/dearflow_agent/test_p5_media.py` 相关用例。compileall 仅语法检查，不冒称 lint/类型检查；新增生产修改还需按服务既有开发规范运行适用检查，不临时发明不存在的 lint 脚本。

### Platform：工作目录 apps/platform-api

```bash
.venv/bin/python -m unittest discover -s "tests" -p "test_runtime_gateway_workspace.py" -v
.venv/bin/python -m unittest discover -s "tests" -p "test_runtime_gateway_files.py" -v
.venv/bin/python -m unittest discover -s "tests" -p "test_runtime_gateway_sdk_adapters.py" -v
.venv/bin/python -m compileall -q "src" "tests"
```

若 B02 新建 `test_runtime_upstream_errors.py`，追加该文件的 discover。共享 mapper 修改后执行服务 README 规定的 broader unittest 回归；数据库/外部服务依赖不可偷偷跳过后标全量通过。

### 真实平台 API smoke

由本方运行，可不等前端新页面。使用现有登录流程取得凭据，放在本地进程内；用 httpx 请求 capabilities/artifacts/preview/content，断言 HTTP、JSON、headers、sha256。建议延伸现有测试脚本而不是加生产 seed API。

输入配置表：

| 输入 | 来源 | 是否写入证据 |
|---|---|---|
| API base URL | local deployment contract | 是 |
| 认证 token | 现有登录 | 否 |
| A/B 项目 ID 与 thread ID | 测试账号/测试线程 | 可去敏写入 |
| graph_id | 线程服务端 metadata | 是，不能由客户端替代授权 |
| artifact path/hash | publish 回执与 list | 是 |

按顺序请求：合法A列表→合法预览→合法下载校验hash→去掉项目头400→B项目读A线程拒绝→权限受限用户拒绝。记录 request_id 便于定位，不打印 token 或完整上游私有详情。

## 8. 前端和联合验证的责任

前端 F01—F08 的具体测试文件和命令全部在 [04 §9](04-frontend-handoff.md#9-前端测试如何写何时算完成)，本方不写/执行前端业务实现来替代接手同事。

G4 联合场景：

1. 真实 Dear 会话写 MD/CSV，实际调用 present_artifacts；保存去敏 run/thread/工具回执。
2. 新成果页能列出同 path；Network 中包含正确项目头且不扫描 history。
3. 渲染/源码/下载正常，原字节摘要一致；HTML 静态隔离、图片授权、Office 下载降级。
4. 刷新/重进和 Runtime 重启后仍读取；切项目无残留；跨项目访问被服务器拒绝。
5. 慢请求竞态、101成果、21会话、断网/权限错误、窄屏键盘与 Showcase 回归由前端记录，本方协助接口问题定位。

## 9. 实施批次、估算与交付物

| 批次 | 本方工作 | 依赖 | 估算/交付 |
|---|---|---|---|
| A | R02/R03 + B01/B02/B04，先跑baseline再补缺口 | Python依赖可用 | 1—2人天；确定性测试与必要生产修复 |
| B | R01/R04 + B03/B-T09 smoke，封存接口样本 | A通过；真实模型/账号/服务配置 | 1—2人天；G2证据与04交付资料 |
| C | 前端同事F01—F08 | 可按当前合同先做，最终依赖G2 | 工期由前端评估；本方不计入开发承诺 |
| D | G4联合验收与问题收口 | B/C通过 | 0.5—1人天联调预算，等待时间另计 |

前版“4—6人天包含前端”不再是本方承诺。若真实模型/数据库迁移环境阻塞，单独记录，不混入代码开发完成度。

## 10. 结果记录、回滚与当前状态

后续每批 `implementation/` 记录必须包含：修改文件/函数、为何修改、commit或工作树标识、命令/退出码、成功失败数、替身范围、实际请求/截图/样本位置、已知限制、交付给谁。当前不创建虚假的实现记录。

首批无数据库/文件格式迁移。生产回滚只回退本次网关错误 helper 等代码；不删 outputs，不覆盖 hash 文件。前端由其负责人单独回退；原接口和旧聊天消费者仍须可用。

当前记录：2026-09-20，完成源码核查和分层文档；G1/G2/G3/G4 全部未执行。阶段状态可写“后端 done、前端待接入”；只有 G4 完成才写整个成果页闭环 done。后置友好名称/Office/编辑不得被包含在 done 宣称里。

本轮实际执行的文档检查：9 份文档相对链接有效；5 段 JSON 可解析；3 段完整 Python 示例可编译（03 的局部伪代码不当成完整程序检查）；9 字节样例 SHA256 一致；`git diff --check` 通过。未运行示例业务逻辑，这些检查不计入 G1—G4。
