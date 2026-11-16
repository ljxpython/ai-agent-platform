"""All explicitly installed business writes require native approve/reject interrupts."""

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware


def create_platform_agent(
    model, tools, *, business_write_tools=(), middleware=(), **kwargs
):
    """Business tools are supplied by trusted backend code, never by user config."""
    return create_agent(
        model=model,
        tools=[*tools, *business_write_tools],
        middleware=[*middleware, write_approval(business_write_tools)],
        **kwargs,
    )


def write_approval(tools):
    return HumanInTheLoopMiddleware(
        interrupt_on={
            tool.name: {
                "allowed_decisions": ["approve", "reject"],
                "description": "此操作将修改业务数据。请核对工具、目标和参数，再选择执行或不执行。",
            }
            for tool in tools
        }
    )
