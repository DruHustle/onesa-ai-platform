"""Release boundary regressions: preserve populated databases and reject foreign targets."""

import unittest
from unittest.mock import MagicMock, patch

import staging_release as release


class StagingReleaseTests(unittest.TestCase):
    def test_foreign_or_pooled_migration_targets_are_rejected(self):
        for host in ["foreign.invalid", release.DATABASE_HOST]:
            with self.assertRaises(ValueError):
                release.migration_url(
                    f"postgresql://neondb_owner:synthetic@{host}/neondb?sslmode=require&channel_binding=require"
                )

    def test_tls_and_database_identity_cannot_be_relaxed(self):
        host = release.DATABASE_HOST.replace("-pooler", "")
        for suffix in [
            "/other?sslmode=require&channel_binding=require",
            "/neondb?sslmode=disable&channel_binding=require",
            "/neondb?sslmode=require",
        ]:
            with self.assertRaises(ValueError):
                release.migration_url(
                    f"postgresql://neondb_owner:synthetic@{host}{suffix}"
                )

    def test_existing_unidentified_schema_is_preserved(self):
        engine, connection = MagicMock(), MagicMock()
        engine.begin.return_value.__enter__.return_value = connection
        connection.connection.driver_connection.pgconn.ssl_in_use = True
        connection.scalar.side_effect = ["neondb", 8, False, "unidentified-revision"]
        with (
            patch.object(release, "create_engine", return_value=engine),
            patch.object(release.command, "upgrade") as migrate,
            patch.dict(release.os.environ),
        ):
            with self.assertRaises(ValueError):
                release.initialize(
                    release.make_url(
                        "postgresql+psycopg://synthetic:synthetic@localhost/neondb"
                    ),
                    {},
                )
            migrate.assert_not_called()
            connection.connection.driver_connection.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
