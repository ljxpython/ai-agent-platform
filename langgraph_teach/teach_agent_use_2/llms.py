import os

from dotenv import load_dotenv

load_dotenv()
# from langchain.chat_models import init_chat_model
from langchain_deepseek.chat_models import ChatDeepSeek


def get_default_model():
    return ChatDeepSeek(model="deepseek-chat")


# llm = get_default_model()
# response = llm.invoke("你好")
# print(response)
# for text in llm.stream("你好"):
#     print(text.content, end="", flush=True)
