"""Publish verified text through the shared immutable artifact store."""
from langchain_core.tools import tool
from runtime_service.workspace.artifact_refs import ArtifactWorkspace


def build_artifact_tool(root):
    @tool
    def present_artifacts(file_path: str) -> dict:
        """Publish a UTF-8 TXT result from /workspace/work/ and return its immutable reference."""
        return ArtifactWorkspace(root).publish(file_path)
    return present_artifacts
