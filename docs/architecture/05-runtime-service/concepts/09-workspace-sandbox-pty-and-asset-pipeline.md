# 运行时操作系统级沙箱、PTY终端与数字资产管线深度剖析 (Workspace, Sandbox, PTY & Asset Pipeline)

> **老王暴躁技术流寄语**：
> “很多半吊子搞 AI Agent，以为让大模型写代码、跑测试就是拿 Python `subprocess.run()` 随便一跑，或者在 `/tmp` 里建个文件夹让它乱写。我呸！一旦用户的提示词被 Prompt Injection（提示词注入），或者模型发癫执行 `rm -rf /`、写入软链接窃取宿主机私钥，你的服务器直接原地升天！
> `apps/runtime-service/src/runtime_service/workspace/` 这 15 个文件，根本不是什么普通的‘存文件的工具包’，它是给自主智能体量身定制的**操作系统级受控运行沙箱（OS-Level Sandboxed Environment）**与**企业级多模态数字资产不可变管线（Digital Asset Pipeline）**！今天老王我就把这 15 个硬核文件的底层底细全给你扒出来！”

---

## 一、30秒速通全景：15 个文件的架构军团总表

在 `workspace` 目录下，15 个文件分工严谨，构成了防逃逸、防注入、防篡改的“五大安全支柱”：

| 架构支柱 | 文件名 | 代码行数 | 核心导出对象 / 函数 | 生产核心职责 (大白话) |
| :--- | :--- | :--- | :--- | :--- |
| **一、路径隔离与防逃逸** | [`scoped.py`](../../../../apps/runtime-service/src/runtime_service/workspace/scoped.py) | 51 行 | `thread_scope_hash`, `hashed_thread_root`, `resolve_thread_workspace` | **物理隔离根计算**：用 SHA-256 单向哈希计算三元组，客户端绝不能传绝对路径，强行阻断越权 |
| | [`deepagent.py`](../../../../apps/runtime-service/src/runtime_service/workspace/deepagent.py) | 99 行 | `DeepAgentWorkspace`, `build_deepagent_workspace`, `resolve_workspace_virtual_path` | **DeepAgents 框架适配**：虚拟路径挂载，防 `..` 穿越，安全解析 `SKILL.md` 技能目录 |
| **二、极度严苛代码沙箱** | [`execution.py`](../../../../apps/runtime-service/src/runtime_service/workspace/execution.py) | 153 行 | `execute_in_workspace`, `docker_workspace_args`, `runtime_backend` | **Docker 执行器**：全网阻断（`--network=none`）、无特权、只读文件系统、限内存 256MB、超时强杀与输出截断 |
| **三、交互式 PTY 终端** | [`terminal.py`](../../../../apps/runtime-service/src/runtime_service/workspace/terminal.py) | 448 行 | `TerminalManager` (`terminals`), `TerminalSession` | **Web 伪终端引擎**：1MB 环形缓冲、Base64 游标重放、窗口动态 Resize、看门狗自动回收与进程组强杀 |
| | [`terminal_child.py`](../../../../apps/runtime-service/src/runtime_service/workspace/terminal_child.py) | 11 行 | `TIOCSCTTY` ioctl 注入 | **PTY 控制终端接管**：绕过 Python 多线程下无法使用 `preexec_fn` 的限制，干净建立会话组长 |
| **四、工作区文件树与下载** | [`schemas.py`](../../../../apps/runtime-service/src/runtime_service/workspace/schemas.py) | 41 行 | `WorkspaceEntry`, `WorkspacePage`, `ArtifactRef`, `ArtifactPage` | **Pydantic 契约**：定义文件树条目、5 种预览类型（text/markdown/image/html-sandbox/download）与分页模型 |
| | [`browser.py`](../../../../apps/runtime-service/src/runtime_service/workspace/browser.py) | 245 行 | `WorkspaceBrowser`, `path_parts` | **只读分页浏览与打包**：带目录纳秒 mtime 指纹的游标分页（409冲突检查）、256KB 预览与防软链接 ZIP 打包 |
| | [`archives.py`](../../../../apps/runtime-service/src/runtime_service/workspace/archives.py) | 59 行 | `read_zip` | **防御性内存 ZIP 解析**：彻底封杀 Zip Slip 穿越、解压炸弹（100倍膨胀阻断）、软链接劫持与加密压缩包 |
| **五、资产管线与格式消杀** | [`file_refs.py`](../../../../apps/runtime-service/src/runtime_service/workspace/file_refs.py) | 62 行 | `FileRef`, `validate_file_path`, `validate_file_ref` | **上传文件寻址**：`/workspace/uploads/<sha256>.<ext>` 强校验，文件内容哈希即路径 |
| | [`documents.py`](../../../../apps/runtime-service/src/runtime_service/workspace/documents.py) | 178 行 | `DocumentWorkspace`, `validate_document`, `open_pdf` | **文档格式体检与原子落盘**：`dir_fd` + `os.link` 防撕裂，校验 PDF 魔数/密码，Excel 阻断宏病毒 |
| | [`media.py`](../../../../apps/runtime-service/src/runtime_service/workspace/media.py) | 87 行 | `validate_media`, `MEDIA_MIMES` | **多媒体/PPTX 深度安检**：阻断 XXE 实体注入、外部链接嗅探与宏病毒，限制幻灯片 20 页防 DoS |
| | [`image_refs.py`](../../../../apps/runtime-service/src/runtime_service/workspace/image_refs.py) | 177 行 | `ImageRef`, `validate_image_ref`, `build_image_reference_block` | **多模态图片协议**：校验 PNG/JPEG/WEBP 格式与 SHA256，生成 LangChain 消息协议标准附件块 |
| | [`html_preview.py`](../../../../apps/runtime-service/src/runtime_service/workspace/html_preview.py) | 126 行 | `safe_html`, `_StaticHTML`, `HTML_CSP` | **静态 HTML 净化器**：严格白名单剥离 `<script>`/`<iframe>`/事件属性，注入最严 CSP，彻底杜绝 Stored XSS |
| | [`artifact_refs.py`](../../../../apps/runtime-service/src/runtime_service/workspace/artifact_refs.py) | 214 行 | `ArtifactWorkspace`, `validate_artifact`, `publish` | **不可变工件发布总管**：从临时区发布到 `/workspace/outputs/<sha256>.<ext>`，原子硬链接与防篡改验证 |
| | [`__init__.py`](../../../../apps/runtime-service/src/runtime_service/workspace/__init__.py) | 16 行 | `__all__` 导出列表 | 门面模块统一导出 |

