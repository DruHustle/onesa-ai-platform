"""API timestamps stay stable when the database host uses a different timezone."""

import pytest
from sqlalchemy import text

from app.database import make_engine


@pytest.mark.parametrize("zone", ["Asia/Singapore", "America/New_York"])
def test_database_transactions_use_utc_without_leaking_session_configuration(pg, zone):
    # Only the disposable PostgreSQL fixture gets this startup option. The
    # application itself must work with transaction-pooling providers too.
    url = pg.url.update_query_dict({"options": "-c timezone=" + zone})
    engine = make_engine(url.render_as_string(hide_password=False))
    try:
        with engine.connect() as connection:
            for _ in range(2):
                with connection.begin():
                    observed = connection.scalar(
                        text("SELECT TIMESTAMPTZ '2026-06-10 00:00:00+00'")
                    )
                    assert observed.isoformat() == "2026-06-10T00:00:00+00:00"
                assert (
                    connection.connection.driver_connection.info.parameter_status("TimeZone")
                    == zone
                )
    finally:
        engine.dispose()
