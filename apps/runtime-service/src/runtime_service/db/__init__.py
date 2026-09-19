"""Connections and explicit migrations for Runtime-owned application data."""
import os

import psycopg
from psycopg.rows import dict_row


def normalize_dsn(dsn: str | None = None) -> str:
    return (dsn or os.environ["DATABASE_URI"]).replace(
        "postgresql+asyncpg://", "postgresql://"
    ).replace("postgresql+psycopg://", "postgresql://")


def connect(dsn: str | None = None, *, row_factory=dict_row):
    return psycopg.connect(normalize_dsn(dsn), row_factory=row_factory)


def upgrade(dsn: str | None = None) -> None:
    """Serialize and atomically apply the application chain, never the engine chain."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    config = Config()
    config.set_main_option("script_location", str(Path(__file__).with_name("migrations")))
    engine = create_engine("postgresql+psycopg://", creator=lambda: psycopg.connect(normalize_dsn(dsn)), poolclass=NullPool)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(746183209)")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    finally:
        engine.dispose()
