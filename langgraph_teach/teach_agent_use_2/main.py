from langchain.agents import create_agent
from langgraph.prebuilt import create_react_agent
from llms import get_default_model
from tools import (
    get_chrome_devtools_mcp_tools,
    get_chrome_mcp_tools,
    get_mcp_server_chart_tools,
    get_playwright_mcp_tools,
    get_tavily_search_tools,
    get_weather,
    get_zhipu_search_mcp_tools,
    save_test_cases_to_excel,
    toolSearch,
)

# from 父 import 儿子
model = get_default_model()

agent = create_agent(
    model=model, tools=[get_weather], system_prompt="You are a helpful assistant"
)


web_agent = create_agent(
    model=model,
    tools=get_mcp_server_chart_tools()
    + get_chrome_mcp_tools()
    + [save_test_cases_to_excel],
    system_prompt="You are a helpful assistant",
)
