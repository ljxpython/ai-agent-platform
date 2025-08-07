# DSPy 系统提示词优化完整指南

## 🎯 核心概念

DSPy 提示词优化的核心是**自动化地找到最优的提示词组合**，而不是手动调试。

### 关键组件

1. **Signature（签名）**: 定义任务的输入输出格式
2. **Module（模块）**: 包含推理逻辑的组件
3. **Teleprompter（优化器）**: 自动优化提示词的工具
4. **Metric（评估指标）**: 衡量输出质量的函数

## 🚀 快速开始

### 1. 基础设置

```python
import dspy
from dspy.teleprompt import BootstrapFewShot

# 配置模型
lm = dspy.LM("deepseek-chat", api_key="your_key", api_base="your_url")
dspy.configure(lm=lm)
```

### 2. 定义任务签名

```python
class TaskSignature(dspy.Signature):
    """任务描述：这里写清楚你要做什么"""

    input_field = dspy.InputField(desc="输入字段描述")
    output_field = dspy.OutputField(desc="输出字段描述")
```

### 3. 创建模块

```python
class TaskModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predictor = dspy.ChainOfThought(TaskSignature)

    def forward(self, input_field):
        return self.predictor(input_field=input_field)
```

### 4. 准备训练数据

```python
train_data = [
    dspy.Example(
        input_field="示例输入",
        output_field="期望输出"
    ).with_inputs("input_field"),
    # 更多示例...
]
```

### 5. 优化提示词

```python
# 定义评估指标
def quality_metric(example, pred, trace=None):
    return 1.0 if pred.output_field else 0.0

# 创建优化器
teleprompter = BootstrapFewShot(
    metric=quality_metric,
    max_bootstrapped_demos=4,
    max_labeled_demos=2
)

# 优化模块
module = TaskModule()
optimized_module = teleprompter.compile(module, trainset=train_data)
```

## 🔧 优化器详解

### 1. BootstrapFewShot（推荐）

**最常用的优化器，适合大多数场景**

```python
teleprompter = BootstrapFewShot(
    metric=quality_metric,           # 评估指标
    max_bootstrapped_demos=4,        # 最大自举示例数
    max_labeled_demos=2,             # 最大标注示例数
    max_rounds=3                     # 最大优化轮数
)
```

**优点**：
- 稳定可靠
- 适用范围广
- 计算成本适中

### 2. BootstrapFewShotWithRandomSearch

**在 BootstrapFewShot 基础上增加随机搜索**

```python
teleprompter = BootstrapFewShotWithRandomSearch(
    metric=quality_metric,
    max_bootstrapped_demos=4,
    num_candidate_programs=10,       # 候选程序数量
    num_threads=4                    # 并行线程数
)
```

**优点**：
- 更全面的搜索
- 可能找到更优解

**缺点**：
- 计算成本更高

### 3. MIPRO（最先进）

**最新的优化器，效果最好但计算成本最高**

```python
teleprompter = MIPRO(
    metric=quality_metric,
    num_candidates=20,               # 候选数量
    init_temperature=1.0             # 初始温度
)
```

### 4. LabeledFewShot（简单快速）

**直接使用标注示例，无需优化**

```python
teleprompter = LabeledFewShot(k=3)  # 使用3个示例
```

## 📊 评估指标设计

### 基础指标

```python
def basic_metric(example, pred, trace=None):
    """基础评估：检查输出是否存在"""
    return 1.0 if pred.output_field and len(pred.output_field.strip()) > 0 else 0.0
```

### 内容质量指标

```python
def content_quality_metric(example, pred, trace=None):
    """内容质量评估"""
    if not pred.output_field:
        return 0.0

    # 检查长度
    if len(pred.output_field.strip()) < 10:
        return 0.2

    # 检查关键词
    keywords = ["方法", "步骤", "建议", "原因"]
    if any(kw in pred.output_field for kw in keywords):
        return 1.0

    return 0.6
```

### 准确性指标

```python
def accuracy_metric(example, pred, trace=None):
    """准确性评估"""
    if hasattr(example, 'expected_output'):
        # 简单的字符串匹配
        if example.expected_output.lower() in pred.output_field.lower():
            return 1.0
    return 0.0
```

## 💡 最佳实践

### 1. 训练数据准备

**质量 > 数量**
- 至少准备 3-5 个高质量示例
- 示例要覆盖不同的输入类型
- 输出要准确、完整、一致

