"""
DSPy 医疗陷阱检测器 - 修正版本

这个示例展示了如何使用 DSPy 正确的 API 来构建和优化医疗陷阱检测系统。
"""

import os
import sys

import dspy
from dspy.teleprompt import BootstrapFewShot

from examples.conf.config import settings

print(f"模型: {settings.aimodel.model}")
print(f"API 基础URL: {settings.aimodel.base_url}")

# 配置语言模型
lm = dspy.LM(
    "deepseek-chat",
    api_key=settings.aimodel.api_key,
    api_base=settings.aimodel.base_url,
    temperature=0.1,
    cache=False,
)
dspy.configure(lm=lm)


# 定义输入输出签名
class TrapDetectionSignature(dspy.Signature):
    """分析医疗症状描述和病历文本，判断是否存在隐藏的医疗陷阱"""

    symptom_desc = dspy.InputField(desc="患者症状描述")
    medical_record = dspy.InputField(desc="病历文本内容")
    conclusion = dspy.OutputField(desc="判断结论：是/否")
    reasoning = dspy.OutputField(desc="判断理由")


# 定义医疗陷阱检测器模块
class TrapDetector(dspy.Module):
    def __init__(self):
        super().__init__()
        # 使用 ChainOfThought 进行推理
        self.detect = dspy.ChainOfThought(TrapDetectionSignature)

    def forward(self, symptom_desc, medical_record):
        result = self.detect(symptom_desc=symptom_desc, medical_record=medical_record)
        return result


# 准备训练数据
train_data = [
    dspy.Example(
        symptom_desc="咳嗽一周，无发热",
        medical_record="患者否认过敏史，胸片正常",
        conclusion="否",
        reasoning="症状描述与病历记录一致，无明显矛盾",
    ).with_inputs("symptom_desc", "medical_record"),
    dspy.Example(
        symptom_desc="皮疹伴瘙痒，自行用药后加重",
        medical_record="患者未提及近期更换护肤品",
        conclusion="是",
        reasoning="患者可能隐瞒了更换护肤品的信息，这可能是皮疹加重的原因",
    ).with_inputs("symptom_desc", "medical_record"),
    dspy.Example(
        symptom_desc="头痛三天，自行服用止痛药无效",
        medical_record="患者未提及高血压病史（但病历显示血压160/100mmHg）",
        conclusion="是",
        reasoning="病历显示高血压但患者未主动提及，存在隐瞒病史的可能",
    ).with_inputs("symptom_desc", "medical_record"),
    dspy.Example(
        symptom_desc="腹痛两天，伴恶心",
        medical_record="患者否认饮食不洁，体检腹部轻压痛",
        conclusion="否",
        reasoning="症状与体检结果相符，患者陈述可信",
    ).with_inputs("symptom_desc", "medical_record"),
]


# 定义评估指标
def trap_detection_metric(example, pred, trace=None):
    """评估预测结果的准确性"""
    return example.conclusion.lower() == pred.conclusion.lower()


# 创建检测器实例
detector = TrapDetector()

print("\n=== 基础检测测试 ===")
# 测试基础功能
test_case = {
    "symptom_desc": "头痛三天，自行服用止痛药无效",
    "medical_record": "患者未提及高血压病史（但病历显示血压160/100mmHg）",
}

result = detector(
    symptom_desc=test_case["symptom_desc"], medical_record=test_case["medical_record"]
)
print(f"症状描述: {test_case['symptom_desc']}")
print(f"病历记录: {test_case['medical_record']}")
print(f"检测结论: {result.conclusion}")
print(f"推理过程: {result.reasoning}")

print("\n=== 开始优化训练 ===")
# 使用 BootstrapFewShot 进行优化
teleprompter = BootstrapFewShot(
    metric=trap_detection_metric, max_bootstrapped_demos=4, max_labeled_demos=4
)

# 编译优化后的程序
try:
    optimized_detector = teleprompter.compile(detector, trainset=train_data)
    print("✅ 优化训练完成")

    print("\n=== 优化后检测测试 ===")
    # 测试优化后的效果
    optimized_result = optimized_detector(
        symptom_desc=test_case["symptom_desc"],
        medical_record=test_case["medical_record"],
    )
    print(f"优化后结论: {optimized_result.conclusion}")
    print(f"优化后推理: {optimized_result.reasoning}")

    print("\n=== 批量测试 ===")
    # 批量测试所有训练样例
    correct_predictions = 0
    total_predictions = len(train_data)

    for i, example in enumerate(train_data):
        pred = optimized_detector(
            symptom_desc=example.symptom_desc, medical_record=example.medical_record
        )
        is_correct = trap_detection_metric(example, pred)
        correct_predictions += is_correct

        print(
            f"测试 {i+1}: {'✅' if is_correct else '❌'} "
            f"预测: {pred.conclusion}, 实际: {example.conclusion}"
        )

    accuracy = correct_predictions / total_predictions
    print(f"\n准确率: {accuracy:.2%} ({correct_predictions}/{total_predictions})")

except Exception as e:
    print(f"❌ 优化过程出错: {e}")
    print("使用基础检测器继续测试...")

    # 如果优化失败，使用基础检测器
    print("\n=== 基础检测器批量测试 ===")
    correct_predictions = 0
    total_predictions = len(train_data)

    for i, example in enumerate(train_data):
        pred = detector(
            symptom_desc=example.symptom_desc, medical_record=example.medical_record
        )
        is_correct = trap_detection_metric(example, pred)
        correct_predictions += is_correct

        print(
            f"测试 {i+1}: {'✅' if is_correct else '❌'} "
            f"预测: {pred.conclusion}, 实际: {example.conclusion}"
        )

    accuracy = correct_predictions / total_predictions
    print(f"\n基础准确率: {accuracy:.2%} ({correct_predictions}/{total_predictions})")

print("\n=== 程序执行完成 ===")
