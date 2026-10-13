# Runtime Service 标准文档

这里记录当前生效的开发规则。新开发者按以下顺序阅读：

1. [资料导航](./runtime-service-reading-guide.md)
2. [开发范式与规则](./runtime-service-development-standard.md)
3. [运行与验证](./runtime-service-onboarding-and-verification.md)
4. [通用后台任务接入](./background-task-integration.md)（受管 Docker；正式启用仍受专项门禁限制）
5. [模型上下文隐私保护](./model-context-privacy.md)
6. [已采集用量聚合查询](runtime-service-development-standard.md#已采集用量的受控聚合查询)（可重建投影、整链路容量和恢复已验，B01已解除；[专项](../../../../docs/projects/20261011-token-usage-dashboard/README.md)）
7. [本地 / 远端沙箱运行](../../../../docs/runbooks/runtime-sandbox-node.md)（三模式、持久绑定、单节点 mTLS、回收与恢复；公网门禁以专项为准）

## 权威优先级

1. 可执行代码与 `tests/` 契约
2. 本目录 `standards/`
3. `src/runtime_service/services/demo/showcase_demo/README.md` 及其代码
4. `docs/knowledge/` 设计推导和借鉴资料

发现文档与代码冲突时，先修正文档或建立变更记录，不要照着过期资料开发。
