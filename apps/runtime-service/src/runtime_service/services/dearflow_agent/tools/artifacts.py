"""Publish verified text through the shared immutable artifact store."""
from langchain_core.tools import tool

from runtime_service.workspace.artifact_refs import ArtifactWorkspace


def build_artifact_tool(root):
    @tool
    def present_artifacts(file_path: str) -> dict:
        """Publish one validated .txt/.md/.bib/.csv/.json/.html/.css/.js/.pptx or source .zip result from /workspace/work/; return an immutable reference."""
        return ArtifactWorkspace(root).publish(file_path)
    present_artifacts.handle_tool_error = True
    return present_artifacts
