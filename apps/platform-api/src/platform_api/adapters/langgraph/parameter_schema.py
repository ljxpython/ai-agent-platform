from __future__ import annotations

from typing import TYPE_CHECKING, Any

from platform_api.core.context.models import ActorContext
from platform_api.core.errors import ServiceUnavailableError
from platform_api.core.runtime_contract import build_execution_config_schema_properties

if TYPE_CHECKING:
    from platform_api.modules.runtime_catalog.application.service import RuntimeCatalogService


class GraphParameterSchemaProvider:
    """Present permitted parameters from the deployed graph, never local Python sources."""

    def __init__(self, catalog: RuntimeCatalogService) -> None:
        self._catalog = catalog

    async def build_schema(
        self, graph_id: str, *, actor: ActorContext, project_id: str,
    ) -> dict[str, Any]:
        schemas = await self._catalog.get_graph_schema(
            actor=actor, project_id=project_id, graph_id=graph_id,
        )
        context = schemas.get("context_schema")
        if schemas.get("graph_id") != graph_id or (
            context is not None and not isinstance(context, dict)
        ):
            raise ServiceUnavailableError(
                code="runtime_graph_schema_invalid", message="Runtime returned an invalid graph schema",
            )
        properties = (context or {}).get("properties", {})
        if not isinstance(properties, dict):
            raise ServiceUnavailableError(
                code="runtime_graph_schema_invalid", message="Runtime returned invalid context properties",
            )
        # These are the existing public model overrides. Tool grants, identity,
        # internal model references and arbitrary configurable fields are not editable.
        editable = {"model_id", "temperature", "max_tokens", "top_p"}
        return {
            "graph_id": graph_id,
            "schema_version": "remote-v1",
            "dynamic": True,
            "sections": [
                {
                    "key": "config", "title": "Execution Config", "type": "object",
                    "required": False, "properties": build_execution_config_schema_properties(),
                },
                {
                    "key": "context", "title": "Runtime Context", "type": "object",
                    "required": False,
                    "properties": {key: value for key, value in properties.items() if key in editable},
                },
            ],
        }
