import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app


def test_production_requires_https_secure_cookies_and_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production")
    assert Settings(
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
        environment="production",
        secure_cookies=True,
        public_origin="https://example.invalid",
        metrics_token="x" * 32,
    )
    with TestClient(create_app(config)) as api:
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
        connection.execute(text("GRANT USAGE ON SCHEMA public TO onesa_app_test"))
        connection.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE "
                "ON ALL TABLES IN SCHEMA public TO onesa_app_test"
            )
        )
    url = pg.url.set(username="onesa_app_test", password="test-role-only").render_as_string(
        hide_password=False
    )
    config = Settings(
        database_url=url,
        environment="production",
        secure_cookies=True,
        public_origin="https://example.invalid",
        metrics_token="x" * 32,
    )
    with TestClient(create_app(config)) as api:
        assert api.get("/ready").status_code == 200


def test_readiness_metrics_report_failed_model_without_private_details() -> None:
    from unittest.mock import AsyncMock

    config = Settings(metrics_token="test-metrics-only")
    with TestClient(create_app(config)) as api:
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
