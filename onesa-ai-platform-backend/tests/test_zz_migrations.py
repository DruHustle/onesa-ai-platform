import io
import json
import os
import runpy
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text

from app.database import REQUIRED_SCHEMA_REVISION


@pytest.mark.parametrize("driver", ["postgresql", "postgresql+psycopg"])
def test_owner_runner_migration_uses_supplied_connection_without_inherited_url(
    pg: Engine, monkeypatch, capsys, driver: str
) -> None:
    """Exercise actual Alembic and DML grants in the isolated _test database.

    Only connection establishment is substituted: local CI Postgres has no hosted
    TLS certificate. The runner must still request all required TLS options.
    """
    assert (pg.url.database or "").endswith("_test")
    program = runpy.run_path(
        str(Path(__file__).parents[2] / "scripts/release/oracle_ai_runner.py")
    )["MIGRATION_PROGRAM"]
    role = "onesa_migration_test_" + uuid4().hex
    owner = pg.url.set(drivername=driver).render_as_string(hide_password=False)
    request = {
        "owner": owner,
        "runtime": "postgresql+psycopg://" + role + ":synthetic@localhost/onesa_test",
    }

    def supplied_engine(url, *, connect_args):
        assert url == pg.url.set(drivername="postgresql+psycopg")
        assert connect_args == {
            "connect_timeout": 10,
            "sslmode": "verify-full",
            "sslrootcert": "/etc/ssl/cert.pem",
            "channel_binding": "require",
        }
        return pg

    monkeypatch.setattr(sqlalchemy, "create_engine", supplied_engine)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))
    monkeypatch.delenv("ONESA_DATABASE_URL", raising=False)
    with pg.begin() as connection:
        connection.execute(text('CREATE ROLE "' + role + '" NOLOGIN'))
    try:
        exec(program, {})
        observed = capsys.readouterr().out
        assert owner not in observed
        assert json.loads(observed) == {
            "migration_revision": "20261025_twins",
            "runtime_DDL_granted": False,
            "runtime_new_tables_DML_granted": 9,
        }
        assert os.environ["ONESA_DATABASE_URL"] == pg.url.set(
            drivername="postgresql+psycopg"
        ).render_as_string(hide_password=False)
        with pg.connect() as connection:
            assert connection.scalar(
                text("SELECT has_table_privilege(:role,'twin_assets',:permissions)"),
                {"role": role, "permissions": "SELECT,INSERT,UPDATE,DELETE"},
            )
            assert not connection.scalar(
                text("SELECT has_schema_privilege(:role,'public','CREATE')"), {"role": role}
            )
            assert not connection.scalar(
                text("SELECT has_table_privilege(:role,'alembic_version','UPDATE')"), {"role": role}
            )
    finally:
        # Only this test's random no-login role exists; no other role/data is touched.
        with pg.begin() as connection:
            connection.execute(text('DROP OWNED BY "' + role + '"'))
            connection.execute(text('DROP ROLE "' + role + '"'))


def test_upgrade_downgrade_and_model_consistency(pg: Engine) -> None:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.check(config)
    # A rollback must not silently erase eligibility, mail or private-upload state.
    with pytest.raises(RuntimeError, match="explicit forward rollback plan"):
        command.downgrade(config, "base")
    with pg.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == REQUIRED_SCHEMA_REVISION
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
        "industrial_investigations",
        "twin_templates",
        "twin_assets",
        "twin_files",
        "twin_models",
        "twin_sources",
        "twin_readings",
        "twin_events",
        "twin_notes",
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
