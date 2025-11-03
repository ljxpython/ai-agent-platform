import asyncio

from langchain.agents import create_agent
from llms import get_default_model
from tools import (
    get_chrome_devtools_mcp_tools,
    get_chrome_mcp_tools,
    get_mcp_server_chart_tools,
    get_playwright_mcp_tools,
    get_tavily_search_tools,
    get_weather,
    get_zhipu_search_mcp_tools,
    toolSearch,
)
from ui_test_tools import (
    generate_html_report,
    get_output_directory,
    save_test_cases_to_excel,
    set_output_directory,
)

# from 父 import 儿子
model = get_default_model()

agent = create_agent(
    model=model, tools=[get_weather], system_prompt="You are a helpful assistant"
)


web_agent = create_agent(
    model=model,
    tools=get_mcp_server_chart_tools() + get_chrome_mcp_tools(),
    system_prompt="You are a helpful assistant",
)


# UI自动化测试Agent
ui_test_agent = create_agent(
    model=model,
    tools=get_chrome_mcp_tools()
    + [
        save_test_cases_to_excel,
        generate_html_report,
        set_output_directory,
        get_output_directory,
    ],
    system_prompt="""你是一个专业的UI自动化测试专家。你的职责是：

1. **测试用例设计**：根据用户需求，设计清晰、完整的测试用例
   - 每个测试用例应包含：用例ID、标题、测试步骤、预期结果
   - 测试步骤要详细、可执行
   - 覆盖正常流程和异常场景

2. **自动化测试执行**：使用Chrome MCP工具执行测试
   - 使用chrome_navigate_chrome_mcp打开网页
   - 使用chrome_get_web_content_chrome_mcp获取页面内容
   - 使用chrome_click_element_chrome_mcp点击元素
   - 使用chrome_fill_or_select_chrome_mcp填写表单
   - 使用chrome_screenshot_chrome_mcp截取关键步骤的截图
   - 使用chrome_get_interactive_elements_chrome_mcp获取可交互元素

3. **测试结果记录**：
   - 记录每个测试用例的执行结果（Pass/Fail）
   - 记录实际结果与预期结果的对比
   - 保存关键步骤的截图（base64格式）

4. **报告生成**：
   - 使用save_test_cases_to_excel将测试用例保存到Excel
   - 使用generate_html_report生成图文并茂的HTML测试报告
   - 报告应包含：测试摘要、详细用例、截图、统计数据

5. **工作流程**：
   a. 理解用户需求，设计测试用例
   b. 打开目标网站
   c. 逐个执行测试用例，记录结果和截图
   d. 汇总测试结果
   e. 生成Excel和HTML报告
   f. 向用户报告测试完成情况和报告路径

注意事项：
- 每个测试步骤都要截图记录
- 遇到错误要详细记录错误信息
- 测试报告要清晰、专业、易读
- 所有文件保存到ui_test_reports目录
""",
)


if __name__ == "__main__":

    async def main():
        # resp = agent.invoke({"input": "今天北京的温度是多少"})
        # # 直接打印返回结果
        # print(resp)
        for i in agent.stream({"input": "今天北京的温度是多少"}):
            print(i)

    asyncio.run(main())

    # resp = agent.invoke("请打开百度，搜索'你好'，并点击搜索按钮")
    # for i in resp:
    #     print(i)
