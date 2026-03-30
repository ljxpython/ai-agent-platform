# test_case_service 设计文档

## 1. 背景与目标

### 1.1 背景

在软件测试工作流中，测试用例设计是最耗时、最依赖经验的环节。测试工程师需要：
1. 深入理解 PRD、用户故事等需求文档
2. 运用多种测试设计技术（等价类、边界值等）系统化设计用例
3. 确保用例覆盖完整、质量达标
4. 输出符合团队规范的交付物

这一过程对经验要求高，且重复劳动多，是 AI 辅助的理想场景。

### 1.2 目标

构建一个「测试架构师级别」的 AI 智能体服务，能够：
- 接收任意形式的需求输入（文本、图片、PDF）
- 系统化执行需求分析 → 测试策略 → 用例设计 → 质量评审 → 格式化输出
- 输出专业、可执行、可量化的测试资产

---

## 2. 架构设计

### 2.1 技术选型决策

#### 为什么选 `create_deep_agent` 而非 `create_agent`？

| 对比维度 | `create_agent` | `create_deep_agent` |
|---------|---------------|---------------------|
| 任务规划 | 无内置规划 | 内置 `write_todos` 任务分解 |
| 文件系统 | 需手动集成 | 内置文件系统工具（读写、列目录）|
| Skills 机制 | 需手动实现 | 内置 `SkillsMiddleware` |
| 适用场景 | 简单问答、工具调用 | 多步骤复杂任务、需要规划的工作流 |

测试用例分析是典型的多步骤任务，需要规划（先分析需求，再制定策略，再设计用例），且需要 Skills 知识库驱动行为规范，因此选择 `create_deep_agent`。

#### 为什么使用 `FilesystemBackend(virtual_mode=True)`？

- **技能从磁盘加载**：SKILL.md 文件随代码部署，无需额外配置
- **运行时产物保存内存**：避免落盘权限问题，每次会话独立，天然隔离
- **中间产物无需落盘**：需求矩阵、策略文档、评审结果仍然保持会话态
- **正式结果单独持久化**：最终附件解析结果和正式测试用例通过服务私有工具写入 `interaction-data-service`

#### Skills 路径设计

```python
skills = ["/skills/"]
```

Backend root 指向服务包根目录（`get_service_root()`），`/skills/` 是相对于 root 的路径。
这样 Skills 文件与服务代码共处同一包，随代码版本管理，部署无需额外步骤。

### 2.2 组件依赖图

```
用户输入
    │
    ▼
MultimodalMiddleware          ← 图片/PDF 解析（横切）
    │
    ▼
create_deep_agent
    ├── model                 ← 通过 options.model_spec 解析
    ├── tools                 ← build_tools() + persist_test_case_results（服务私有工具）
    ├── middleware
    │   └── MultimodalMiddleware
    ├── system_prompt         ← SYSTEM_PROMPT（含 Skills 激活协议）
    ├── backend               ← FilesystemBackend(root=service_root, virtual_mode=True)
    ├── skills                ← ["/skills/"]（6个私有 SKILL.md）
    └── context_schema        ← RuntimeContext
```

### 2.3 数据流

```
RunnableConfig
    │
    ├── merge_trusted_auth_context()  → runtime_context
    ├── read_configurable()           → private_config
    ├── build_test_case_service_config() → service_config（默认主模型 + 多模态 + 默认项目 + 持久化开关）
    └── build_runtime_config()        → options（model_spec, system_prompt）
```

### 2.4 System Prompt 合并策略

```python
system_prompt = (
    f"{options.system_prompt}\n\n{SYSTEM_PROMPT}"
    if options.system_prompt
    else SYSTEM_PROMPT
)
```

**设计理由**：运行时覆盖（`options.system_prompt`）作为「前置补充」，服务自身的 SYSTEM_PROMPT 始终追加在后，保证 Skills 激活协议和行为约束不被覆盖。

---

## 3. Skills 设计

### 3.1 Skills 执行顺序

```
requirement-analysis
        ↓
test-strategy
        ↓
test-case-design ←──→ test-data-generator（按需）
        ↓
quality-review
        ↓
output-formatter
        ↓
test-case-persistence（按需）
```

### 3.2 各 Skill 职责边界

