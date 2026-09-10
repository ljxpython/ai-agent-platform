from __future__ import annotations

from platform_api.config import load_settings
from platform_api.core.db import build_engine, create_core_tables


def main() -> None:
    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("PLATFORM_API_DATABASE_URL is required")
    engine = build_engine(settings.database_url)
    try:
        create_core_tables(engine)
    finally:
        engine.dispose()
    print("platform-api database initialized")


if __name__ == "__main__":
    main()
