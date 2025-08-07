import dspy
from dspy.teleprompt import BootstrapFewShotWithRandomSearch

from examples.conf.config import settings

print(settings.aimodel.model)
print(settings.aimodel.base_url)

lm = dspy.LM(
    "deepseek-chat",
    api_key=settings.aimodel.api_key,
    api_base=settings.aimodel.base_url,
    temperature=0.1,
    cache=False,
)
dspy.configure(lm=lm)
# print('test')
# lm("Say this is a test!", temperature=0.7)  # => ['This is a test!']
# lm(messages=[{"role": "user", "content": "Say this is a test!"}])  # => ['This is a test!']
#
#
# # Define a module (ChainOfThought) and assign it a signature (return an answer, given a question).
# qa = dspy.ChainOfThought('question -> answer')
#
# # Run with the default LM configured with `dspy.configure` above.
# response = qa(question="How many floors are in the castle David Gregory inherited?")
# print(response.answer)
#

# sentence = "it's a charming and often affecting journey."  # example from the SST-2 dataset.
#
# # 1) Declare with a signature.
# classify = dspy.Predict('sentence -> sentiment: bool')
#
# # 2) Call with input argument(s).
# response = classify(sentence=sentence)
#
# # 3) Access the output.
# print(response.sentiment)


# Set up the optimizer: we want to "bootstrap" (i.e., self-generate) 8-shot examples of your program's steps.
# The optimizer will repeat this 10 times (plus some initial attempts) before selecting its best attempt on the devset.
# config = dict(max_bootstrapped_demos=4, max_labeled_demos=4, num_candidate_programs=10, num_threads=4)
#
# teleprompter = BootstrapFewShotWithRandomSearch(metric=YOUR_METRIC_HERE, **config)
# optimized_program = teleprompter.compile(YOUR_PROGRAM_HERE, trainset=YOUR_TRAINSET_HERE)
#

initial_prompt = """
请仔细阅读以下症状描述和病历文本，判断是否存在隐藏的医疗陷阱（如隐瞒过敏史、症状描述矛盾等）。
症状描述：{symptom_desc}
病历文本：{medical_record}
结论：是/否
"""


# 定义优化目标（最大化F1分数）
class TrapDetector(dspy.Module):
    def __init__(self):
        super().__init__()
        self.prompt = dspy.Prompt(initial_prompt)

    def forward(self, symptom_desc, medical_record):
        return dspy.Predict(self.prompt)(
            symptom_desc=symptom_desc, medical_record=medical_record
        )


# 用合成数据训练（这里用模拟数据举例）
train_data = [
    {
        "symptom_desc": "咳嗽一周，无发热",
        "medical_record": "患者否认过敏史，胸片正常",
        "label": "否",
    },
    {
        "symptom_desc": "皮疹伴瘙痒，自行用药后加重",
        "medical_record": "患者未提及近期更换护肤品",
        "label": "是",
    },
]

# 启动优化（自动搜索最优提示词）
optimized_detector = dspy.optimize(TrapDetector(), train_data, num_samples=10)

# 测试优化后的效果
test_case = {
    "symptom_desc": "头痛三天，自行服用止痛药无效",
    "medical_record": "患者未提及高血压病史（但病历显示血压160/100mmHg）",
}
result = optimized_detector(
    symptom_desc=test_case["symptom_desc"], medical_record=test_case["medical_record"]
)
print(f"结论：{result.conclusion}")  # 输出：是（正确识别矛盾）
