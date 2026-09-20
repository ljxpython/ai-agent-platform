# 验证入口及首轮历史记录

最新验收计划与分层完成标准见 [05 验证与交付](05-verification-and-delivery.md)。本页仅保留首轮调研记录，不维护第二套测试清单。

## 首轮实际记录


- 已完成：两仓源码链路核查、既有设计与历史验收记录对照；本地参考 HEAD `44ae7505`。
- 已确认：本地 runtime `.env` 声明启用治理；未读取/输出模型密钥或数据库连接串；未验证运行中进程加载值。
- 首次前端基线命令包含 MemoryPage、memory.service 和 useDearGovernanceContext 三个测试文件；退出码 1，三套均在 Vite/esbuild 转换阶段报 `The service is no longer running`，0 条断言执行。此结果是测试基础设施失败，不能推断记忆业务测试失败或通过。
- 单 worker 定向复验：相同命令追加 `--maxWorkers=1 --minWorkers=1`，退出码 0；MemoryPage 4、memory.service 7、useDearGovernanceContext 4，共 3 文件 15 条通过，耗时 46.27 秒。这些测试使用 mock，不证明真实存储、权限和模型闭环。
- 未执行：真实 PG 写入测试、实际用户页面诊断、模型调用、端到端测试、安全/性能实测和回滚演练。本轮仅规划，未改业务代码，不对这些验收项作通过声明。