---

## 二、架构全景交互图：工作区沙箱如何为 Agent 保驾护航

整个 `workspace` 模块在宿主机、Docker 沙箱与前端客户端之间形成了一个严密的受控屏障：

```
+----------------------------------------------------------------------------------------------------+
|                                      Web 前端 / API Gateway                                        |
+----------------------------------------------------------------------------------------------------+
       |                                      |                                       |
 (1) 上传文档/图片                       (2) 查看工作区/预览/下载                (3) 交互式终端 WebSocket
       |                                      |                                       |
       v                                      v                                       v
+------------------+                  +------------------+                   +------------------+
|  documents.py    |                  |   browser.py     |                   |   terminal.py    |
|  - validate_doc  |                  |   - list_dir()   |                   |  TerminalManager |
|  - dir_fd+link   |                  |   - safe_html()  |                   |  - 1MB RingBuf   |
+------------------+                  +------------------+                   +------------------+
       |                                      ^                                       |
       v                                      |                                       v
+-----------------------------------------------------------------------------------------------+
|                      受控宿主机存储 (Scoped Workspace Root) - scoped.py                         |
|                                                                                               |
|  .runtime/workspaces/{graph_id}/{sha256(tenant, project, thread)}/workspace/                 |
|  ├── uploads/     <-- 用户上传的文件 (不可变，SHA-256 命名) [documents.py / file_refs.py]     |
|  ├── work/        <-- Agent 自由发挥的临时工作区 (代码、临时输出、scratch)                      |
|  └── outputs/     <-- Agent 正式发布的最终交付物 (不可变，硬链接原子发布) [artifact_refs.py]     |
+-----------------------------------------------------------------------------------------------+
                                      |
                                      | (4) 执行命令 / 交互调试 (单向 bind 挂载)
                                      v
+-----------------------------------------------------------------------------------------------+
|                   Docker 隔离沙箱 (Ultra-Secure Docker Sandbox) - execution.py                 |
|                                                                                               |
|  --network=none (断网)                 --read-only (根系统只读)      --cap-drop=ALL (剥离特权)   |
|  --user=1000:1000 (普通用户)            --pids-limit=64 (防fork炸弹)  --memory=256m (限内存)    |
|  --tmpfs /tmp (只允许内存临时写)         --mount /workspace (受控挂载)  timeout 60s (硬超时)       |
+-----------------------------------------------------------------------------------------------+
```

