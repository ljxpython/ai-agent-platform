"""LangGraph entrypoint for the reference agent."""

from runtime_service.runtime.scheduled import scheduled_execution
from runtime_service.services.reference_agent.agent import get_agent

get_agent = scheduled_execution(get_agent, agent_key="reference_agent")

__all__ = ["get_agent"]
