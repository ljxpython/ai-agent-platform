# 方案

## 背景

`local-stack.sh` 只将 Showcase 的 execute 设为 local；Dear Agent 的 `DearWorkspaceBackend.aexecute()` 固定调用 Docker。终端另有独立后端变量，行为不一致。

## 实现

- 所有执行入口通过 `RUNTIME_BACKEND=local|docker` 选择后端；未设置时为 Docker。
- 本地栈默认导出 `RUNTIME_BACKEND=local`，命令行环境变量优先于 `.env`。Runtime API 和 Worker 共享此值。
- local 复用已安装的 `LocalShellBackend`，工作目录为线程的 `work/`，不继承服务进程环境；传入工作区及技能目录变量供 shell 使用。Docker 路径、审批和文件工具权限保持原样。
- Runtime 常规依赖提供数据分析和 PPT 脚本所需的 Python 包，使独立运行时仅需设置 `RUNTIME_BACKEND=local`。
- 更新 Dear Agent 指令，使本地模式使用宿主路径或相对路径，容器模式继续使用虚拟路径。Showcase 和交互终端使用同一开关。

## 边界

本地 shell 与 Showcase local 模式相同，不具有容器文件系统、网络或资源隔离；文件工具的虚拟路径权限不限制 shell。仅在受信任的个人开发环境启用，正式环境默认 Docker。切换后需重启 Runtime API/Worker。

## 验证

验证默认和显式后端选择、命令与工作区文件互通、环境变量不泄露、退出码/超时、审批后的真实工具链，以及本地栈传参。
