"""LangGraph entrypoint for the Showcase Demo."""

from runtime_service.runtime.scheduled import scheduled_execution
from runtime_service.services.demo.showcase_demo.agent import get_agent

get_agent = scheduled_execution(get_agent, agent_key="showcase_demo")

__all__ = ["get_agent"]