| Skill | 输入 | 输出 | 强制顺序 |
|-------|------|------|----------|
| `requirement-analysis` | 用户提供的需求文本/附件 | 需求矩阵（功能点、风险、优先级）| 必须首先执行 |
| `test-strategy` | 需求矩阵 | 测试类型决策、P0-P3 分层、覆盖率目标 | 需求分析后 |
| `test-case-design` | 测试策略 | 标准格式测试用例集 | 策略后 |
| `test-data-generator` | 字段规格 / 用例中的测试数据占位符 | 具体测试数据集 | 与用例设计并行或后置 |
| `quality-review` | 测试用例集 | 四维度评分报告 | 用例设计后（自动触发）|
| `output-formatter` | 所有阶段产出 | 格式化交付物（MD/JSON/CSV）| 最后执行 |
| `test-case-persistence` | 格式化后的正式测试用例 + 附件解析结果 | interaction-data-service 落库结果 | 仅正式落库时执行 |

### 3.3 SKILL.md 格式规范

```yaml
---
name: skill-name          # kebab-case，与目录名一致
description: 激活场景说明   # 供 Agent 判断何时激活此 Skill
---

# Skill 标题

## 激活场景     # 具体触发条件
## 执行流程     # Step by Step 操作规范
## 输出规范     # 期望的输出格式和内容
## 关键约束     # 必须遵守的规则
```

---

## 4. 配置设计

### 4.1 TestCaseServiceConfig

```python
@dataclass(frozen=True)
class TestCaseServiceConfig:
    default_model_id: str             # 服务级默认主模型（仅在未显式传 model_id 时生效）
    multimodal_parser_model_id: str   # 多模态解析模型
    multimodal_detail_mode: bool      # 是否启用详细解析
    multimodal_detail_text_max_chars: int  # 详细模式字符上限
    default_project_id: str           # 项目上下文缺失时的默认项目 ID
    persistence_enabled: bool         # 是否允许正式落库
```

使用 `frozen=True` 确保不可变性，避免运行时意外修改。

### 4.1.1 服务级默认模型策略

- `test_case_service` 默认主模型固定为 `deepseek_chat`
- 只有在调用方没有显式传 `model_id`，且环境变量 `MODEL_ID` 也未覆盖时，才注入这个服务级默认值
- 这样可以保证：
  - 当前 testcase 业务默认走工具遵循性更稳定的 DeepSeek
  - 其他 graph 仍然可以继续使用 runtime 全局默认模型
  - 调用方如果明确指定模型，仍然可以覆盖这个服务级默认值

### 4.2 Backend Root 解析逻辑

```python
def _resolve_backend_root_dir_path(private_config, *, agent_name) -> Path:
    override = private_config.get("test_case_backend_root_dir")
    if isinstance(override, str) and override.strip():
        return Path(override).expanduser()
    return get_service_root()  # 默认：服务包根目录
```

优先级：显式覆盖 > 服务包目录。覆盖机制用于测试和特殊部署场景。

---

## 5. 测试策略

### 5.1 测试层次

| 层次 | 文件 | 覆盖内容 |
|------|------|----------|
| 单元测试 | `tests/test_smoke.py` | schemas、prompts、路径解析、graph 工厂 |
| 集成测试 | 暂无（需真实模型）| make_graph 端到端执行 |

### 5.2 Graph 测试策略

`make_graph` 通过 `monkeypatch` 替换所有外部依赖：
- `merge_trusted_auth_context`、`build_runtime_config`：替换为返回 DummyOptions
- `resolve_model`、`apply_model_runtime_params`：直接透传
- `build_tools`：返回固定 fixture
- `create_deep_agent`：捕获调用参数进行断言

这样可以在不依赖真实模型和网络的情况下验证装配逻辑的正确性。

---

## 6. 已知限制与后续优化方向

| 限制 | 影响 | 优化方向 |
|------|------|----------|
| `virtual_mode=True` 不持久化 | 会话结束后中间产物丢失 | 支持 `virtual_mode=False` + 配置化存储路径 |
| 无流式输出进度反馈 | 长任务用户体验差 | 集成 LangGraph streaming |
| Skills 无版本管理 | SKILL.md 变更无法灰度 | 引入 skills 版本号机制 |
| 默认项目 ID 仍是过渡方案 | 真实项目上下文尚未完全透传 | 后续由 runtime.context / runtime.config 正式承载 |
| 无用例去重 | 多轮对话可能产生重复用例 | 在 interaction-data-service 增加幂等键/批次去重 |
| 旧 `usecase-generation` 结果域已退役 | 旧服务仍可能残留历史依赖 | 后续下线 `usecase_workflow_agent` 并清理历史文档 |
