"""
医疗陷阱检测器 - 不依赖 DSPy 的替代方案

使用原生的 LLM API 调用实现医疗陷阱检测功能
"""

import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conf.config import settings
from openai import OpenAI

# 配置 OpenAI 客户端（兼容 DeepSeek API）
client = OpenAI(api_key=settings.aimodel.api_key, base_url=settings.aimodel.base_url)


class MedicalTrapDetector:
    def __init__(self):
        self.system_prompt = """你是一个专业的医疗陷阱检测专家。你的任务是分析患者的症状描述和病历文本，判断是否存在隐藏的医疗陷阱。

医疗陷阱包括但不限于：
1. 隐瞒过敏史
2. 症状描述矛盾
3. 隐瞒既往病史
4. 药物使用不当
5. 症状与检查结果不符

请仔细分析并给出判断。"""

        self.examples = [
            {
                "symptom_desc": "咳嗽一周，无发热",
                "medical_record": "患者否认过敏史，胸片正常",
                "conclusion": "否",
                "reasoning": "症状描述与病历记录一致，无明显矛盾",
            },
            {
                "symptom_desc": "皮疹伴瘙痒，自行用药后加重",
                "medical_record": "患者未提及近期更换护肤品",
                "conclusion": "是",
                "reasoning": "患者可能隐瞒了更换护肤品的信息，这可能是皮疹加重的原因",
            },
            {
                "symptom_desc": "头痛三天，自行服用止痛药无效",
                "medical_record": "患者未提及高血压病史（但病历显示血压160/100mmHg）",
                "conclusion": "是",
                "reasoning": "病历显示高血压但患者未主动提及，存在隐瞒病史的可能",
            },
        ]

    def create_prompt(self, symptom_desc, medical_record, include_examples=True):
        """创建检测提示词"""
        prompt = f"{self.system_prompt}\n\n"

        if include_examples:
            prompt += "以下是一些示例：\n\n"
            for i, example in enumerate(self.examples, 1):
                prompt += f"示例 {i}:\n"
                prompt += f"症状描述：{example['symptom_desc']}\n"
                prompt += f"病历文本：{example['medical_record']}\n"
                prompt += f"结论：{example['conclusion']}\n"
                prompt += f"理由：{example['reasoning']}\n\n"

        prompt += "现在请分析以下案例：\n"
        prompt += f"症状描述：{symptom_desc}\n"
        prompt += f"病历文本：{medical_record}\n\n"
        prompt += "请按以下格式回答：\n"
        prompt += "结论：是/否\n"
        prompt += "理由：[详细分析理由]\n"

        return prompt

    def detect(self, symptom_desc, medical_record, include_examples=True):
        """检测医疗陷阱"""
        prompt = self.create_prompt(symptom_desc, medical_record, include_examples)

        try:
            response = client.chat.completions.create(
                model=settings.aimodel.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
            )

            result_text = response.choices[0].message.content
            return self.parse_result(result_text)

        except Exception as e:
            return {
                "conclusion": "错误",
                "reasoning": f"API 调用失败: {str(e)}",
                "raw_response": "",
            }

    def parse_result(self, result_text):
        """解析 LLM 返回结果"""
        lines = result_text.strip().split("\n")
        conclusion = "未知"
        reasoning = "无法解析结果"

        for line in lines:
            if line.startswith("结论：") or line.startswith("结论:"):
                conclusion = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            elif line.startswith("理由：") or line.startswith("理由:"):
                reasoning = line.split("：", 1)[-1].split(":", 1)[-1].strip()

        return {
            "conclusion": conclusion,
            "reasoning": reasoning,
            "raw_response": result_text,
        }

    def batch_evaluate(self, test_cases):
        """批量评估测试案例"""
        results = []
        correct_count = 0

        for i, case in enumerate(test_cases):
            print(f"\n=== 测试案例 {i+1} ===")
            print(f"症状描述: {case['symptom_desc']}")
            print(f"病历记录: {case['medical_record']}")
            print(f"期望结论: {case['expected']}")

            result = self.detect(case["symptom_desc"], case["medical_record"])

            print(f"检测结论: {result['conclusion']}")
            print(f"推理过程: {result['reasoning']}")

            is_correct = result["conclusion"].lower() == case["expected"].lower()
            if is_correct:
                correct_count += 1
                print("✅ 正确")
            else:
                print("❌ 错误")

            results.append({**case, **result, "is_correct": is_correct})

        accuracy = correct_count / len(test_cases) if test_cases else 0
        print(f"\n总体准确率: {accuracy:.2%} ({correct_count}/{len(test_cases)})")

        return results, accuracy


def main():
    """主函数"""
    print("=== 医疗陷阱检测器 - 替代方案 ===")
    print(f"使用模型: {settings.aimodel.model}")
    print(f"API 地址: {settings.aimodel.base_url}")

    # 创建检测器
    detector = MedicalTrapDetector()

    # 单个测试案例
    print("\n=== 单个案例测试 ===")
    test_case = {
        "symptom_desc": "头痛三天，自行服用止痛药无效",
        "medical_record": "患者未提及高血压病史（但病历显示血压160/100mmHg）",
    }

    result = detector.detect(test_case["symptom_desc"], test_case["medical_record"])
    print(f"症状描述: {test_case['symptom_desc']}")
    print(f"病历记录: {test_case['medical_record']}")
    print(f"检测结论: {result['conclusion']}")
    print(f"推理过程: {result['reasoning']}")

    # 批量测试
    print("\n=== 批量测试 ===")
    test_cases = [
        {
            "symptom_desc": "咳嗽一周，无发热",
            "medical_record": "患者否认过敏史，胸片正常",
            "expected": "否",
        },
        {
            "symptom_desc": "皮疹伴瘙痒，自行用药后加重",
            "medical_record": "患者未提及近期更换护肤品",
            "expected": "是",
        },
        {
            "symptom_desc": "头痛三天，自行服用止痛药无效",
            "medical_record": "患者未提及高血压病史（但病历显示血压160/100mmHg）",
            "expected": "是",
        },
        {
            "symptom_desc": "腹痛两天，伴恶心",
            "medical_record": "患者否认饮食不洁，体检腹部轻压痛",
            "expected": "否",
        },
    ]

    results, accuracy = detector.batch_evaluate(test_cases)

    # 保存结果
    output_file = "examples/dspy_demo/detection_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {"accuracy": accuracy, "results": results}, f, ensure_ascii=False, indent=2
        )

    print(f"\n结果已保存到: {output_file}")


if __name__ == "__main__":
    main()
