# 本地栈启停脚本基于真实进程与端口归属管理优化

## 背景
在执行 `bash scripts/local-stack.sh start` 时，若之前服务异常退出、热重载产生孤儿工作进程或 PID 文件丢失，会导致端口（如 2142）被残留的 Python / Uvicorn 真实进程占用。
原先的校验逻辑仅凭 PID 文件判断进程托管状态，在无 PID 文件或 PID 变动时抛出：
`ERROR port 2142 is already in use; refusing to kill an unmanaged process`
且 `stop` 无法识别 Uvicorn reload 派生的 multiprocessing 孤儿 worker，导致用户陷入“停不掉、启不来”的死锁状态。

## 改动内容
1. **真实进程识别与快速短路 (`scripts/local_stack_processes.py`)**：
   - 增加监听端口所有权检测：通过 `lsof -ti tcp:<port> -sTCP:LISTEN` 定位占用端口的真实 PID，核验其 cwd、虚拟环境 executable 及参数是否归属当前仓库应用目录；
   - 支持检测 Uvicorn / Multiprocessing 孤儿 worker 进程；
   - 优化短路检查与进程树递归逻辑，消除全量遍历 `lsof` 带来的性能开销；
   - 增加 `port-owner`、`find` 等子命令，精准区分 `free`、`owned`（属于本项目）与 `external`（属于外部无关进程）。
2. **启动与停止健壮性增强 (`scripts/local-stack.sh`)**：
   - `check_port`：当端口被本仓库的残留/孤儿进程占用时，自动识别并优雅终止真实进程，释放端口后继续启动，不再无脑拒绝；若被外部无关进程占用，安全拒绝并提示具体 PID 与命令；
   - `stop_process`：按配置端口与进程特征彻底终止父子进程树，超时自动升级 SIGKILL；
   - `status`：在 PID 文件缺失时能够探测并展示真实运行的 PID。
3. **自动化测试覆盖 (`scripts/test_local_stack_processes.py`)**：
   - 新增端口所有者检测、自动清理真实残留进程、以及外部进程安全隔离保护的单元测试。

## 涉及文件
- `scripts/local_stack_processes.py`
- `scripts/local-stack.sh`
- `scripts/test_local_stack_processes.py`
- `docs/FEATURES.md`
