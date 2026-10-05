"""Dear Agent graph registration; service owns composition."""

from runtime_service.runtime.scheduled import scheduled_execution
from runtime_service.services.dearflow_agent.agent import get_agent

get_agent = scheduled_execution(get_agent, agent_key="dearflow_agent")

__all__ = ["get_agent"]
