from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from app.core.config import Settings


class GraphParameterSchemaProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build_schema(self, graph_id: str) -> dict[str, Any]:
        root = self._discover_graph_source_root()
        if root is None:
            return self._fallback_schema(graph_id, reason="graph_source_not_found")

        graph_config_path = root / "langgraph.json"
        graph_entry_file = self._resolve_graph_entry_file(graph_config_path, graph_id)
        if graph_entry_file is None:
            return self._fallback_schema(graph_id, reason="graph_entry_not_found")

        runtime_options_file = root / "runtime" / "options.py"
        runtime_context_file = root / "runtime" / "context.py"
        config_properties = self._extract_runtime_config_properties(runtime_options_file)
        context_properties = self._extract_context_properties(
            runtime_options_file,
            runtime_context_file,
        )
        metadata_properties = {
            "project_id": {"type": "string", "required": False},
        }

        graph_specific_keys = self._extract_graph_specific_config_keys(graph_entry_file)
        for key in sorted(graph_specific_keys):
            config_properties.setdefault(key, {"type": "string", "required": False})

        return {
            "graph_id": graph_id,
            "schema_version": "dynamic-v1",
            "dynamic": True,
            "sources": {
                "root": str(root),
                "langgraph_json": str(graph_config_path),
                "graph_entry": str(graph_entry_file),
                "runtime_options": str(runtime_options_file),
                "runtime_context": str(runtime_context_file),
            },
            "sections": [
                {
                    "key": "config",
                    "title": "Runtime Config",
                    "type": "object",
                    "required": False,
                    "properties": config_properties,
                },
                {
                    "key": "context",
                    "title": "Business Context",
                    "type": "object",
                    "required": False,
                    "properties": context_properties,
                    "readonly_keys": [
                        "user_id",
                        "tenant_id",
                        "role",
                        "permissions",
                        "project_id",
                    ],
                },
                {
                    "key": "metadata",
                    "title": "Search Metadata",
                    "type": "object",
                    "required": False,
                    "properties": metadata_properties,
                },
            ],
        }

    def _discover_graph_source_root(self) -> Path | None:
        explicit = self._settings.langgraph_graph_source_root
        candidates: list[Path] = []
        if isinstance(explicit, str) and explicit.strip():
            candidates.append(Path(explicit.strip()).expanduser())

        repo_root = Path(__file__).resolve().parents[3]
        candidates.extend(
            [
                repo_root / "graph_src_v2",
                repo_root.parent / "langgraph_open_teach" / "graph_src_v2",
            ]
        )

        for path in candidates:
            resolved = path.resolve()
            if resolved.exists() and (resolved / "langgraph.json").exists():
                return resolved
        return None

    def _resolve_graph_entry_file(
        self,
        graph_config_path: Path,
        graph_id: str,
    ) -> Path | None:
        if not graph_config_path.exists():
            return None
        try:
            payload = json.loads(graph_config_path.read_text(encoding="utf-8"))
        except Exception:
            return None

        graphs = payload.get("graphs")
        if not isinstance(graphs, dict):
            return None

        raw_target = graphs.get(graph_id)
        if not isinstance(raw_target, str) or not raw_target.strip():
            return None

        relative_file = raw_target.split(":", 1)[0].strip()
        if not relative_file:
            return None

        normalized = relative_file[2:] if relative_file.startswith("./") else relative_file
        candidate_roots = [graph_config_path.parent, graph_config_path.parent.parent]
        for root in candidate_roots:
            file_path = (root / normalized).resolve()
            if file_path.exists() and file_path.is_file():
                return file_path
        return None

    def _extract_runtime_config_properties(
        self,
        options_file: Path,
    ) -> dict[str, dict[str, Any]]:
        defaults: dict[str, dict[str, Any]] = {
            "model_id": {"type": "string", "required": False},
            "system_prompt": {"type": "string", "required": False},
            "enable_local_tools": {"type": "boolean", "required": False},
            "local_tools": {"type": "array[string]", "required": False},
            "enable_local_mcp": {"type": "boolean", "required": False},
            "mcp_servers": {"type": "array[string]", "required": False},
            "temperature": {"type": "number", "required": False},
            "max_tokens": {"type": "number", "required": False},
            "top_p": {"type": "number", "required": False},
        }
        if not options_file.exists():
            return defaults

        try:
            tree = ast.parse(options_file.read_text(encoding="utf-8"))
        except Exception:
            return defaults

        fields = self._extract_dataclass_fields(tree, "AppRuntimeConfig")
        mapped: dict[str, dict[str, Any]] = {}
        for key, annotation in fields.items():
            if key in {"environment", "model_spec"}:
                continue
            mapped[key] = {
                "type": self._annotation_to_schema_type(annotation),
                "required": False,
            }
        return mapped or defaults

    def _extract_context_properties(
        self,
        options_file: Path,
        context_file: Path,
    ) -> dict[str, dict[str, Any]]:
        defaults: dict[str, dict[str, Any]] = {
            "environment": {"type": "string", "required": False},
            "user_id": {"type": "string", "required": False},
            "tenant_id": {"type": "string", "required": False},
            "role": {"type": "string", "required": False},
            "permissions": {"type": "array[string]", "required": False},
        }

        if context_file.exists():
            try:
                context_tree = ast.parse(context_file.read_text(encoding="utf-8"))
                context_fields = self._extract_dataclass_fields(
                    context_tree,
                    "RuntimeContext",
                )
                for key, annotation in context_fields.items():
                    defaults[key] = {
                        "type": self._annotation_to_schema_type(annotation),
                        "required": False,
                    }
            except Exception:
                pass

        if not options_file.exists():
            return defaults

        try:
            tree = ast.parse(options_file.read_text(encoding="utf-8"))
        except Exception:
            return defaults

        key_candidates = self._extract_get_call_string_args(tree)
        for key in sorted(key_candidates):
            if key.startswith("langgraph_auth_"):
                defaults.setdefault(key, {"type": "string", "required": False})
        return defaults

    def _extract_graph_specific_config_keys(self, graph_entry_file: Path) -> set[str]:
        try:
            tree = ast.parse(graph_entry_file.read_text(encoding="utf-8"))
        except Exception:
            return set()

        keys = self._extract_get_call_string_args(tree)
        known_noise = {
            "messages",
            "allowed_decisions",
            "description",
            "interrupt_on",
            "metadata",
            "configurable",
        }
        return {key for key in keys if key and key not in known_noise and len(key) < 64}

    def _extract_dataclass_fields(
        self,
        tree: ast.AST,
        class_name: str,
    ) -> dict[str, ast.expr | None]:
        for node in tree.body if isinstance(tree, ast.Module) else []:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                result: dict[str, ast.expr | None] = {}
                for child in node.body:
                    if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                        result[child.target.id] = child.annotation
                return result
        return {}

    def _extract_get_call_string_args(self, tree: ast.AST) -> set[str]:
        keys: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "get":
                continue
            if not node.args:
                continue
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                keys.add(first_arg.value)
        return keys

    def _annotation_to_schema_type(self, annotation: ast.expr | None) -> str:
        if annotation is None:
            return "string"
        if isinstance(annotation, ast.Name):
            mapping = {
                "str": "string",
                "int": "number",
                "float": "number",
                "bool": "boolean",
                "dict": "object",
                "list": "array[string]",
            }
            return mapping.get(annotation.id, "string")
        if isinstance(annotation, ast.Subscript):
            value = annotation.value
            if isinstance(value, ast.Name) and value.id in {"list", "Sequence"}:
                return "array[string]"
            if isinstance(value, ast.Name) and value.id in {"dict", "Mapping"}:
                return "object"
            if isinstance(value, ast.Name) and value.id == "Literal":
                return "string"
        return "string"

    def _fallback_schema(self, graph_id: str, *, reason: str) -> dict[str, Any]:
        return {
            "graph_id": graph_id,
            "schema_version": "fallback-v1",
            "dynamic": False,
            "reason": reason,
            "sections": [
                {
                    "key": "config",
                    "title": "Runtime Config",
                    "type": "object",
                    "required": False,
                    "properties": {
                        "model_id": {"type": "string", "required": False},
                        "system_prompt": {"type": "string", "required": False},
                    },
                },
                {
                    "key": "context",
                    "title": "Business Context",
                    "type": "object",
                    "required": False,
                    "properties": {
                        "project_id": {"type": "string", "required": False},
                    },
                    "readonly_keys": ["project_id"],
                },
                {
                    "key": "metadata",
                    "title": "Search Metadata",
                    "type": "object",
                    "required": False,
                    "properties": {
                        "project_id": {"type": "string", "required": False},
                    },
                },
            ],
        }
