"""Release boundary regressions: preserve populated databases and reject foreign targets."""

import unittest
from unittest.mock import MagicMock, patch

import httpx
import staging_release as release
from staging_acceptance import preview_is_protected


class StagingReleaseTests(unittest.TestCase):
    def test_preview_protection_accepts_only_denial_or_verified_vercel_login(self):
        self.assertTrue(preview_is_protected(httpx.Response(401)))
        self.assertTrue(preview_is_protected(httpx.Response(403)))
        self.assertTrue(
            preview_is_protected(
                httpx.Response(
                    302,
                    headers={"location": "https://vercel.com/sso-api?url=synthetic"},
                )
            )
        )
        for location in [
            "https://foreign.invalid/sso-api",
            "https://vercel.com.evil.invalid/sso-api",
            "http://vercel.com/sso-api",
            "https://vercel.com/other",
            "/login",
        ]:
            self.assertFalse(
                preview_is_protected(
                    httpx.Response(302, headers={"location": location})
                )
            )
        self.assertFalse(preview_is_protected(httpx.Response(200)))

    def test_absent_optional_settings_are_not_sent_as_empty_values(self):
        with patch.object(release, "write_json") as write:
            release.save_environment("base", "path", "synthetic", {"OPTIONAL": ""}, {})
            write.assert_not_called()

    def test_transient_save_retries_and_preserves_other_settings(self):
        with (
            patch.object(release, "write_json", side_effect=[429, 200]) as write,
            patch.object(release.time, "sleep"),
        ):
            release.save_environment(
                "base", "path", "synthetic", {"KEY": "synthetic"}, {}
            )
            self.assertEqual(write.call_count, 2)
            self.assertEqual(write.call_args.args[1], "path/env-vars/KEY")

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
