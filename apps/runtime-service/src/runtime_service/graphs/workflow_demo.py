"""LangGraph entrypoint for the deterministic workflow demo."""

from runtime_service.runtime.scheduled import scheduled_execution
from runtime_service.services.demo.workflow_demo.agent import get_agent

get_agent = scheduled_execution(get_agent, agent_key="workflow_demo")

__all__ = ["get_agent"]
