"""Immutable snapshot reads reuse the installed DeepAgents file contract."""

from deepagents.backends import FilesystemBackend


def skills_operation(snapshot, operation, arguments):
    backend = FilesystemBackend(root_dir=snapshot, virtual_mode=True)
    handlers = {
        "ls": backend.ls,
        "read": backend.read,
        "glob": backend.glob,
        "grep": backend.grep,
        "download_files": backend.download_files,
    }
    arguments = dict(arguments)
    if operation == "read_raw":
        return backend.read(arguments["path"]).file_data
    if "path" in arguments and operation in {"read", "read_raw"}:
        arguments["file_path"] = arguments.pop("path")
    return handlers[operation](**arguments)
