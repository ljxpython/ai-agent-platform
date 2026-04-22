# platform-web 知识图谱验收清单

## 1. 环境

- [ ] `./scripts/platform-web-demo-down.sh` 正常
- [ ] `./scripts/platform-web-demo-up.sh` 正常
- [ ] LightRAG 参考服务可运行
- [ ] 登录后能进入本地图谱页
- [ ] `/api/identity/session` 不再阻塞走查

## 2. 页面结构

- [ ] 左上为轻量 labels 区
- [ ] 右上为轻量节点搜索区
- [ ] 左下为分组 toolbar
- [ ] 右侧为 properties/detail panel
- [ ] 右下为 legend
- [ ] 中间画布明显是主角

## 3. 图谱交互

- [ ] 点击节点显示节点详情
- [ ] 点击边显示边详情
- [ ] 节点搜索候选可用
- [ ] 选择搜索结果会聚焦节点
- [ ] zoom / fit / rotate / fullscreen 可用
- [ ] 点击不会导致图谱“消失”或镜头异常飞走

## 4. 视觉

- [ ] 节点颜色按 type 稳定
- [ ] legend 与节点颜色一致
- [ ] 标签密度合理
- [ ] 边样式克制、选中时有强调
- [ ] 面板和浮层不压过图谱画布

## 5. Mutation

- [ ] entity edit 可用
- [ ] relation edit 可用
- [ ] entity exists check 可用
- [ ] delete entity 可用
- [ ] delete relation 可用
- [ ] expand 可用
- [ ] prune 可用
- [ ] rename collision guidance 可用

## 6. 状态一致性

- [ ] 编辑后 panel 与 selection 状态正确
- [ ] 删除后 selection 不残留
- [ ] expand 不重复加节点/边
- [ ] prune 后无孤儿 selection
- [ ] mutation 失败时错误可见且页面可恢复

## 7. 构建与回归

- [ ] `pnpm typecheck` 通过
- [ ] `pnpm build` 通过
- [ ] `pytest -q apps/platform-api/tests/test_project_knowledge_contract.py` 通过

## 8. 对照验收

- [ ] 已与运行中的 LightRAG graph page 对照
- [ ] 当前仍然存在的 parity gap 已明确记录