```python
# ✅ 好的示例
good_examples = [
    dspy.Example(
        question="如何提高工作效率？",
        answer="1. 制定优先级列表 2. 使用时间管理工具 3. 减少干扰因素"
    ).with_inputs("question"),

    dspy.Example(
        question="Python如何处理异常？",
        answer="使用try-except语句：try块包含可能出错的代码，except块处理异常"
    ).with_inputs("question")
]
```

### 2. 任务描述优化

**清晰具体的任务描述**

```python
# ❌ 模糊的描述
class BadSignature(dspy.Signature):
    """回答问题"""
    question = dspy.InputField()
    answer = dspy.OutputField()

# ✅ 清晰的描述
class GoodSignature(dspy.Signature):
    """根据用户问题提供准确、有用的回答，包含具体的步骤或方法"""
    question = dspy.InputField(desc="用户的具体问题")
    answer = dspy.OutputField(desc="详细的回答，包含具体步骤或建议")
```

### 3. 迭代优化策略

```python
def iterative_optimization(base_module, train_data, val_data):
    """迭代优化策略"""

    best_score = 0
    best_module = base_module

    # 尝试不同的优化器
    optimizers = [
        BootstrapFewShot(metric=quality_metric, max_bootstrapped_demos=2),
        BootstrapFewShot(metric=quality_metric, max_bootstrapped_demos=4),
        BootstrapFewShotWithRandomSearch(metric=quality_metric, num_candidate_programs=5)
    ]

    for optimizer in optimizers:
        try:
            optimized = optimizer.compile(base_module, trainset=train_data, valset=val_data)
            score = evaluate_module(optimized, val_data)

            if score > best_score:
                best_score = score
                best_module = optimized

        except Exception as e:
            print(f"优化器失败: {e}")

    return best_module, best_score
```

## 🎯 实际应用示例

### 文本分类优化

```python
# 运行简化版本
python examples/dspy_demo/prompt_optimization_simple.py
```

### 问答系统优化

```python
# 运行完整版本
python examples/dspy_demo/prompt_optimization_guide.py
```

## 🔍 提示词提取

### 查看优化后的提示词

```python
def extract_optimized_prompts(optimized_module):
    """提取优化后的提示词"""

    # 获取示例
    if hasattr(optimized_module, 'predictor'):
        predictor = optimized_module.predictor

        if hasattr(predictor, 'demos'):
            print(f"包含 {len(predictor.demos)} 个优化示例:")
            for i, demo in enumerate(predictor.demos):
                print(f"示例 {i+1}: {demo}")

        if hasattr(predictor, 'signature'):
            print(f"任务签名: {predictor.signature}")
```

## ⚡ 性能优化技巧

### 1. 减少计算成本

```python
# 使用较少的示例数
teleprompter = BootstrapFewShot(
    max_bootstrapped_demos=2,  # 减少到2个
    max_labeled_demos=1,       # 减少到1个
    max_rounds=1               # 只运行1轮
)
```

### 2. 并行优化

```python
# 使用多线程
teleprompter = BootstrapFewShotWithRandomSearch(
    num_threads=4,             # 4个并行线程
    num_candidate_programs=8   # 8个候选程序
)
```

### 3. 缓存机制

```python
# 启用缓存
lm = dspy.LM("deepseek-chat", cache=True)  # 启用缓存
```

## 🚨 常见问题

### 1. 优化失败

**原因**：训练数据质量差、评估指标不合适
**解决**：检查数据质量，简化评估指标

### 2. 效果不佳

**原因**：任务描述不清晰、示例不够代表性
**解决**：优化任务描述，增加多样化示例

### 3. 计算成本高

**原因**：参数设置过高
**解决**：减少示例数量，使用简单优化器

## 📈 效果评估

### 对比测试

```python
def compare_modules(base_module, optimized_module, test_data):
    """对比基础模块和优化模块"""

    base_score = evaluate_module(base_module, test_data)
    opt_score = evaluate_module(optimized_module, test_data)

    improvement = (opt_score - base_score) / base_score * 100
    print(f"基础模块得分: {base_score:.2f}")
    print(f"优化模块得分: {opt_score:.2f}")
    print(f"提升幅度: {improvement:.1f}%")
```

通过这个完整的指南，您可以系统地使用 DSPy 来优化您的系统提示词，获得最佳的性能表现！
