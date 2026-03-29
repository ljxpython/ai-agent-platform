# test_case_service

测试用例分析智能体服务。基于 `create_deep_agent` + 私有 Skills 体系，将模糊的产品需求转化为高质量、可执行、可量化的测试资产。

## 功能概述

| 能力 | 说明 |
|------|------|
| 需求分析 | PRD / 用户故事 / 功能描述解析，识别隐性需求与测试风险 |
| 测试策略 | 测试类型决策、优先级分层（P0-P3）、覆盖率目标制定 |
| 用例设计 | 六大设计技术（等价类、边界值、判定表、状态转换、场景法、错误猜测）|
| 质量评审 | 四维度自动评分（完整性、准确性、可执行性、规范性）|
| 数据生成 | 边界值、正常值、异常值完整测试数据集构造 |
| 格式化输出 | Markdown / JSON / CSV 多格式交付，可直接导入测试管理工具 |
| 多模态输入 | 图片 / PDF 通过 `MultimodalMiddleware` 自动解析后作为需求输入 |

## 架构说明

```
test_case_service/
├── graph.py          # make_graph 工厂函数（LangGraph 入口）
├── prompts.py        # SYSTEM_PROMPT（角色定位 + Skills 激活协议）
├── schemas.py        # 服务配置 DataClass + 路径工具函数
├── __init__.py       # 延迟导入（避免 pytest collect 阶段 import 错误）
├── skills/           # 私有 Skills 知识库
│   ├── requirement-analysis/SKILL.md
│   ├── test-strategy/SKILL.md
│   ├── test-case-design/SKILL.md
│   ├── quality-review/SKILL.md
│   ├── output-formatter/SKILL.md
│   └── test-data-generator/SKILL.md
└── tests/
    ├── __init__.py
    └── test_smoke.py # 冒烟测试（schemas / prompts / graph / 注册）
```

### 核心技术选型

- **`create_deep_agent`**：DeepAgent 模式，内置任务规划（`write_todos`）、文件系统工具、Skills 机制
- **`FilesystemBackend(virtual_mode=True)`**：Skills 从磁盘加载，运行时中间产物保存内存不落盘
- **`skills=["/skills/"]`**：加载 backend root 下 `skills/` 目录中的所有 SKILL.md
- **`MultimodalMiddleware`**：横切多模态解析能力，解析结果写入 `state.multimodal_summary`
- **`RuntimeContext`**：通过 `context_schema` 注入运行时上下文

## 配置项

通过 `RunnableConfig.configurable` 传入，所有配置项均有默认值：

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `test_case_multimodal_parser_model_id` | `str` | `iflow_qwen3-vl-plus` | 多模态解析模型 |
| `test_case_multimodal_detail_mode` | `bool` | `False` | 启用详细解析模式 |
| `test_case_multimodal_detail_text_max_chars` | `int` | `2000` | 详细模式最大字符数 |
| `test_case_backend_root_dir` | `str` | 服务包目录 | FilesystemBackend 根目录覆盖 |

## Skills 说明

Agent 通过 `SkillsMiddleware` 自动加载以下 Skills，按需激活：

| Skill | 激活场景 |
|-------|----------|
| `requirement-analysis` | 用户提供需求文档、PRD、用户故事、功能描述 |
| `test-strategy` | 需求分析完成后，制定整体测试方案 |
| `test-case-design` | 为具体功能点设计测试用例 |
| `quality-review` | 用例生成后自动执行质量自检 |
| `output-formatter` | 输出最终格式化测试用例交付物 |
| `test-data-generator` | 用户需要配套测试数据 |

## 在 LangGraph 中的注册

```json
"test_case_agent": {
  "path": "./runtime_service/services/test_case_service/graph.py:graph",
  "description": "测试用例分析智能体：..."
}
```

## 运行测试

```bash
cd apps/runtime-service
pytest runtime_service/services/test_case_service/tests/ -v
```

## 典型使用场景

1. **输入 PRD 文档** → Agent 依次执行：需求分析 → 测试策略 → 用例设计 → 质量评审 → 格式化输出
2. **上传原型图/截图** → MultimodalMiddleware 解析图片 → 触发需求分析流程
3. **上传已有用例集** → 直接触发 quality-review 评分
4. **指定导出格式** → output-formatter 输出 JSON/CSV 供工具导入
