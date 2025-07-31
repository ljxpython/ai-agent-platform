"""


Autogen memory + mem0 使用范例,未来使用范例,应该直接参考backend/ai_core/memory.py的代码

"""

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType
from autogen_ext.memory.mem0 import Mem0Memory

from examples.conf.config import settings
from examples.llms import openai_model_client

# For local deployment, use is_cloud=False with appropriate config
# 这个没有配置会报错Mem0 API Key not provided. Please provide an API Key.
# 后面参考https://docs.mem0.ai/examples/mem0-with-ollama 来调试使用
mem0_memory = Mem0Memory(api_key=settings.mem0_api_key, is_cloud=True)


async def main():
    # Initialize user memory
    # user_memory = ListMemory()

    # Add user preferences to memory
    await mem0_memory.add(
        MemoryContent(
            content="The weather should be in metric units",
            mime_type=MemoryMimeType.TEXT,
        )
    )

    await mem0_memory.add(
        MemoryContent(
            content="Meal recipe must be vegan", mime_type=MemoryMimeType.TEXT
        )
    )

    async def get_weather(city: str, units: str = "imperial") -> str:
        if units == "imperial":
            return f"The weather in {city} is 73 °F and Sunny."
        elif units == "metric":
            return f"The weather in {city} is 23 °C and Sunny."
        else:
            return f"Sorry, I don't know the weather in {city}."

    assistant_agent = AssistantAgent(
        name="assistant_agent",
        model_client=openai_model_client,
        tools=[get_weather],
        memory=[mem0_memory],
    )
    stream = assistant_agent.run_stream(task="What is the weather in New York?")
    await Console(stream)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