---

## 三、五大核心支柱源码深度剖析

### 支柱一：路径隔离与防逃逸 (Path Scoping & Traversal Defense)

#### 1. 绝对路径禁止与三元组哈希 (`scoped.py`)
```python
# 核心源码截取：scoped.py
def thread_scope_hash(tenant_id: str, project_id: str, thread_id: str) -> str:
    scope = (tenant_id, project_id, thread_id)
    return hashlib.sha256(json.dumps(scope).encode("utf-8")).hexdigest()

def resolve_thread_workspace(tenant_id: str, project_id: str, thread_id: str, graph_id: str) -> Path:
    capability = graph_capabilities(graph_id)
    if not capability["files"]:
        raise ValueError("workspace_capability_unavailable")
    base = Path(os.getenv("RUNTIME_WORKSPACE_ROOT", ".runtime/workspaces")) / graph_id
    return hashed_thread_root(base, tenant_id, project_id, thread_id) / "workspace"
```
- **老王点评**：
  “看到没有？外部请求哪怕传递了什么 `../../etc/passwd`，根本没用！服务端根本不信任客户端传入的任何物理路径。所有的目录完全由后端的 `(tenant_id, project_id, thread_id)` 经过 SHA-256 算出 64 位纯十六进制哈希作为真实根目录，神仙也跳不出这个沙箱！”

#### 2. DeepAgents 虚拟路径映射 (`deepagent.py`)
- `resolve_workspace_virtual_path()`：智能体在虚拟环境中看到的是 `/workspace/foo.py`，底层代码先做 `Path.resolve()`，然后强校验 `resolved.is_relative_to(root)`。只要包含 `..`、`~`、`\` 或者软链接跳出根目录，直接抛出 `ValueError`。

---

### 支柱二：极度严苛 Docker 代码执行沙箱 (`execution.py`)

智能体调用 bash 工具执行代码时，必须走 `execute_in_workspace()`。老王带你看这套 Docker 命令参数有多绝：

```python
# execution.py: docker_workspace_args()
args = [
    "docker", "run", "--rm", "--pull=never",
    "--name", name,
    "--network=none",                    # 彻底掐断网络！禁止外联反弹 shell，禁止向外泄露数据
    "--read-only",                       # 容器自身镜像的根文件系统只读，别想在系统目录搞破坏
    "--cap-drop=ALL",                    # 剥离 Linux kernel 所有的特权能力 (Capabilities)
    "--user", f"{os.getuid()}:{os.getgid()}", # 以普通宿主机用户运行，容器内即使拿到 root 也是废的
    "--security-opt=no-new-privileges",  # 禁止通过 SUID/SGID 提权
    "--pids-limit=64",                   # 限制最多创建 64 个进程，彻底掐死 Fork 炸弹！
    "--memory=256m",                     # 内存死死卡在 256MB，谁也别想搞 OOM 爆宿主机
    "--cpus=1",                          # 最多占用 1 个 CPU 核心
    "--ulimit", "fsize=8388608:8388608", # 单个文件大小硬上限 8MB
    "--tmpfs", "/tmp:rw,nosuid,nodev,size=16777216", # /tmp 挂内存，大小 16MB，禁止 suid
    "--mount", f"type=bind,src={workspace},dst=/workspace",
]
```

#### 超时防挂起与输出截断
```python
# execution.py: execute_in_workspace()
args += [
    "sh", "-c",
    'timeout -s KILL "$1" sh -c "$2" > /tmp/output 2>&1; result=$?; '
    + f'head -c {MAX_OUTPUT} /tmp/output; exit "$result"',
    "runtime", str(seconds), command,
]
```
- **超时强杀**：单次命令执行最长不能超过 60 秒，超过直接 `SIGKILL` 强杀容器。
- **输出截断**：标准输出限制为 `MAX_OUTPUT = 128KB`。很多大模型写出死循环 `while True: print("草")`，如果服务不做截断，几秒钟就能生成几个 G 的日志把 Node.js/Python 进程撑爆，这里的 `head -c 131072` 在管道层面就把它截死！

---

### 支柱三：交互式 Web PTY 终端 (`terminal.py` & `terminal_child.py`)

前端 Web 控制台要像 VSCode 一样给开发者提供真实的交互式 Shell，这就是 `TerminalManager` 和 `TerminalSession` 干的事。

#### 1. 绕过 Python 多线程限制的妙招 (`terminal_child.py`)
在 Linux/macOS 下，启动伪终端需要执行 `ioctl(slave, TIOCSCTTY, 0)` 让从设备成为子进程的控制终端。但 Python 的 `subprocess.Popen` 在多线程环境下**严禁**使用 `preexec_fn`（极易造成线程死锁）：
```python
# terminal_child.py: 11 行神作
import fcntl, os, sys, termios

