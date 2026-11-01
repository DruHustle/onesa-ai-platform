from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Connection, Engine, create_engine, event
from sqlalchemy.orm import Session

from app.errors import fail


def make_engine(url: str) -> Engine:
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=0,
        pool_timeout=2,
        connect_args={"connect_timeout": 3},
    )

    @event.listens_for(engine, "begin")
    def bound_transaction(connection: Connection) -> None:
        # Transaction-local settings survive PgBouncer backend switching without
        # unsupported startup options or leaking session state to another client.
        connection.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
        # Stable API/export timestamps must not depend on the host or pooled
        # connection's timezone. In-memory timestamps already use UTC.
        connection.exec_driver_sql("SET LOCAL TIME ZONE 'UTC'")

    return engine


def database(request: Request) -> Iterator[Session]:
    engine: Engine | None = request.app.state.engine
    if engine is None:
        fail(503, "database_unavailable", "Database is not configured")
    with Session(engine, expire_on_commit=False) as db:
        yield db


REQUIRED_SCHEMA_REVISION = "20261026_cybersecurity"
