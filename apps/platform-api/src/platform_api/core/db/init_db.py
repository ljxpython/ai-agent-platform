from __future__ import annotations

from sqlalchemy.engine import Engine

from platform_api.core.db.base import Base


def import_core_models() -> None:
    # Import modules here so metadata is fully populated before create_all runs.
    import platform_api.modules.identity.models  # noqa: F401
    import platform_api.modules.projects.models  # noqa: F401
    import platform_api.modules.announcements.models  # noqa: F401
    import platform_api.modules.agents.infra.sqlalchemy.models  # noqa: F401
    import platform_api.modules.audit.models  # noqa: F401
    import platform_api.modules.runtime_catalog.infra.sqlalchemy.models  # noqa: F401
    import platform_api.modules.runtime_gateway.infra.sqlalchemy.models  # noqa: F401
    import platform_api.modules.runtime_policies.infra.sqlalchemy.models  # noqa: F401
    import platform_api.modules.platform_config.models  # noqa: F401
    import platform_api.modules.service_accounts.models  # noqa: F401


def create_core_tables(engine: Engine) -> None:
    import_core_models()

    Base.metadata.create_all(engine)
