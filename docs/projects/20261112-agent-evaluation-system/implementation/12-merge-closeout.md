# 合并与测试资源清理（2026-11-13）

用户明确批准经验沉淀、两个Worktree提交推送、合并main后验证、清理Worktree与测试数据库。生产发布不在范围。

## Git与既有功能保护

- Agent原主分支d7283189，先将主目录未提交的早期方案保存为9b14605，再合入已推送分支9ffef6d，合并提交539c112。六处冲突仅为早期方案与已验收文档；逐项比对后采用已验收状态，原方案在父提交完整保留。
- EvalFlow原主分支710ece1ad，已推送分支9929e0180，通过fast-forward合入main。
- 合并完成时，两仓文件树与各自已验证feature分支逐文件相同。Agent仅docs变化，原业务源码完整；EvalFlow官方mlflow/无变化。
- EvalFlow主工作区原有未跟踪docs/EVALUATION_GUIDE.md通过SHA256核对未变，不纳入本次提交。
- 远端feature分支保留；main的最终文档收尾提交在上述实现/合并提交之后。

## 主工作区真实复验

- 使用主工作区源码及独立临时Python环境安装锁定依赖，未共享Worktree虚拟环境或覆盖主环境依赖；实际导入路径为主仓eval_platform与mlflow。
- 后端tests/eval_platform：64 passed，1 warning。
- 前端8个相关套件：39 passed，包含原生Run详情、Trace结果/查询与新任务/数据集/比较组件。
- 主包与共享包TypeScript检查、Ruff和upstream-guard通过。
- 对应日志原位保留在主仓.local-stack/evaluation-merge-{pytest,jest,tsc,shared-tsc}.log；测试计数与退出码均实际核对。
- 合并没有改变已验证代码，因此不重复调用真实模型或重跑浏览器；此前真实E2E和最终构建证据仍有效。此前构建关闭既有全局ESLint插件的限制不变。

## 资源销毁结果

- 两仓local-stack停止，另对核实cwd/命令的fixture进程发送TERM；23419、25409、29256、25954、5011、9138、54629均无监听。
- 使用Agent标准destroy --confirm wt_3a133f065724，删除wt_3a133f065724_platform/runtime两个数据库及两个同名角色，所属Redis/Workspace/私有状态一起清理。
- 销毁前核实PG归属注释与零活动连接；销毁后数据库/角色完整清单比对，只少上述两个资源，其余元数据完全不变。
- 两个agent-evaluation Worktree在干净、feature已推送的前提下移除；EvalFlow所属data/mlflow.db、产物和私有配置随目录删除，注册表分配释放。
- 合并复验专属临时虚拟环境和pytest临时数据库目录删除。其他Worktree（含retention-governance）、主库和生产服务未清理。
- Git内截图、脱敏JSON与实施文档保留；原Worktree本地Run URL和未入Git的临时报告已失效。重跑时按操作手册重新准备隔离环境，不直接复用历史ID/端口。

## 经验

已按用户批准写入EvalFlow docs/lessons/eval-architecture.md第6节；Agent经验索引只维护指引，不复制两份规则。

状态：done（实现合并、本地验证与资源清理）；main推送以最终远端核验为准。
