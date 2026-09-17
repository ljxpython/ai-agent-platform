"""Shared publication tool for thread-bound agents."""

from langchain_core.tools import tool

from runtime_service.workspace.artifact_refs import ArtifactWorkspace


def build_artifact_tool(root):
    @tool
    def present_artifacts(file_path: str) -> dict:
        """Publish a validated document, source file, image or archive from /workspace/work/, generated/ or charts/; return an immutable reference."""
        return ArtifactWorkspace(root).publish(file_path)

    present_artifacts.handle_tool_error = True
    return present_artifacts
