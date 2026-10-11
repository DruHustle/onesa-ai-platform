import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from app.config import Settings
from app.main import create_app


@pytest.fixture
def fixed_auth_window(monkeypatch):
    """Rate-limit assertions share one window even at a real clock boundary."""
    from app import auth

    instant = auth.now()
    monkeypatch.setattr(auth, "now", lambda: instant)


@pytest.fixture(scope="session")
def pg() -> Iterator[Engine]:
    url = os.environ.get("ONESA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("ONESA_TEST_DATABASE_URL is required for real PostgreSQL tests")
    if not (make_url(url).database or "").endswith("_test"):
        raise RuntimeError("Use a dedicated database whose name ends with _test")
    os.environ["ONESA_DATABASE_URL"] = url
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    engine = create_engine(url)
    yield engine
    engine.dispose()
    os.environ.pop("ONESA_DATABASE_URL", None)


@pytest.fixture
def api(pg: Engine) -> Iterator[TestClient]:
    with pg.begin() as connection:
        connection.execute(text("TRUNCATE users, rate_buckets CASCADE"))
    config = Settings(
        database_url=str(pg.url.render_as_string(hide_password=False)), auth_rate_limit=100
    )
    with TestClient(create_app(config)) as client:
        client.headers["Origin"] = config.public_origin
        yield client


def signup(api: TestClient, email: str = "user@example.com") -> dict[str, str]:
    response = api.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-123!", "display_name": "Tester"},
    )
    assert response.status_code == 201, response.text
    api.headers["X-CSRF-Token"] = api.cookies["onesa_csrf"]
    return response.json()
