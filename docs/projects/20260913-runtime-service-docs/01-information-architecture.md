# 现状与信息架构

## 目标
把现有 README、knowledge、标准 Demo 和测试入口组织成清晰的事实来源，降低新开发者阅读成本。

## 方案设计
- `docs/README.md`：总入口和阅读地图。
- `docs/standards/`：当前生效的开发规范、边界和验收要求。
- `docs/knowledge/`：设计推导、借鉴资料和历史决策，标明 Draft/Superseded。
- `src/runtime_service/services/demo/showcase_demo/README.md`：可执行范式，代码与文档同步。
- `tests/`：可运行契约和验证证据；文档只引用命令，不虚构结果。

## 任务拆分
- [x] 盘点 knowledge 文档并标注权威级别。
- [ ] 重写 `docs/README.md` 为新人入口（后续可补充）。
- [x] 建立 standards 目录及最小规范集合。

## 验证要求与记录
- [ ] 新人按阅读顺序能定位代码、启动命令和测试命令。
- [ ] 所有规范链接可访问，旧设计不会被误当成当前事实源。

## 状态
进行中：正式 standards 已落地，docs/README.md 总入口重写后置。
