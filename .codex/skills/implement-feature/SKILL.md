---
name: implement-feature
description: AI 在项目文档（docs/projects/{YYYYMMDD}-{项目名}/）已存在时，实现任务过程中自动调用（不需要用户手动触发），记录改动细节到 implementation/ 目录。跳过条件：单项目改动的小改动不需要创建实现记录。
---

# Implement Feature（实现功能）

实现具体功能，并记录详细的改动信息。**这是 AI 在链路改动/治理改动的实现过程中自动调用的 Skill**，跟着 `plan-project` 创建的项目文档走。

## 触发条件

- 已有项目文档（docs/projects/{YYYYMMDD}-{项目名}/）
- 准备开始实现某个任务
- 需要记录改动的文件、函数、理由

## 跳过条件

- 单项目改动的小改动，直接实现+commit，不创建实现记录

## 两层分工原则

| 层 | 文档 | 职责 |
|---|---|---|
| **进度层** | `tasks.md` / 子专题文档的「任务拆分」小节 | 做没做完、结果摘要——所有人看进度看这里 |
| **细节层** | `implementation/` | 怎么做的、代码对比、踩坑记录——只有想了解细节时才翻 |

两层严格分开：tasks.md 不堆代码细节，implementation/ 不作为进度来源。

## 工作流

1. **读取任务列表**
   - 标准模板：读取 `docs/projects/{YYYYMMDD}-{项目名}/tasks.md`
   - 多专题模板（无全局 `tasks.md`）：读取对应子专题文档 `docs/projects/{YYYYMMDD}-{项目名}/{序号}-{子专题}.md` 里的「任务拆分」小节
   - 确认要实现的任务

2. **实现代码**
   - 编写代码
   - 添加测试
   - 确保代码质量

3. **记录改动细节**（细节层）
   - 在 `docs/projects/{YYYYMMDD}-{项目名}/implementation/` 下创建记录文件
   - 记录具体改动的文件、函数、理由（可选，不做不影响进度判断）

4. **输出 Task Completion Card**（进度层，必做）

   每个 Task 完成后，在 `tasks.md`（或对应子专题文档）中将该 Task 更新为以下完成卡格式：

   ```markdown
   ### Task X.X: {任务名称}
   - **改动内容：** {具体做什么}
   - **代码位置：** `apps/xxx/src/xxx.py` → `ClassName.function_name()`
   - **预期结果：** {改完后的行为或输出}
   - **验证项：** {验证命令或步骤} → ✅ 通过 / ❌ 失败（原因：xxx）
   - **状态：** `[x]` 已完成 {YYYY-MM-DD} → 见 implementation/xx-xxx.md（如有）
   - **合规检查：**
     - [x] 代码实现完成
     - [x] 验证项已执行（结果写在验证项行里）
     - [x] tasks.md 状态已更新
     - [ ] CONTEXT.md 已更新（此 Task 未涉及服务状态变化，跳过）
   ```

   **合规检查说明：**
   - 前三项必须勾选，不得跳过
   - CONTEXT.md 更新：Task 涉及服务能力/状态变化时必须更新；纯内部重构/bugfix 可标注"跳过"
   - `tasks.md` 是进度的唯一来源，任何人看进度看这里



## 实现记录模板

文件名：`docs/projects/{YYYYMMDD}-{项目名}/implementation/{序号}-{简短描述}.md`

```markdown
# {改动标题}

## 改动时间
{YYYY-MM-DD}

## 相关任务
- Task X.Y: {任务名称}

## 改动文件
- `apps/xxx/src/models.py`
- `apps/xxx/src/api.py`
- `apps/xxx/tests/test_models.py`

## 具体改动

### 1. {改动点1}
**位置：** `models.py:15-45`

**改动前：**
```python
class OldModel:
    def __init__(self):
        # 旧实现
```

**改动后：**
```python
@dataclass
class NewModel:
    field1: str
    field2: int
    # 新实现
```

**理由：** {为什么这样改}

**影响：**
- ✅ 向后兼容 / ⚠️ 需要适配
- {其他影响}

### 2. {改动点2}
**位置：** `api.py:78-120`

**改动内容：**
- 新增 `/api/xxx` 接口
- 参数：{参数说明}
- 返回：{返回值说明}

**测试：**
- 新增 `test_api_xxx_success()`
- 新增 `test_api_xxx_failure()`

## 验证
- [x] 单元测试通过
- [x] 类型检查通过
- [x] Lint 通过
- [ ] 集成测试（待执行）

## 注意事项
- {需要注意的点1}
- {需要注意的点2}
```

## 示例工作流

### 场景：实现 Runtime 数据建模重构

1. **读取任务**（AI 自动进行，无需用户触发）
   ```bash
   读取 docs/projects/20260908-runtime-modeling-refactor/tasks.md
   确认要实现 Task 1.1: 重构 RuntimeConfig 数据类
   ```

2. **实现代码**
   ```python
   # apps/runtime-service/src/models/runtime.py
   @dataclass
   class RuntimeConfig:
       model_id: str
       tools: List[Tool]
       # ... 新实现
   ```

3. **记录改动**
   创建 `docs/projects/20260908-runtime-modeling-refactor/implementation/01-runtime-config-refactor.md`

4. **更新任务**
   在 `tasks.md` 中标记：
   ```markdown
   - [x] Task 1.1: 重构 RuntimeConfig 数据类 ✅ 2024-09-07
   ```

## 文件命名规范

```
implementation/
├── 01-数据建模.md           # 数据建模相关
├── 02-API契约.md            # API 契约相关
├── 03-业务逻辑.md           # 业务逻辑相关
└── 04-测试.md               # 测试相关
```

## 记录要点

### 必须记录
- ✅ 改动的具体文件和行号
- ✅ 改动前后的代码对比（关键部分）
- ✅ 改动理由和影响
- ✅ 新增的测试

### 不要记录
- ❌ 大段完整代码（代码在 Git 里）
- ❌ 重复的信息（如果已经在 plan.md 里说明）
- ❌ 无关细节（如格式化调整）

## 最佳实践

1. **边实现边记录**
   - 不要等全部完成再记录
   - 每完成一个改动点就记录

2. **突出重点**
   - 记录关键改动，不是流水账
   - 重点说明"为什么"而不是"是什么"

3. **便于查找**
   - 文件路径要完整
   - 函数名要准确
   - 行号要标注

4. **保持更新**
   - 如果后续调整，更新记录
   - 标注修改时间

## 注意事项

- 对于单项目改动的小改动，可以不创建实现记录
- 对于链路改动、治理改动，必须记录详细信息
- 记录的目的是帮助其他人理解，不是应付检查
