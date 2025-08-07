"""
DSPy 系统提示词优化完整指南

展示如何使用 DSPy 的各种优化器来获得最优的系统提示词
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json

import dspy
from conf.config import settings
from dspy.teleprompt import (
    MIPRO,
    BootstrapFewShot,
    BootstrapFewShotWithRandomSearch,
    LabeledFewShot,
)

# 配置语言模型
lm = dspy.LM(
    "deepseek-chat",
    api_key=settings.aimodel.api_key,
    api_base=settings.aimodel.base_url,
    temperature=0.1,
    cache=False,
)
dspy.configure(lm=lm)


# 定义任务签名
class TaskSignature(dspy.Signature):
    """根据用户输入生成高质量的回答"""

    user_input = dspy.InputField(desc="用户的问题或请求")
    context = dspy.InputField(desc="相关背景信息")
    response = dspy.OutputField(desc="高质量的回答")
    confidence = dspy.OutputField(desc="回答的置信度(1-10)")


# 定义基础模块
class ResponseGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate = dspy.ChainOfThought(TaskSignature)

    def forward(self, user_input, context=""):
        result = self.generate(user_input=user_input, context=context)
        return result


class PromptOptimizer:
    def __init__(self):
        self.base_module = ResponseGenerator()
        self.train_data = self._create_training_data()
        self.dev_data = self._create_dev_data()

    def _create_training_data(self):
        """创建训练数据集"""
        return [
            dspy.Example(
                user_input="如何提高工作效率？",
                context="办公环境，时间管理",
                response="提高工作效率的关键方法包括：1) 制定明确的优先级列表；2) 使用番茄工作法进行时间管理；3) 减少干扰因素；4) 定期休息保持专注力；5) 使用合适的工具和技术。",
                confidence="8",
            ).with_inputs("user_input", "context"),
            dspy.Example(
                user_input="Python中如何处理异常？",
                context="编程，错误处理",
                response="Python异常处理使用try-except语句：1) try块包含可能出错的代码；2) except块处理特定异常；3) finally块执行清理代码；4) 可以使用多个except处理不同异常；5) raise语句可以主动抛出异常。",
                confidence="9",
            ).with_inputs("user_input", "context"),
            dspy.Example(
                user_input="如何学习新技能？",
                context="个人发展，学习方法",
                response="学习新技能的有效方法：1) 设定明确的学习目标；2) 制定循序渐进的学习计划；3) 理论与实践相结合；4) 寻找导师或学习伙伴；5) 定期复习和总结；6) 保持持续的练习。",
                confidence="8",
            ).with_inputs("user_input", "context"),
            dspy.Example(
                user_input="什么是机器学习？",
                context="人工智能，技术概念",
                response="机器学习是人工智能的一个分支，让计算机通过数据学习模式而无需明确编程。主要类型包括：1) 监督学习（有标签数据）；2) 无监督学习（无标签数据）；3) 强化学习（通过奖励学习）。应用广泛，如图像识别、自然语言处理等。",
                confidence="9",
            ).with_inputs("user_input", "context"),
        ]

    def _create_dev_data(self):
        """创建验证数据集"""
        return [
            dspy.Example(
                user_input="如何保持健康的生活方式？",
                context="健康，生活习惯",
                response="保持健康生活方式的要点：1) 规律作息，充足睡眠；2) 均衡饮食，多吃蔬果；3) 定期运动，保持活力；4) 管理压力，保持心理健康；5) 定期体检，预防疾病；6) 避免不良习惯如吸烟酗酒。",
                confidence="8",
            ).with_inputs("user_input", "context"),
            dspy.Example(
                user_input="数据库设计的基本原则是什么？",
                context="数据库，系统设计",
                response="数据库设计的基本原则：1) 规范化，减少数据冗余；2) 完整性约束，确保数据准确性；3) 性能优化，合理设计索引；4) 安全性，控制访问权限；5) 可扩展性，考虑未来增长；6) 备份恢复，确保数据安全。",
                confidence="9",
            ).with_inputs("user_input", "context"),
        ]

    def quality_metric(self, example, pred, trace=None):
        """定义质量评估指标"""
        # 检查回答是否包含关键信息
        if not pred.response or len(pred.response.strip()) < 20:
            return 0.0

        # 检查置信度是否合理
        try:
            confidence = int(pred.confidence)
            if confidence < 1 or confidence > 10:
                return 0.5
        except:
            return 0.5

        # 简单的内容质量评估
        response_lower = pred.response.lower()
        if any(
            keyword in response_lower for keyword in ["方法", "步骤", "包括", "要点"]
        ):
            return 1.0

        return 0.7

    def optimize_with_bootstrap_fewshot(self):
        """使用 BootstrapFewShot 优化"""
        print("\n=== 使用 BootstrapFewShot 优化 ===")

        teleprompter = BootstrapFewShot(
            metric=self.quality_metric,
            max_bootstrapped_demos=4,
            max_labeled_demos=2,
            max_rounds=3,
        )

        optimized_module = teleprompter.compile(
            self.base_module, trainset=self.train_data, valset=self.dev_data
        )

        return optimized_module

    def optimize_with_random_search(self):
        """使用 BootstrapFewShotWithRandomSearch 优化"""
        print("\n=== 使用 BootstrapFewShotWithRandomSearch 优化 ===")

        teleprompter = BootstrapFewShotWithRandomSearch(
            metric=self.quality_metric,
            max_bootstrapped_demos=4,
            max_labeled_demos=2,
            num_candidate_programs=5,
            num_threads=2,
        )

        optimized_module = teleprompter.compile(
            self.base_module, trainset=self.train_data, valset=self.dev_data
        )

        return optimized_module

    def optimize_with_mipro(self):
        """使用 MIPRO 优化（最先进的优化器）"""
        print("\n=== 使用 MIPRO 优化 ===")

        try:
            teleprompter = MIPRO(
                metric=self.quality_metric, num_candidates=5, init_temperature=1.0
            )

            optimized_module = teleprompter.compile(
                self.base_module, trainset=self.train_data, valset=self.dev_data
            )

            return optimized_module
        except Exception as e:
            print(f"MIPRO 优化失败: {e}")
            return None

    def optimize_with_labeled_fewshot(self):
        """使用 LabeledFewShot 优化"""
        print("\n=== 使用 LabeledFewShot 优化 ===")

        teleprompter = LabeledFewShot(k=3)

        optimized_module = teleprompter.compile(
            self.base_module, trainset=self.train_data
        )

        return optimized_module

    def evaluate_module(self, module, test_data, name="模块"):
        """评估模块性能"""
        print(f"\n=== 评估 {name} ===")

        total_score = 0
        for i, example in enumerate(test_data):
            try:
                pred = module(user_input=example.user_input, context=example.context)
                score = self.quality_metric(example, pred)
                total_score += score

                print(f"测试 {i+1}: 得分 {score:.2f}")
                print(f"  问题: {example.user_input}")
                print(f"  回答: {pred.response[:100]}...")
                print(f"  置信度: {pred.confidence}")

            except Exception as e:
                print(f"测试 {i+1} 失败: {e}")

        avg_score = total_score / len(test_data) if test_data else 0
        print(f"{name} 平均得分: {avg_score:.2f}")
        return avg_score

    def extract_optimized_prompts(self, module):
        """提取优化后的提示词"""
        print("\n=== 提取优化后的提示词 ===")

        # 获取模块的历史记录
        if hasattr(module, "generate") and hasattr(module.generate, "demos"):
            demos = module.generate.demos
            print(f"发现 {len(demos)} 个示例:")
            for i, demo in enumerate(demos):
                print(f"\n示例 {i+1}:")
                print(f"  输入: {demo.user_input}")
                print(f"  输出: {demo.response[:100]}...")

        # 尝试获取系统提示词
        if hasattr(module, "generate") and hasattr(module.generate, "signature"):
            signature = module.generate.signature
            print(f"\n任务描述: {signature.__doc__}")

        return module

    def run_comprehensive_optimization(self):
        """运行全面的提示词优化"""
        print("=== DSPy 系统提示词优化指南 ===")

        results = {}

        # 1. 基础模块评估
        base_score = self.evaluate_module(self.base_module, self.dev_data, "基础模块")
        results["基础模块"] = base_score

        # 2. BootstrapFewShot 优化
        try:
            bs_module = self.optimize_with_bootstrap_fewshot()
            bs_score = self.evaluate_module(
                bs_module, self.dev_data, "BootstrapFewShot"
            )
            results["BootstrapFewShot"] = bs_score
            self.extract_optimized_prompts(bs_module)
        except Exception as e:
            print(f"BootstrapFewShot 优化失败: {e}")
            results["BootstrapFewShot"] = 0

        # 3. RandomSearch 优化
        try:
            rs_module = self.optimize_with_random_search()
            rs_score = self.evaluate_module(rs_module, self.dev_data, "RandomSearch")
            results["RandomSearch"] = rs_score
        except Exception as e:
            print(f"RandomSearch 优化失败: {e}")
            results["RandomSearch"] = 0

        # 4. LabeledFewShot 优化
        try:
            lf_module = self.optimize_with_labeled_fewshot()
            lf_score = self.evaluate_module(lf_module, self.dev_data, "LabeledFewShot")
            results["LabeledFewShot"] = lf_score
        except Exception as e:
            print(f"LabeledFewShot 优化失败: {e}")
            results["LabeledFewShot"] = 0

        # 5. MIPRO 优化（如果可用）
        mipro_module = self.optimize_with_mipro()
        if mipro_module:
            mipro_score = self.evaluate_module(mipro_module, self.dev_data, "MIPRO")
            results["MIPRO"] = mipro_score

        # 总结结果
        print("\n=== 优化结果总结 ===")
        for method, score in results.items():
            print(f"{method}: {score:.2f}")

        best_method = max(results.items(), key=lambda x: x[1])
        print(f"\n🏆 最佳优化方法: {best_method[0]} (得分: {best_method[1]:.2f})")

        return results


def main():
    """主函数"""
    optimizer = PromptOptimizer()
    results = optimizer.run_comprehensive_optimization()

    # 保存结果
    output_file = "examples/dspy_demo/optimization_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {output_file}")


if __name__ == "__main__":
    main()
