from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text


def test_upgrade_downgrade_and_model_consistency(pg: Engine) -> None:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.check(config)
    # A rollback must not silently erase eligibility, mail or private-upload state.
    with pytest.raises(RuntimeError, match="explicit forward rollback plan"):
        command.downgrade(config, "base")
    with pg.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "20261010_capacity"
        )
    command.check(config)
    assert {
        "users",
        "messages",
        "documents",
        "document_chunks",
        "agent_runs",
        "trips",
        "identity_tokens",
        "identity_mail",
        "bounded_uploads",
        "model_leases",
    } <= set(inspect(pg).get_table_names())
    # Retain the original reversible-history check in a separate disposable schema.
    schema = "migration_test_" + uuid4().hex
    with pg.connect() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(
            text(f'CREATE TABLE "{schema}".alembic_version (version_num varchar(32) PRIMARY KEY)')
        )
        connection.execute(text(f'SET search_path TO "{schema}", public'))
        connection.commit()
        historical = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        historical.attributes["connection"] = connection
        try:
            command.upgrade(historical, "608f3f79f76e")
            assert "users" in inspect(connection).get_table_names(schema=schema)
            command.downgrade(historical, "base")
            assert inspect(connection).get_table_names(schema=schema) == ["alembic_version"]
        finally:
            connection.rollback()
            connection.execute(text("SET search_path TO public"))
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            connection.commit()
