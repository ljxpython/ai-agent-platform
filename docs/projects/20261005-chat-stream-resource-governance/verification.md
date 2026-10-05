# 验证

## Phase
2026-10-05：只读确认上述运行已成功、PG 有 terminal 事件；Redis 默认 DB 7 运行缓存无过期，系统 watchdog 报告和保存日志相互印证。此前已执行限定终态缓存清理：79 个符合条件、释放估算约 4.2 GB；2026-10-05 10:25 复查 dry-run：eligible=0、retained=22、unknown=618；Redis used_memory=13.86 GiB，unknown 未清理。

T1：维护脚本边界测试 1 passed；未知、运行中、中断和近期缓存均保留。
T2：GraphHarbor 组合回归 179 passed / 7 skipped，额外终态清理与分页定向 9 passed；锁步、ruff、mypy、双包构建和隔离 wheel 导入通过，双包已发布并独立安装验证，现役 Runtime API/Worker 已升级重启。
T3：前端全量单测 474 passed / 1 skipped，类型/构建通过，lint 0 errors / 27 warnings；浏览器验收仍在执行。

## Final

2026-10-05 Final：done。GraphHarbor post39 已发布并安装验证；Redis 未知遗留 618 个 run-stream 已按授权删除，业务 Redis 保留 22 个已有且未达到清理条件的运行流；隔离浏览器验收中新生成的缓存实测 TTL 为 3446–3584 秒；active_runs=0。前端 474 passed/1 skipped、定向连接/会话 44 passed、多会话浏览器 1 passed（39.9s）、权限浏览器 4 passed（13.4s）、生产构建和类型检查通过；Runtime API/Worker 已重启。不得以此前权限项目的测试代替本次多会话与容量验收。

2026-10-05 用户进一步明确授权删除未知缓存：再次按 run_id 在 PG 核对不存在后 UNLINK 618 个 run-stream，未碰其他 Redis 键；异步释放完成后 used_memory=611541472 bytes（583.21 MiB），RSS 2.46 GiB，lazyfree_pending_objects=0。

最终浏览器证据：/tmp/platform-resource-browser-final.log，详细报告 /var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/q5-message-t9g7cxb7/browser-report.json；三个会话均完成至少两个 Run，全部 success，补充 human 消息恰好一次、AI 回复包含补充内容，连续 6 次切换 SSE 稳定 ≤2，页面同源权限 GET 200，无页面异常。权限证据 /tmp/resource-permissions-browser.log。

资源数据：清理前峰值 Redis used_memory 18.01 GiB，先清确认终态约 4.2 GB，再按用户明确授权清 618 个未知遗留键；最终约 586 MiB。仅能确认资源异常与 WindowServer watchdog 同期，不能断言是死机的唯一原因。

限制：未部署任何远端平台服务；PyPI 为正式发布，本地三服务已使用当前源码/新依赖。系统 RSS 不等于 Redis used_memory，不相加计算共享页。旧测试的 7 项 skip 未计为通过；lint 27 条既有 warning、Vite chunk warning 保留。
