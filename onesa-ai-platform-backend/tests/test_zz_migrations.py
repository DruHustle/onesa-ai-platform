from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect


def test_upgrade_downgrade_and_model_consistency(pg: Engine) -> None:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.check(config)
    command.downgrade(config, "base")
    assert inspect(pg).get_table_names() == ["alembic_version"]
    command.upgrade(config, "head")
    assert {"users", "messages", "documents", "document_chunks", "agent_runs", "trips"} <= set(
        inspect(pg).get_table_names()
    )
    command.check(config)
