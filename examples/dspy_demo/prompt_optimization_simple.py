"""
DSPy 提示词优化 - 简化实用版本

专注于最实用的提示词优化方法，快速获得最优提示词
"""

import dspy
from dspy.teleprompt import BootstrapFewShot

from examples.conf.config import settings

# 配置模型
lm = dspy.LM(
    "deepseek-chat",
    api_key=settings.aimodel.api_key,
    api_base=settings.aimodel.base_url,
    temperature=0.1,
    cache=False,
)
dspy.configure(lm=lm)


class OptimalPromptGenerator:
    """最优提示词生成器"""

    def __init__(self, task_description, input_fields, output_fields):
        """
        初始化提示词生成器

        Args:
            task_description: 任务描述
            input_fields: 输入字段列表 [(field_name, description), ...]
            output_fields: 输出字段列表 [(field_name, description), ...]
        """
        self.task_description = task_description
        self.input_fields = input_fields
        self.output_fields = output_fields

        # 动态创建签名类
        self.signature_class = self._create_signature()

        # 创建基础模块
        self.base_module = self._create_module()

    def _create_signature(self):
        """动态创建任务签名"""

        class DynamicSignature(dspy.Signature):
            pass

        # 设置任务描述
        DynamicSignature.__doc__ = self.task_description

        # 添加输入字段
        for field_name, description in self.input_fields:
            setattr(DynamicSignature, field_name, dspy.InputField(desc=description))

        # 添加输出字段
        for field_name, description in self.output_fields:
            setattr(DynamicSignature, field_name, dspy.OutputField(desc=description))

        return DynamicSignature

    def _create_module(self):
        """创建基础模块"""

        class DynamicModule(dspy.Module):
            def __init__(self, signature):
                super().__init__()
                self.predictor = dspy.ChainOfThought(signature)

            def forward(self, **kwargs):
                return self.predictor(**kwargs)

        return DynamicModule(self.signature_class)

    def create_training_data(self, examples):
        """
        创建训练数据

        Args:
            examples: 示例列表，每个示例是一个字典，包含所有输入和输出字段
        """
        training_data = []
        input_field_names = [name for name, _ in self.input_fields]

        for example in examples:
            dspy_example = dspy.Example(**example).with_inputs(*input_field_names)
            training_data.append(dspy_example)

        return training_data

    def optimize_prompt(self, training_examples, validation_examples=None, metric=None):
        """
        优化提示词

        Args:
            training_examples: 训练示例
            validation_examples: 验证示例（可选）
            metric: 评估指标函数（可选）

        Returns:
            优化后的模块
        """
        print("🚀 开始提示词优化...")

        # 创建训练数据
        train_data = self.create_training_data(training_examples)
        val_data = (
            self.create_training_data(validation_examples)
            if validation_examples
            else None
        )

        # 默认评估指标
        if metric is None:
            metric = self._default_metric

        # 使用 BootstrapFewShot 优化
        teleprompter = BootstrapFewShot(
            metric=metric,
            max_bootstrapped_demos=min(4, len(train_data)),
            max_labeled_demos=min(2, len(train_data)),
            max_rounds=2,
        )

        # 编译优化模块
        try:
            # 新版本 DSPy API
            optimized_module = teleprompter.compile(
                self.base_module, trainset=train_data
            )
        except TypeError:
            # 兼容旧版本
            optimized_module = teleprompter.compile(
                self.base_module, trainset=train_data, valset=val_data
            )

        print("✅ 提示词优化完成!")
        return optimized_module

    def _default_metric(self, example, pred, trace=None):
        """默认评估指标"""
        # 检查所有输出字段是否存在且非空
        for field_name, _ in self.output_fields:
            if not hasattr(pred, field_name) or not getattr(pred, field_name):
                return 0.0
        return 1.0

    def extract_optimized_prompt(self, optimized_module):
        """提取优化后的提示词"""
        print("\n📝 提取优化后的提示词:")

        # 获取示例
        if hasattr(optimized_module, "predictor") and hasattr(
            optimized_module.predictor, "demos"
        ):
            demos = optimized_module.predictor.demos
            print(f"\n🎯 优化后包含 {len(demos)} 个示例:")

            for i, demo in enumerate(demos, 1):
                print(f"\n--- 示例 {i} ---")
                for field_name, _ in self.input_fields:
                    if hasattr(demo, field_name):
                        value = getattr(demo, field_name)
                        print(f"{field_name}: {value}")

                for field_name, _ in self.output_fields:
                    if hasattr(demo, field_name):
                        value = getattr(demo, field_name)
                        print(f"{field_name}: {value}")

        # 获取任务描述
        print(f"\n📋 任务描述: {self.task_description}")

        return optimized_module

    def test_optimized_module(self, optimized_module, test_examples):
        """测试优化后的模块"""
        print("\n🧪 测试优化后的模块:")

        for i, example in enumerate(test_examples, 1):
            print(f"\n--- 测试 {i} ---")

            # 准备输入
            inputs = {
                name: example[name] for name, _ in self.input_fields if name in example
            }

            try:
                # 执行预测
                result = optimized_module(**inputs)

                # 显示结果
                print("输入:")
                for name, value in inputs.items():
                    print(f"  {name}: {value}")

                print("输出:")
                for field_name, _ in self.output_fields:
                    if hasattr(result, field_name):
                        value = getattr(result, field_name)
                        print(f"  {field_name}: {value}")

            except Exception as e:
                print(f"❌ 测试失败: {e}")


