from __future__ import annotations

from app.core.config import load_settings
from app.core.db import build_engine, create_core_tables


def main() -> None:
    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("PLATFORM_API_DATABASE_URL is required")
    engine = build_engine(settings.database_url)
    create_core_tables(engine)
    print("platform-api database initialized")


if __name__ == "__main__":
    main()
