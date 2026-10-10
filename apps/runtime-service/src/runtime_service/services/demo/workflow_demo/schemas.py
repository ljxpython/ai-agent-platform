"""State schema owned by the workflow demo."""

from typing import Annotated, Literal

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from runtime_service.middlewares.execution_budget import GraphBudgetState
from runtime_service.middlewares.plan_mode import PlanModeState

MessageValue = Annotated[list[object], add_messages]


class WorkflowState(TypedDict, total=False):
    messages: MessageValue
    message: str
    route: Literal["approve", "reject", "respond"]
    requires_confirmation: bool
    confirmation: Literal["approve", "reject"]
    resume_error: str | None
    prepared_count: int
    response: str
    _runtime_model_ref: str


class WorkflowBudgetState(WorkflowState, GraphBudgetState, PlanModeState):
    pass
