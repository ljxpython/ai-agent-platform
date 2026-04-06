# Platform API V2 Harness Playbook

这份文档定义 `platform-api-v2` 的工程 Harness。目的不是限制开发，而是把人和 AI 代理都锁进同一套高质量轨道里。

## 1. Harness 是什么

在这里，Harness 指的是一整套“可持续开发外壳”：

- 固定的模块边界
- 固定的文档入口
- 固定的权限与审计约束
- 固定的开发顺序
- 固定的验收动作

没有这层外壳，AI 代理很容易又把业务塞回 handler、把权限写散、把审计漏掉。

## 2. 人和 AI 的统一开发顺序

每次改动默认按这个顺序：

1. 先确认模块归属
2. 再确认 request/response 契约
3. 再确认权限边界
4. 再确认审计影响
5. 再确认是否进入 operation
6. 最后才写代码

## 3. 写代码前的必读文档

至少按这个顺序看：

1. `architecture-v2.md`
2. `engineering-standards.md`
3. `permission-standard.md`
4. `audit-standard.md`
5. `operations-standard.md`
6. `phase-1-checklist.md`

## 4. AI 代理禁止事项

- 直接在 handler 里写复杂业务
- 直接跨模块读写 repository
- 遇到权限问题就临时硬编码角色
- 审计没想明白就先不记
- 为了兼容旧坏结构继续复制旧实现

## 5. AI 代理最低交付物

结构性改动至少同步这些产物：

- 代码
- 对应文档
- checklist
- 最小验证命令

## 6. 验收清单

每轮最小验收都要能回答：

- 模块边界有没有变清楚
- 权限有没有被破坏
- 审计有没有新增盲区
- 前端契约有没有更稳定
- 长任务有没有继续走错误模型

## 7. 为什么这对持续编程有用

因为平台代码一旦没有统一轨道，AI 每一轮都可能换一种写法。Harness 的作用，就是把“可写的空间”收敛成“可维护的空间”。
