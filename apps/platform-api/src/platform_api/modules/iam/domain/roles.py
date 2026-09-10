from __future__ import annotations

from enum import StrEnum


class PlatformRole(StrEnum):
    SUPER_ADMIN = "platform_super_admin"
    OPERATOR = "platform_operator"
    VIEWER = "platform_viewer"


class ProjectRole(StrEnum):
    ADMIN = "project_admin"
    EDITOR = "project_editor"
    EXECUTOR = "project_executor"

    @classmethod
    def from_db(cls, value: str) -> "ProjectRole":
        mapping = {
            "admin": cls.ADMIN,
            "editor": cls.EDITOR,
            "executor": cls.EXECUTOR,
            cls.ADMIN.value: cls.ADMIN,
            cls.EDITOR.value: cls.EDITOR,
            cls.EXECUTOR.value: cls.EXECUTOR,
        }
        try:
            return mapping[value]
        except KeyError as exc:
            raise ValueError(f"unsupported_project_role:{value}") from exc

    def to_db(self) -> str:
        mapping = {
            ProjectRole.ADMIN: "admin",
            ProjectRole.EDITOR: "editor",
            ProjectRole.EXECUTOR: "executor",
        }
        return mapping[self]