def demo_text_classification():
    """演示：文本分类任务的提示词优化"""
    print("=== 文本分类提示词优化演示 ===")

    # 1. 定义任务
    generator = OptimalPromptGenerator(
        task_description="分析文本的情感倾向，判断是正面、负面还是中性",
        input_fields=[("text", "需要分析的文本内容")],
        output_fields=[
            ("sentiment", "情感分类：正面/负面/中性"),
            ("confidence", "置信度(1-10)"),
        ],
    )

    # 2. 准备训练数据
    training_examples = [
        {
            "text": "这个产品真的很棒，我非常满意！",
            "sentiment": "正面",
            "confidence": "9",
        },
        {"text": "服务态度很差，完全不推荐。", "sentiment": "负面", "confidence": "8"},
        {"text": "价格还可以，质量一般般。", "sentiment": "中性", "confidence": "7"},
        {"text": "超级喜欢这个设计，太美了！", "sentiment": "正面", "confidence": "10"},
    ]

    # 3. 优化提示词
    optimized_module = generator.optimize_prompt(training_examples)

    # 4. 提取优化后的提示词
    generator.extract_optimized_prompt(optimized_module)

    # 5. 测试优化后的模块
    test_examples = [
        {"text": "这次购物体验很愉快"},
        {"text": "质量有问题，要求退款"},
        {"text": "普通的产品，没什么特别的"},
    ]

    generator.test_optimized_module(optimized_module, test_examples)

    return optimized_module


def demo_qa_system():
    """演示：问答系统的提示词优化"""
    print("\n=== 问答系统提示词优化演示 ===")

    # 1. 定义任务
    generator = OptimalPromptGenerator(
        task_description="根据给定的上下文信息，准确回答用户问题",
        input_fields=[("question", "用户的问题"), ("context", "相关的背景信息")],
        output_fields=[("answer", "准确的答案"), ("source", "答案来源说明")],
    )

    # 2. 准备训练数据
    training_examples = [
        {
            "question": "Python是什么时候发布的？",
            "context": "Python是由Guido van Rossum在1991年首次发布的编程语言。",
            "answer": "Python在1991年首次发布",
            "source": "基于提供的上下文信息",
        },
        {
            "question": "机器学习有哪些主要类型？",
            "context": "机器学习主要分为监督学习、无监督学习和强化学习三大类。",
            "answer": "机器学习主要有三种类型：监督学习、无监督学习和强化学习",
            "source": "基于提供的上下文信息",
        },
    ]

    # 3. 优化提示词
    optimized_module = generator.optimize_prompt(training_examples)

    # 4. 测试
    test_examples = [
        {
            "question": "什么是深度学习？",
            "context": "深度学习是机器学习的一个子领域，使用多层神经网络来学习数据的表示。",
        }
    ]

    generator.test_optimized_module(optimized_module, test_examples)

    return optimized_module


def main():
    """主函数"""
    print("🎯 DSPy 提示词优化实用指南")
    print("=" * 50)

    # 演示1: 文本分类
    demo_text_classification()

    # 演示2: 问答系统
    # demo_qa_system()

    print("\n🎉 提示词优化演示完成!")
    print("\n💡 使用建议:")
    print("1. 准备高质量的训练示例（至少3-5个）")
    print("2. 定义清晰的任务描述和字段说明")
    print("3. 使用合适的评估指标")
    print("4. 多次迭代优化以获得最佳效果")


if __name__ == "__main__":
    main()
