"""Opt-in reversible migration check against a disposable PostgreSQL database."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_context_capacity_migration_preserves_existing_model():
    url = os.getenv("CONTEXT_TEST_PLATFORM_DATABASE_URL")
    if not url:
        pytest.skip("CONTEXT_TEST_PLATFORM_DATABASE_URL must be a disposable database")
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[2] / "migrations")
    )
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "20260925_0005")
    engine = create_engine(url)
    model_id = uuid4()
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO runtime_catalog_models "
                    "(id,display_name,provider,base_url,protocol,model_name,api_key_ciphertext,enabled,scope_type) "
                    "VALUES (:id,'existing','openai','https://example.test/v1','openai','existing','ciphertext-preserved',true,'platform')"
                ),
                {"id": model_id},
            )
        command.upgrade(config, "head")
        with engine.begin() as connection:
            row = connection.execute(
                text(
                    "SELECT context_window_tokens,api_key_ciphertext,scope_type FROM runtime_catalog_models WHERE id=:id"
                ),
                {"id": model_id},
            ).one()
            assert tuple(row) == (None, "ciphertext-preserved", "platform")
            connection.execute(
                text(
                    "UPDATE runtime_catalog_models SET context_window_tokens=12000 WHERE id=:id"
                ),
                {"id": model_id},
            )
        command.downgrade(config, "20260925_0005")
        assert "context_window_tokens" not in {
            column["name"]
            for column in inspect(engine).get_columns("runtime_catalog_models")
        }
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text(
                        "SELECT api_key_ciphertext FROM runtime_catalog_models WHERE id=:id"
                    ),
                    {"id": model_id},
                ).scalar_one()
                == "ciphertext-preserved"
            )
        command.upgrade(config, "head")
    finally:
        engine.dispose()
