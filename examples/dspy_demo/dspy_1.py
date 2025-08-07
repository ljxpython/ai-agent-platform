import dspy

from examples.conf.config import settings

# Configure DSPy with tracking enabled
dspy.settings.configure(
    lm=dspy.LM(
        "deepseek-chat",
        api_key=settings.aimodel.api_key,
        api_base=settings.aimodel.base_url,
        temperature=0.1,
        cache=False,
    ),
    track_usage=True,
)


# Define a simple program that makes multiple LM calls
class MyProgram(dspy.Module):
    def __init__(self):
        self.predict1 = dspy.ChainOfThought("question -> answer")
        self.predict2 = dspy.ChainOfThought("question, answer -> score")

    def __call__(self, question: str) -> str:
        answer = self.predict1(question=question)
        score = self.predict2(question=question, answer=answer)
        return score


# Run the program and check usage
program = MyProgram()
output = program(question="What is the capital of France?")
print(output)
print(output.get_lm_usage())
