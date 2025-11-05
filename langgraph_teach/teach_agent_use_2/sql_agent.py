import asyncio
import os

from dotenv import load_dotenv

load_dotenv()
# pip install langchain_community


from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_mcp_adapters.client import MultiServerMCPClient
from llms import get_default_model

llm = get_default_model()

# 封装了对数据库的常见操作（作业：换成mysql数据库）
db = SQLDatabase.from_uri("sqlite:///Chinook.db")

# print(db.get_usable_table_names())
# # print(f"Dialect: {db.dialect}")
# # print(f"Available tables: {db.get_usable_table_names()}")
# print(f'Sample output: {db.run("SELECT * FROM Artist LIMIT 5;")}')

toolkit = SQLDatabaseToolkit(db=db, llm=llm)

# 获取所有的工具
tools = toolkit.get_tools()

for tool in tools:
    print(f"{tool.name}: {tool.description}\n")


llm = init_chat_model("deepseek:deepseek-chat")

system_prompt = """
你是一个专为与SQL数据库交互而设计的智能体。
根据输入的问题，你需要生成语法正确的{dialect}查询语句，
执行查询后分析结果并返回答案。除非用户明确指定要获取的记录数量，
否则始终将查询结果限制在最多{top_k}条。

你可以通过相关列对结果进行排序，以返回数据库中最有价值的信息。
切勿查询特定表的所有列，只需获取与问题相关的列即可。

在执行查询前必须仔细检查语句。若执行过程中出现错误，
应重新编写查询语句并再次尝试。

严禁对数据库执行任何数据操作语言语句（INSERT、UPDATE、DELETE、DROP等）。

开始操作时，你必须始终先查看数据库中的表结构以确定可查询的内容，
切勿跳过这一步骤。

随后应当查询最相关表的模式结构。

根据查询的数据特点选择合适的图表生成工具显示
""".format(
    dialect=db.dialect,
    top_k=10,
)

mcp_client = MultiServerMCPClient(
    {
        "mcp-server-chart": {
            "command": "npx",
            # Make sure to update to the full absolute path to your math_server.py file
            "args": ["-y", "@antv/mcp-server-chart"],
            "transport": "stdio",
        }
    }
)


mcp_tools = asyncio.run(mcp_client.get_tools())
agent = create_agent(
    llm,
    tools + mcp_tools,
    system_prompt=system_prompt,
)
question = "哪种音乐类型的曲目平均时长最长？"


async def main():
    async for step in agent.astream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="values",
    ):
        step["messages"][-1].pretty_print()


if __name__ == "__main__":
    asyncio.run(main())
