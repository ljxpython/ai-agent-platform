# 20260927 AI Harness 自我进化机制补全

## 背景

讨论"AI 完成功能后能否自我迭代"时，识别出三个已有 Harness 框架中缺失的闭环环节：

1. **经验无法自动沉淀**：项目完成后 AI 不会主动提议把踩坑加入 `docs/lessons/`
2. **standards 元数据不自动维护**：专项 done 后对应标准文件的 last_verified/status 不会自动刷新
3. **FEATURES.md 维护不一致**：完成卡里没有强制勾选项，经常被跳过

## 改动内容

### AGENTS.md

在「任务完成与汇报」章节末尾新增 **项目收尾反思** 段落，要求链路/治理改动完成时主动执行两件事：

**经验提案**：回顾本次项目是否遇到了值得沉淀的教训，若有，主动提议加入 `docs/lessons/`，等待用户确认后写入。

**标准文件毕业**：若本项目对应 `docs/standards/` 中的草案文件，且项目已达 done，将该文件 `status` 从 `draft` 改为 `active`，刷新 `last_verified`，更新 `docs/standards/README.md` 状态行。partial/blocked 不触发。

### .agents/skills/implement-feature/SKILL.md

Task Completion Card 合规检查列表新增一项：
```
- [ ] docs/FEATURES.md 已更新（新增/改变了功能能力时必须；纯修复/重构/文档标注「跳过」）
```
同步更新合规检查说明中对 FEATURES.md 的判断标准。

## 涉及文件

- `AGENTS.md`（1处改动）
- `.agents/skills/implement-feature/SKILL.md`（1处改动）

## 完成度对比

| 自我进化能力 | 改动前 | 改动后 |
|---|---|---|
| 项目状态记忆更新 | ✅ 有 | ✅ 有 |
| 验证留痕 | ✅ 有 | ✅ 有 |
| 改动追踪 | ✅ 有 | ✅ 有 |
| 经验自动提案 | ❌ 无 | ✅ 收尾反思强制触发 |
| 标准文件自动毕业 | ❌ 无 | ✅ done 时自动更新 |
| FEATURES.md 强制维护 | ❌ 软规则 | ✅ 完成卡必填项 |

## 永远不自动做的

AI 不在没有人工批准的情况下修改 AGENTS.md 和 Skills 本身（约束层需要人工监督）。
