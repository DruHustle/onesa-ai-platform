from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.errors import fail


def make_engine(url: str) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=0,
        pool_timeout=2,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=5000"},
    )


def database(request: Request) -> Iterator[Session]:
    engine: Engine | None = request.app.state.engine
    if engine is None:
        fail(503, "database_unavailable", "Database is not configured")
    with Session(engine, expire_on_commit=False) as db:
        yield db


REQUIRED_SCHEMA_REVISION = "20261010_capacity"
