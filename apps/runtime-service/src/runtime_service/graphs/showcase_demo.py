"""LangGraph entrypoint for the Showcase Demo."""

from runtime_service.runtime.background_completion import (
    background_completion_execution,
)
from runtime_service.runtime.scheduled import scheduled_execution
from runtime_service.services.demo.showcase_demo.agent import get_agent

get_agent = scheduled_execution(get_agent, agent_key="showcase_demo")
get_agent = background_completion_execution(get_agent, agent_key="showcase_demo")

__all__ = ["get_agent"]