if __name__ == "__main__":
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    os.execvpe(sys.argv[1], sys.argv[1:], os.environ)
```
- **架构智慧**：主进程使用一个轻量级的 Python 独立脚本 `terminal_child.py` 作为中间跳板，在子进程起来后第一件事就是夺取控制终端，然后再 `os.execvpe` 启动真正的 Shell 或 Docker 容器！不依赖任何不安全的 `preexec_fn`，稳如泰山！

#### 2. 1MB 环形缓冲区与防并发冲突
```python
# terminal.py: TerminalSession
BUFFER_BYTES = 1024 * 1024  # 1MB 环形缓冲区
IDLE_SECONDS = 900          # 15 分钟无输入自动标记空闲超时
LIFETIME_SECONDS = 3600     # 1 小时绝对硬生命周期
RETAIN_SECONDS = 300        # 退出后保留 5 分钟供前端拉取最后日志
```
- **序列号幂等写入**：前端通过 WebSocket 往终端敲字，带有递增的 `sequence` 编号。如果网络抖动重发，服务端利用缓存的最后一次写入哈希做幂等处理，防止终端出现重复打字。
- **动态 Resize**：前端浏览器窗口缩放时，下发 `rows` 和 `cols`，服务端通过 `termios.TIOCSWINSZ` 修改 PTY 尺寸，并如果是 Docker 容器，同步执行 `docker exec ... stty` 动态下发尺寸！

---

### 支柱四：工作区浏览、分页与安全解包 (`browser.py`, `archives.py`)

#### 1. 带纳秒修改指纹的游标分页 (`browser.py`)
```python
# browser.py: WorkspaceBrowser.list_directory()
fingerprint = str(os.fstat(directory).st_mtime_ns)
if after and after.get("revision") != fingerprint:
    raise DocumentError("workspace_directory_changed", 409)
```
- **老王点评**：
  “很多菜鸟做文件分页就是简单的 offset/limit。试想一下：用户翻到第二页时，Agent 刚好在第一页删了一个文件、加了两个文件，分页直接错位或者死循环！
  老王这里的做法非常老辣：用目录的 `st_mtime_ns` 纳秒修改时间做成 `revision` 封进 Base64 游标里。只要翻页期间目录发生了变动，直接返回 `409 Conflict`，前端立刻感知并重新刷新，杜绝脏读！”

#### 2. 工业级防 Zip Slip 与解压炸弹 (`archives.py`)
```python
# archives.py: read_zip()
if len(entries) > 256 or sum(item.file_size for item in entries) > 20 * 1024 * 1024:
    raise ValueError("archive_size_limit")

for item in entries:
    name = item.filename
    path = PurePosixPath(name)
    mode = item.external_attr >> 16
    if (
        not name or len(name) > 1000 or name.startswith("/") or "\\" in name or ":" in name
        or any(ord(c) < 32 for c in name) or ".." in path.parts
        or stat.S_ISLNK(mode)                                    # 彻底封杀符号链接！
        or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR) # 拒绝设备文件、管道
        or item.flag_bits & 1                                    # 拒绝加密条目
    ):
        raise ValueError("unsafe_archive_entry")
    if item.file_size > 2 * 1024 * 1024 or item.file_size > max(1, item.compress_size) * 100:
        raise ValueError("archive_expansion_limit")              # 防御 100 倍解压炸弹！
