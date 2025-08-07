# DSPy 医疗陷阱检测器

## 问题分析

您遇到的错误 `AttributeError: module 'dspy' has no attribute 'optimize'` 是因为：

1. **DSPy 未安装**: 项目中没有安装 `dspy-ai` 包
2. **API 使用错误**: DSPy 没有 `dspy.optimize` 方法

## 解决方案

### 1. 安装 DSPy

```bash
# 使用 Poetry 安装
poetry add dspy-ai

# 或使用 pip 安装
pip install dspy-ai
```

### 2. 修正代码

原代码中的问题：

```python
# ❌ 错误的 API
optimized_detector = dspy.optimize(TrapDetector(), train_data, num_samples=10)
```

正确的 DSPy 使用方式：

```python
# ✅ 正确的 API
from dspy.teleprompt import BootstrapFewShot

# 定义评估指标
def metric(example, pred, trace=None):
    return example.conclusion.lower() == pred.conclusion.lower()

# 使用 teleprompter 进行优化
teleprompter = BootstrapFewShot(metric=metric, max_bootstrapped_demos=4)
optimized_detector = teleprompter.compile(detector, trainset=train_data)
```

### 3. 主要修改点

1. **签名定义**: 使用 `dspy.Signature` 定义输入输出
2. **模块结构**: 继承 `dspy.Module` 并使用 `dspy.ChainOfThought`
3. **数据格式**: 使用 `dspy.Example` 包装训练数据
4. **优化方法**: 使用 `BootstrapFewShot` 等 teleprompter

## 文件说明

- `dspy_demo.py`: 原始代码（有错误）
- `dspy_demo_fixed.py`: 修正后的代码
- `alternative_solution.py`: 不依赖 DSPy 的替代方案

## 运行方式

```bash
# 确保已安装 DSPy
poetry add dspy-ai

# 运行修正后的代码
python examples/dspy_demo/dspy_demo_fixed.py

# 或运行替代方案
python examples/dspy_demo/alternative_solution.py
```

## DSPy 核心概念

1. **Signature**: 定义任务的输入输出格式
2. **Module**: 包含推理逻辑的可组合组件
3. **Teleprompter**: 用于优化和训练的工具
4. **Example**: 训练数据的标准格式

## 常见错误

1. `dspy.optimize` 不存在 → 使用 `teleprompter.compile`
2. `dspy.Prompt` 不存在 → 使用 `dspy.Signature`
3. 数据格式错误 → 使用 `dspy.Example`
