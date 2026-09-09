"""Two explicit roles; no model-global profiles or implicit extra subagent."""

from collections.abc import Callable, Sequence

from deepagents import SubAgent
from deepagents.backends.protocol import BackendProtocol
from deepagents.middleware import FilesystemMiddleware, FilesystemPermission
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel

from runtime_service.services.demo.showcase_demo.prompts import (
    IMPLEMENTOR_PROMPT,
    RESEARCH_PROMPT,
)

READ_TOOLS = ("ls", "read_file", "glob", "grep")
WORK_TOOLS = (*READ_TOOLS, "write_file", "edit_file", "execute")
APPROVALS = {
    name: {"allowed_decisions": ["approve", "edit", "reject"]}
    for name in ("write_file", "edit_file", "execute")
}
PERMISSIONS = [
    FilesystemPermission(operations=["write"], paths=["/skills/**"], mode="deny"),
]


def build_subagents(
    model: BaseChatModel,
    backend: BackendProtocol,
    middleware: Callable[[Sequence[str]], list[AgentMiddleware]],
) -> list[SubAgent]:
    return [
        {
            "name": "research",
            "description": "只读分析实际项目，返回问题依据与最小修改建议。",
            "system_prompt": RESEARCH_PROMPT,
            "model": model,
            "tools": [],
            "permissions": PERMISSIONS,
            "interrupt_on": {},
            "middleware": [
                FilesystemMiddleware(
                    backend=backend, tools=list(READ_TOOLS), _permissions=PERMISSIONS
                ),
                *middleware(READ_TOOLS),
            ],
        },
        {
            # Defining the official default name suppresses the implicit unrestricted one.
            "name": "general-purpose",
            "description": "按明确需求实现最小修改，通过审批后执行真实验证。",
            "system_prompt": IMPLEMENTOR_PROMPT,
            "model": model,
            "tools": [],
            "permissions": PERMISSIONS,
            "interrupt_on": APPROVALS,
            "middleware": [
                FilesystemMiddleware(
                    backend=backend,
                    tools=list(WORK_TOOLS),
                    _permissions=PERMISSIONS,
                    max_execute_timeout=60,
                ),
                *middleware(WORK_TOOLS),
            ],
        },
    ]
