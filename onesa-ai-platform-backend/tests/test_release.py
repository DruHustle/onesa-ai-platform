import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.inference import MockModelClient
from app.main import create_app

PRODUCTION_INFERENCE = {
    "model_backend": "ollama",
    "model_base_url": "https://model.example.invalid/v1",
    "model_api_key": "security-test-fixture-only",
}


def test_production_requires_https_secure_cookies_and_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production")
    assert Settings(
        **PRODUCTION_INFERENCE,
        environment="production",
        secure_cookies=True,
        public_origin="https://example.invalid",
        database_url="postgresql+psycopg://localhost/onesa",
        metrics_token="x" * 32,
    )


def test_metrics_protected_and_request_size_limit() -> None:
    with TestClient(create_app(Settings(metrics_token="private-token"))) as api:
        assert api.get("/metrics").status_code == 403
        response = api.get("/metrics", headers={"Authorization": "Bearer private-token"})
        assert response.status_code == 200 and "onesa_http_requests_total" in response.text
        oversized = api.post("/api/v1/auth/login", content=b"x" * (6 * 1024 * 1024 + 1))
        assert oversized.status_code == 413
        assert oversized.json()["error"]["code"] == "request_too_large"


def test_production_rejects_superuser_database(pg) -> None:
    url = pg.url.render_as_string(hide_password=False)
    config = Settings(
        database_url=url,
        **PRODUCTION_INFERENCE,
        environment="production",
        secure_cookies=True,
        public_origin="https://example.invalid",
        metrics_token="x" * 32,
    )
    with TestClient(create_app(config, MockModelClient())) as api:
        assert api.get("/ready").status_code == 503


def test_production_readiness_accepts_restricted_database_role(pg) -> None:
    from sqlalchemy import text

    with pg.begin() as connection:
        connection.execute(
            text(
                "DO $$ BEGIN IF NOT EXISTS "
                "(SELECT 1 FROM pg_roles WHERE rolname='onesa_app_test') "
                "THEN CREATE ROLE onesa_app_test LOGIN PASSWORD 'test-role-only'; "
                "END IF; END $$"
            )
        )
        connection.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
        connection.execute(text("GRANT USAGE ON SCHEMA public TO onesa_app_test"))
        connection.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE "
                "ON ALL TABLES IN SCHEMA public TO onesa_app_test"
            )
        )
        connection.execute(
            text(
                "REVOKE INSERT, UPDATE, DELETE, TRUNCATE, TRIGGER ON "
                "alembic_version FROM onesa_app_test"
            )
        )
    url = pg.url.set(username="onesa_app_test", password="test-role-only").render_as_string(
        hide_password=False
    )
    config = Settings(
        database_url=url,
        **PRODUCTION_INFERENCE,
        environment="production",
        secure_cookies=True,
        public_origin="https://example.invalid",
        metrics_token="x" * 32,
    )
    with TestClient(create_app(config, MockModelClient())) as api:
        assert api.get("/ready").status_code == 200


def test_runtime_timeout_is_applied_to_each_transaction(pg) -> None:
    from sqlalchemy import text

    from app.database import make_engine

    engine = make_engine(pg.url.render_as_string(hide_password=False))
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SHOW statement_timeout")) == "5s"
            connection.commit()
            assert connection.scalar(text("SHOW statement_timeout")) == "5s"
            connection.rollback()
            assert connection.scalar(text("SHOW statement_timeout")) == "5s"
    finally:
        engine.dispose()


def test_readiness_metrics_report_failed_model_without_private_details() -> None:
    from unittest.mock import AsyncMock

    config = Settings(
        metrics_token="test-metrics-only", model_base_url="https://model.example.invalid/v1"
    )
    with TestClient(create_app(config, MockModelClient())) as api:
        api.app.state.model_client.healthy = AsyncMock(return_value=False)
        assert api.get("/ready").status_code == 503
        response = api.get("/metrics", headers={"Authorization": "Bearer test-metrics-only"})
        assert 'onesa_dependency_available{dependency="model"} 0.0' in response.text
        assert config.model_base_url not in response.text


def test_pdf_subprocess_preserves_text_and_rejects_malformed_input() -> None:
    import io

    from fastapi import HTTPException
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    from app.knowledge import extract

    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 10 100 Td (Private knowledge fixture) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    assert extract(output.getvalue(), "owned.pdf", "application/pdf") == "Private knowledge fixture"
    with pytest.raises(HTTPException) as error:
        extract(b"%PDF-malformed", "owned.pdf", "application/pdf")
    assert error.value.status_code == 422


def test_staging_requires_production_session_controls() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="staging", public_origin="http://example.invalid")


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://localhost:11434/v1",
        "https://localhost/v1",
        "https://host.docker.internal/v1",
        "https://127.0.0.1/v1",
        "https://[::1]/v1",
        "https://169.254.169.254/v1",
    ],
)
def test_production_refuses_development_inference(endpoint):
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            secure_cookies=True,
            public_origin="https://example.invalid",
            database_url="postgresql+psycopg://localhost/onesa",
            metrics_token="x" * 32,
            model_backend="ollama",
            model_base_url=endpoint,
            model_api_key="fixture-only",
        )


def test_production_refuses_mock_inference():
    with pytest.raises(ValidationError, match="real inference"):
        Settings(
            environment="production",
            secure_cookies=True,
            public_origin="https://example.invalid",
            database_url="postgresql+psycopg://localhost/onesa",
            metrics_token="x" * 32,
        )


def test_core_health_survives_inference_outage_without_claiming_model_readiness(pg):
    from unittest.mock import AsyncMock

    client = MockModelClient()
    client.healthy = AsyncMock(return_value=False)
    config = Settings(database_url=pg.url.render_as_string(hide_password=False))
    with TestClient(create_app(config, client)) as api:
        assert api.get("/health").status_code == 200
        core = api.get("/core-ready")
        assert core.status_code == 200
        assert core.json()["inference"] == "degraded"
        assert api.get("/ready").status_code == 503


@pytest.mark.parametrize(
    "origin",
    [
        "https://user:password@onesa.example.com",
        "https://onesa.example.com/path",
        "https://onesa.example.com?token=example",
    ],
)
def test_exact_public_origin(origin: str):
    with pytest.raises(ValueError, match="exact origin"):
        Settings(public_origin=origin)


def test_render_cannot_start_with_implicit_development_defaults(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(ValidationError, match="explicit staging or production"):
        Settings(environment="development")
    with pytest.raises(ValidationError, match="explicit staging or production"):
        Settings(environment="test")


def test_configuration_errors_never_render_secret_input_values():
    marker = "synthetic-private-credential-not-for-logs"
    with pytest.raises(ValidationError) as error:
        Settings(environment="production", model_api_key=marker, database_url=marker)
    assert marker not in str(error.value)


def test_migrations_do_not_require_a_provisioned_inference_service(pg, monkeypatch):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("ONESA_ENVIRONMENT", "production")
    monkeypatch.setenv("ONESA_MODEL_BACKEND", "mock")
    monkeypatch.setenv("ONESA_DATABASE_URL", pg.url.render_as_string(hide_password=False))
    with pytest.raises(ValidationError):
        Settings()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
