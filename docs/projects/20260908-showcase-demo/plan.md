# Showcase Demo 实施方案

## 目标与边界

把展示用脚本收敛为可实际使用的工程助手，保持官方框架主体和少量二次封装。本轮优先完成 runtime-service；前端三栏界面和推理 token 的展示保留独立验收状态，不以此轮后端测试冒充前端完成。

## 真实示例

线程内提供一个小型 CSV 销售报表项目：CSV 数据、Python 报表脚本及使用说明。
- 只读分析：research 阅读文件，说明统计逻辑和问题，不触发修改。
- 实现需求：按需写 Todo，委派实现，审批文件修改与执行，真实运行 Python 检查结果。
- 文档检索：从明确允许的官方文档站点获取真实内容。
- 失败处理：保留真实退出码和错误；不得宣称未执行的测试已通过。

## 组合与所有权

graphs/showcase_demo.py 只导出 get_agent。服务内按实际职责保留：
- agent.py：认证事实、运行配置、官方 graph 组合和追踪。
- prompts.py：主 Agent 和子 Agent 的指令。
- subagents.py：显式子 Agent 及其工具/权限/HITL。
- backend.py：线程工作区、Docker 执行和资源初始化；复用官方 Backend 文件操作。
- tools.py：受限 HTTPS 文档抓取。
- skills/、examples/：随包发布的只读技能与线程初始化样例。
- README.md：教学说明、边界、部署和验证方法。

不建通用 Builder、Registry、插件系统或独立沙箱服务。没有自定义业务状态时使用 DeepAgents 官方 State，加 TodoListMiddleware 的状态扩展，去掉空字段和假完成工具。

## 授权和模型

复用 RuntimeConfigMiddleware，在主/子 Agent 的模型和工具边界检查可信身份、Context 哈希、scope 和工具 allowlist。工厂校验可信输入，但不替代执行期检查。测试模型和身份放在测试夹具，不在正式入口提供认证绕过开关。

模型 catalog HTTP 解析放在公共模型模块；get_agent 只取得已授权模型。线程 Backend 绑定当前可信身份和 thread，因此允许动态构图；schema/state 探测不得连接模型 catalog 或启动 Docker。探测图与执行图保持相同结构和 schema，探测模型不能用于实际推理。

## 工作区与执行

- 模型使用 /workspace/ 文件路径，shell 工作目录也是 /workspace。
- 线程目录由可信 tenant/project/thread 派生；使用可配置的数据根目录，不写死开发机路径。
- 包内资源通过 importlib.resources 定位，Skills 用 /skills/ 虚拟挂载，镜像/机器迁移不改变模型路径。
- 使用 Docker 容器运行真实 shell/Python，网络关闭、只读根文件系统、去 capabilities、进程/内存/CPU/时间/输出限制。
- 只绑定该线程工作区；命令结束容器销毁，工作区保留供后续 Run 和审批恢复。
- Shell 可以修改整个线程工作区，因此 runtime.tool.execute 明确表示可读写整个线程工作区的执行授权；只读 research 不提供 execute。
- Docker 守护进程/镜像不可用时明确失败，禁止回退到宿主机 shell 或假成功。
- 多副本部署需要共享工作区存储及一致的 Docker bind-mount 路径；不在本 Demo 新建分布式存储调度器。

## 部署与验证

showcase_demo 注册到独立 langgraph.demo.json，生产配置移除 showcase_demo。保持现有其他 graph 的配置不动。
验证顺序：授权与资源拒绝测试 → 官方工具/State/HITL/子图组合测试 → 真实 Docker 文件执行与隔离 → 可用环境下的远程调用。未通过或缺外部条件的项如实标为 partial/blocked。
