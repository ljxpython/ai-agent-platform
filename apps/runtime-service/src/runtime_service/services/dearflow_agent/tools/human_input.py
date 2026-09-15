"""Dynamic clarification; no side effects before interrupt."""
from langchain_core.tools import tool
from langgraph.types import interrupt
from runtime_service.services.dearflow_agent.schemas import ClarificationRequest, validate_answer


@tool
def request_information(question: str, fields: list[dict], context: str = "") -> dict:
    """Ask missing information; call alone. Fields: name, label, type, required,
    options (value/label pairs for select/multi_select). Types: text, textarea,
    number, select, multi_select, checkbox, date (YYYY-MM-DD).
    """
    request = ClarificationRequest(question=question, fields=fields, context=context)
    return validate_answer(request, interrupt(request.model_dump()))