```
- 没有任何文件被直接解压到物理磁盘！全部在内存中进行流式解压检查，黑客想构造恶意的 42.zip 把磁盘撑爆？门都没有！

---

### 支柱五：资产不可变发布与格式消杀 (`artifact_refs.py`, `html_preview.py`, `media.py`)

#### 1. 原子发布与内容寻址 (`artifact_refs.py`)
Agent 跑完分析任务，生成了一张图表或者一份报表，如何给用户交付？
```python
# artifact_refs.py: ArtifactWorkspace.publish()
def publish(self, path: str) -> dict:
    # 1. 严格限制来源：只能从临时生成目录发布
    if not path.startswith(("/workspace/work/", "/workspace/generated/", "/workspace/charts/")):
        raise DocumentError("artifact_source_denied")
    # 2. 校验文件内容和格式
    validate_artifact(data, extension)
    # 3. 计算 SHA-256，生成内容寻址文件名
    digest = hashlib.sha256(data).hexdigest()
    filename = digest + "." + extension
    # 4. 基于文件描述符与硬链接原子发布，杜绝并发撕裂
    directory = self.io._directory(("outputs",), create=True)
    temporary = ".publish-" + uuid4().hex
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    # 写入后 fsync 刷盘，并执行硬链接
    os.link(temporary, filename, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
```
- **核心价值**：
  1. **内容寻址（Content-Addressed）**：文件名就是内容的 SHA-256 哈希。内容变了，哈希必变；同一份内容发布多次，天然去重！
  2. **硬链接原子落盘（Atomic Hard Link）**：先写入隐藏临时文件 `.publish-<uuid>`，刷盘完成后一次性 `link` 到目标文件名，彻底杜绝了前端读到“只写了一半的文件”的并发竞争 Bug！

#### 2. 静态 HTML 预览极限消杀 (`html_preview.py`)
Agent 常常会生成 HTML 数据大屏或测试报表，前端如果直接用 `iframe` 或 `v-html` 展示，就是巨大的 XSS 攻击面。
`html_preview.py` 采用了外科手术级的安全防御：
- **严格标签白名单**：丢弃所有 `<script>`, `<iframe>`, `<object>`, `<svg>`, `<math>`, `<template>`。
- **严格属性白名单**：只允许 `class`, `id`, `style`, `width` 等排版属性，剥离所有 `onload`, `onclick`, `href="javascript:..."`。
- **强制注入全球最强 CSP**：
  ```http
  Content-Security-Policy: default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'none'; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'
  ```
  即使有漏网之鱼，浏览器在执行时也会被 CSP 彻底锁死，网络发不出去，脚本执行不了，Cookie/JWT 绝对偷不走！

#### 3. PPTX 与 XML 实体注入攻防 (`media.py`)
在校验用户上传或 Agent 生成的演示文稿时：
```python
# media.py: validate_media()
text = content.decode("utf-8-sig")
if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
    raise ValueError("xml_entities_denied") # 封杀 XXE 注入
if any(node.get("TargetMode") == "External" for node in root.iter()):
    raise ValueError("external_presentation_relationship") # 封杀外部 SSRF 探测
if name.lower().endswith("vbaproject.bin"):
    raise ValueError("macro_presentation_denied") # 封杀宏病毒
if not 1 <= len(slides) <= 20:
    raise ValueError("presentation_slide_limit") # 限制 20 页防拒绝服务
```

---

## 四、真实业务场景全链路演绎：DearFlowAgent 数据分析实战

我们以一个最典型的生产场景为例，看看这 15 个文件在一次任务中是如何紧密联合作战的：

### 场景：用户上传销售数据 Excel，让 DearFlowAgent 编写 Python 脚本分析并产出销售走势图和 HTML 报表

```
[用户上传 sales.xlsx]
       |
       v (1) documents.py
       +--> validate_document(): 检查 Excel 复合格式，确保没有宏病毒
       +--> 计算 SHA-256 (假设为 9f8a7c...)
       +--> DocumentWorkspace.put(): 原子写入 /workspace/uploads/9f8a7c.xlsx
       +--> 返回 FileRef

[DearFlowAgent 启动分析]
       |
       v (2) scoped.py & deepagent.py
       +--> 计算 thread_scope_hash("t-1", "p-1", "th-1") 确定物理根目录
       +--> 构建 DeepAgentWorkspace(virtual_mode=True)
       |
       v (3) Agent 调用 bash 工具执行 Python 脚本
       |    execution.py: execute_in_workspace()
       +--> 启动独立无网络 Docker 容器:
       |    docker run --network=none --read-only --memory=256m -v /workspace ...
       +--> 脚本读取 /workspace/uploads/9f8a7c.xlsx
       +--> 脚本分析数据，将中间图片生成到 /workspace/charts/32hex-uuid.png
       +--> 脚本将 HTML 报表生成到 /workspace/work/report.html
       +--> 容器在 60s 内成功退出，输出截断受控
       |
       v (4) Agent 调用发布工具发布正式交付物
       |    artifact_refs.py: ArtifactWorkspace.publish()
       +--> 将 /workspace/charts/32hex-uuid.png 发布为:
       |    /workspace/outputs/<sha256>.png
       +--> 将 /workspace/work/report.html 发布为:
       |    /workspace/outputs/<sha256>.html
       |
       v (5) 用户在前端控制台点击“预览成果”
       |    browser.py & html_preview.py
       +--> WorkspaceBrowser.list_directory("/workspace/outputs")
       |    返回文件列表（带 mtime 指纹的游标）
       +--> 用户点击查看 report.html:
       |    调用 WorkspaceBrowser.preview("/workspace/outputs/<sha256>.html")
       |    自动触发 html_preview.safe_html() 注入超强 CSP 并剥离危险标签
       +--> 前端安全渲染，毫无 XSS 风险！
```

---

## 五、切斯特顿栅栏：Naive vs Production 架构攻防对比

为什么不能用最直觉、最简单的写法？下面的对比告诉你每一个防护的血泪代价：

| 场景 / 攻击面 | Naive 粗暴实现 (菜鸟做法) | Production 生产实现 (`workspace/` 严苛做法) | 栅栏背后的血泪教训 (为什么必须这么干) |
| :--- | :--- | :--- | :--- |
| **路径解析** | 直接拼接路径：`os.path.join(base, user_path)` | `scoped.py` 单向哈希 + `deepagent.py` 严格 `is_relative_to` 校验 | 菜鸟写法会被 `../../../../etc/shadow` 或软链接直接逃逸，黑客分分钟读取宿主机任意机密！ |
| **代码执行** | `subprocess.run(command, shell=True)` | `execution.py` Docker 容器：`--network=none`、`--cap-drop=ALL`、`--memory=256m`、`--pids-limit=64` | 智能体一旦执行恶意脚本或者死循环 Fork 炸弹，不带沙箱的服务器瞬间死机，甚至被挂木马沦为肉鸡！ |
| **ZIP 解压** | `zipfile.ZipFile.extractall("/tmp")` | `archives.py` 内存流式解压，限制 256 条目、100倍膨胀率、封杀软链接与加密包 | 42.zip 只有几十 KB，解压出来有 4.5 PB！不设防的 `extractall` 会瞬间把整个云磁盘打满，造成全站崩溃！ |
| **文件发布** | `shutil.copy(src, dst)` | `artifact_refs.py` 临时文件落盘 + `fsync` + `dir_fd` + `os.link` 原子硬链接 | `copy` 写入大文件需要时间，前端并发请求读取时会读到只有一半的坏文件；原子硬链接在文件系统层面保证零撕裂！ |
| **HTML 报表展示** | 直接在网页上 `<div v-html="report">` | `html_preview.py` 严格 AST 白名单消杀 + 强制注入 `default-src 'none'` CSP | 报表如果包含外部引用的恶意脚本，会在管理员浏览器中自动静默窃取控制台权限与登录凭证（Stored XSS）！ |
| **PTY 终端会话** | 单纯的 Pipe 管道读取进程 stdout | `terminal.py` 真实 PTY + 1MB 循环缓冲区 + Base64 游标 + 动态 Resize + 进程组清理 | 普通管道没有 ANSI 颜色、不能动态调窗口，且用户关掉网页后，前台子进程在后台继续死循环消耗 CPU！ |

---

## 六、老王架构不变量与避坑清单

1. **绝对禁止接受外部客户端物理路径**：任何 API 入参凡是涉及文件路径的，必须只允许虚拟相对路径（如 `/workspace/...`），由 `scoped.py` 统一计算真实哈希根。
2. **严禁在主进程直接执行非信任代码**：所有非纯 Python 内置沙箱的脚本执行，必须委托给 `execution.py` 下的 Docker 容器，并强制断网（`--network=none`）。
3. **输出物必须内容寻址且不可变**：所有放入 `outputs/` 的交付物必须以 SHA-256 命名，一旦发布禁止修改，只能覆盖或追加。
4. **HTML 必须经由 `safe_html` 消杀**：凡是要在 Web 端做即时渲染的富文本或 HTML 预览，绝不能绕过 `html_preview.py`。
5. **PTY 必须注册看门狗自动清理**：终端会话绝不允许长生不老，必须受限于 900 秒空闲回收和 3600 秒强制生命周期回收。
