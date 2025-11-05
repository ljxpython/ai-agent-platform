import os

from dotenv import load_dotenv

load_dotenv()
from typing import Annotated, TypedDict

from IPython.display import Image, display
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langchain_core.messages import AnyMessage
from langgraph._internal._constants import CONF, CONFIG_KEY_RUNTIME
from langgraph.constants import END, START
from langgraph.graph import MessagesState, StateGraph, add_messages
from langgraph.prebuilt import ToolNode
from langgraph.runtime import DEFAULT_RUNTIME

model = init_chat_model("deepseek:deepseek-chat", temperature=0)


# Define tools
@tool
def multiply(a: int, b: int) -> int:
    """Multiply `a` and `b`.

    Args:
        a: First int
        b: Second int
    """
    return a * b


@tool
def add(a: int, b: int) -> int:
    """Adds `a` and `b`.

    Args:
        a: First int
        b: Second int
    """
    return a + b


@tool
def divide(a: int, b: int) -> float:
    """Divide `a` and `b`.

    Args:
        a: First int
        b: Second int
    """
    return a / b


# Augment the LLM with tools
tools = [add, multiply, divide]

# 将工具绑定到大模型对象


# 结果：应该调用哪个工具，以及工具参数是什么？


# 执行工具
def call_tool():
    model_with_tools = model.bind_tools(tools)

    result = model_with_tools.invoke("Add 3 and 4.")
    print(result)
    t = ToolNode(tools)
    # ToolNode requires a LangGraph runtime in config when invoked directly
    s = t.invoke([result], config={CONF: {CONFIG_KEY_RUNTIME: DEFAULT_RUNTIME}})
    print(s)


# call_tool()


# -------------------------------------
# 定义传输数据的状态

# class State(TypedDict):
#     messages: Annotated[list[AnyMessage], add_messages]


def call_llm_node(state: MessagesState):
    """Write a story"""
    model_with_tools = model.bind_tools(tools)
    # 将大模型绑定的工具进行及用户问题一起发送给大模型，由大模型觉得调用哪些工具，同时生成工具的参数
    result = model_with_tools.invoke(state["messages"])
    return {"messages": result}


# No separate finalize node; we'll loop back to the same LLM node after tools


def condition_edge(state: MessagesState):
    """If assistant requested tools, go to tools; else END."""
    msgs = state.get("messages", [])
    if not msgs:
        return END
    last = msgs[-1]
    tool_calls = getattr(last, "tool_calls", None) or getattr(
        last, "additional_kwargs", {}
    ).get("tool_calls")
    return "tool_node" if tool_calls else END


tool_node = ToolNode(tools)

# Build workflow
agent_builder = StateGraph(MessagesState)

# 添加节点
agent_builder.add_node("llm_call", call_llm_node)
agent_builder.add_node("tool_node", tool_node)
# No separate finalize node
# Note: `condition_edge` is a condition function, not a node.
# Do NOT register it as a node.


# Add edges to connect nodes
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges("llm_call", condition_edge)
# After tools execute, loop back to the LLM node for follow-up/final answer
agent_builder.add_edge("tool_node", "llm_call")
#
# Compile the agent
graph = agent_builder.compile()

# 显示并保存工作流图
graph_image = graph.get_graph().draw_mermaid_png()
display(Image(graph_image))

# 保存工作流图片
with open("tool_call_workflow.png", "wb") as f:
    f.write(graph_image)
print("工作流图片已保存为 'tool_call_workflow.png'")


# Invoke (only when running this file directly)
if __name__ == "__main__":
    from langchain.messages import HumanMessage

    messages = [HumanMessage(content="Add 3 and 4.")]
    messages = graph.invoke({"messages": messages})
    for m in messages["messages"]:
        m.pretty_print()
