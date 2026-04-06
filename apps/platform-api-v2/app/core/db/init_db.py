from __future__ import annotations

from sqlalchemy.engine import Engine

from app.core.db.base import Base


def import_core_models() -> None:
    # Import modules here so metadata is fully populated before create_all runs.
    import app.modules.identity.infra.sqlalchemy.models  # noqa: F401
    import app.modules.projects.infra.sqlalchemy.models  # noqa: F401
    import app.modules.announcements.infra.sqlalchemy.models  # noqa: F401
    import app.modules.assistants.infra.sqlalchemy.models  # noqa: F401
    import app.modules.audit.infra.sqlalchemy.models  # noqa: F401
    import app.modules.operations.infra.sqlalchemy.models  # noqa: F401
    import app.modules.runtime_catalog.infra.sqlalchemy.models  # noqa: F401
    import app.modules.runtime_policies.infra.sqlalchemy.models  # noqa: F401
    import app.modules.platform_config.infra.sqlalchemy.models  # noqa: F401


def create_core_tables(engine: Engine) -> None:
    import_core_models()

    Base.metadata.create_all(engine)
