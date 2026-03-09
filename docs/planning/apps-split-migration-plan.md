# AITestLab 合仓迁移规划（platform + runtime）

## 1. 目标

本次迁移的目标不是立即重构代码，而是先把现有可运行的两套系统放入同一个仓库，并保持它们仍然可以独立运行。

目标系统拆成四部分：

- `platform-api`：平台后端
- `platform-web`：平台前端
- `runtime-service`：LangGraph 执行层
- `runtime-web`：直接调试 LangGraph 的前端

## 2. 迁移原则

### 2.1 第一阶段不改业务代码

- 不先融合依赖
- 不先改 import 路径
- 不先改启动逻辑
- 不先改环境变量约定

第一阶段只做：

- 仓库目录重组
- 根目录公共文档与脚本规划
- 运行验证

### 2.2 每个服务独立维护自己的依赖与环境

- `apps/platform-api`
  - 自己的 `.venv`
  - 自己的 `.env`
  - 自己的 `pyproject.toml`
  - 自己的 `uv.lock`
- `apps/platform-web`
  - 自己的 `package.json`
  - 自己的 `.env`
- `apps/runtime-service`
  - 自己的 `.venv`
  - 自己的 `graph_src_v2/.env`
  - 自己的 `pyproject.toml`
  - 自己的 `uv.lock`
- `apps/runtime-web`
  - 自己的 `package.json`
  - 自己的 `.env`

原因：

- 这样才能保持四部分代码仍可独立运行。
- 也能避免第一阶段就陷入依赖冲突与环境耦合。

## 3. 目标目录结构

```text
agent-platform/
├── README.md
├── apps/
│   ├── platform-api/
│   ├── platform-web/
│   ├── runtime-service/
│   └── runtime-web/
├── docs/
│   ├── planning/
│   ├── repo-layout.md
│   ├── local-dev.md
│   ├── env-matrix.md
│   └── migration-notes.md
├── scripts/
│   ├── dev-up.sh
│   ├── dev-down.sh
│   └── check-health.sh
└── archive/
    └── legacy-aitestlab/
```

说明：

- `apps/`：放四个独立可运行单元
- `docs/`：放根级公共文档
- `scripts/`：放统一启动/检查脚本
- `archive/`：用于后续归档旧代码（当前阶段先规划，不立即移动）

## 4. 四部分代码对应关系

### 4.1 `apps/platform-api`

来源：`/Users/bytedance/PycharmProjects/test2/agent_server`

实际放入：

- 平台后端代码主体
- `app/`
- `migrations/`
- `scripts/`（平台自己的）
- `docs/`（平台自己的）
- `pyproject.toml`
- `uv.lock`
- `alembic.ini`
- `main.py`
- `.env.example`

### 4.2 `apps/platform-web`

来源：`/Users/bytedance/PycharmProjects/test2/agent_server/agent-chat-ui`

实际放入：

- 平台前端全部代码

### 4.3 `apps/runtime-service`

来源：`/Users/bytedance/PycharmProjects/test2/langgraph_open_teach`

实际放入：

- `graph_src_v2/`
- `pyproject.toml`
- `uv.lock`
- `main.py`
- runtime 自己的 `README` / docs

### 4.4 `apps/runtime-web`

来源：`/Users/bytedance/PycharmProjects/test2/langgraph_open_teach/agent-chat-ui`

实际放入：

- 直连 LangGraph 调试前端全部代码

## 5. README 和文档策略

### 5.1 根目录 README

- 当前先保留 `AITestLab` 现有 `README.md`
- 后续逐步清理与改写旧内容
- 不在第一阶段大幅重写，避免与迁移任务相互干扰

### 5.2 各应用内部 docs

- 各自保留在自己代码目录下
- 用于记录本应用自己的开发、运行、排障文档

### 5.3 根目录 docs

根目录 `docs/` 只放全局内容，例如：

- 仓库整体目录结构
- 服务间关系
- 联调方式
- 环境变量矩阵
- 迁移说明

## 6. 旧代码归档策略

### 6.1 当前阶段

- 先不移动旧代码
- 先创建 `archive/legacy-aitestlab/` 作为目标归档位置
- 先完成新结构落位与验证

### 6.2 第二阶段

完成以下验证后，再考虑归档旧代码：

- `platform-api` 可独立启动
- `platform-web` 可独立启动
- `runtime-service` 可独立启动
- `runtime-web` 可独立启动
- 平台与 runtime 联调通过

归档动作建议：

- 将旧根目录历史代码整体迁入 `archive/legacy-aitestlab/`
- 不立即删除，保留回溯空间

## 7. 迁移 checklist

### Phase 1：仓库骨架

- [x] 创建 main 备份分支
- [x] 创建新的整合工作分支
- [x] 创建 `apps/`
- [x] 创建 `docs/planning/`
- [x] 创建 `scripts/`
- [x] 创建 `archive/legacy-aitestlab/`

### Phase 2：四部分代码迁入

- [x] 迁入 `platform-api`
- [x] 迁入 `platform-web`
- [x] 迁入 `runtime-service`
- [x] 迁入 `runtime-web`

### Phase 3：根级公共层

- [x] 补 `docs/repo-layout.md`
- [x] 补 `docs/local-dev.md`
- [x] 补 `docs/env-matrix.md`
- [x] 补 `docs/migration-notes.md`
- [x] 补 `scripts/dev-up.sh`
- [x] 补 `scripts/dev-down.sh`
- [x] 补 `scripts/check-health.sh`

### Phase 4：运行验证

- [ ] 验证 `platform-api`
- [ ] 验证 `platform-web`
- [ ] 验证 `runtime-service`
- [ ] 验证 `runtime-web`
- [ ] 验证平台联调 runtime

### Phase 5：旧代码归档

- [x] 将旧代码迁入 `archive/legacy-aitestlab/`
- [x] 清理根目录不再需要的旧结构
- [ ] 更新 README 的历史说明

## 8. 风险点

### 8.1 同名文件冲突

两个仓库都存在：

- `README.md`
- `pyproject.toml`
- `uv.lock`
- `main.py`
- `agent-chat-ui`

因此必须采用子目录隔离，不能直接摊平。

### 8.2 双前端并存带来的认知混淆

- `platform-web` 是主产品前端
- `runtime-web` 是 runtime 调试前端

需要在根文档中清楚说明职责差异。

### 8.3 依赖与环境不能过早合并

如果第一阶段就尝试共享：

- `.venv`
- Python 依赖
- Node 依赖

会显著增加迁移难度与出错概率。

## 9. 当前拍板结果

本次迁移已经确认：

- 采用 `apps/*` 目录组织四部分代码
- 当前阶段保持每个服务独立维护自己的环境与依赖
- 根目录 README 先保留现状，后续逐步改造
- 旧代码先做归档规划，不立即移动
