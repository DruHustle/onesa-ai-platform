"""Synthetic URI/custody validation. No network, real credentials or DDL."""

import unittest
from urllib.parse import parse_qs, urlsplit

import oracle_migration_custody as c

RUNTIME = "postgresql+psycopg://app:synthetic@ai-staging.invalid/neondb?sslmode=require"
OWNER = "postgresql://owner:synthetic@ai-staging.invalid/neondb?sslmode=require"


class CustodyTests(unittest.TestCase):
    def test_exact_separate_owner_and_forced_tls(self):
        self.assertEqual(len(c.validate_target(OWNER, RUNTIME)), 64)
        query = parse_qs(urlsplit(c.hardened(OWNER)).query)
        self.assertEqual(query["sslmode"], ["verify-full"])
        self.assertEqual(query["channel_binding"], ["require"])
        self.assertEqual(query["sslrootcert"], ["/etc/ssl/cert.pem"])
        for scheme in ["postgresql", "postgresql+psycopg"]:
            normalized = urlsplit(
                c.hardened(OWNER.replace("postgresql:", scheme + ":"))
            )
            self.assertEqual(normalized.scheme, "postgresql+psycopg")
            self.assertEqual(normalized.netloc, urlsplit(OWNER).netloc)
        self.assertEqual(
            c.validate_target(
                OWNER.replace("ai-staging.invalid", "ep-staging.neon.invalid"),
                RUNTIME.replace("ai-staging.invalid", "ep-staging-pooler.neon.invalid"),
            ),
            c.validate_target(
                OWNER.replace("ai-staging.invalid", "ep-staging.neon.invalid"),
                RUNTIME.replace("ai-staging.invalid", "ep-staging.neon.invalid"),
            ),
        )

    def test_foreign_target_runtime_role_and_connection_overrides(self):
        for uri in [
            OWNER.replace("staging", "production"),
            OWNER.replace("owner:", "app:"),
            OWNER.replace("/neondb", "/other"),
            OWNER + "&host=evil.invalid",
            OWNER + "&sslmode=disable",
            OWNER + "&sslrootcert=/tmp/forged.pem",
            OWNER + "\nOTHER=secret",
            OWNER.replace("postgresql:", "https:"),
            OWNER.replace("synthetic@", "@"),
        ]:
            with self.subTest(uri=uri), self.assertRaises((c.Refused, ValueError)):
                c.validate_target(uri, RUNTIME)

    def test_probe_is_read_only_and_uses_retained_image(self):
        self.assertIn("BEGIN READ ONLY", c.PROBE)
        self.assertNotIn("ALTER ", c.PROBE)
        self.assertNotIn("GRANT ", c.PROBE)

    def test_existing_runtime_system_ca_does_not_change_owner_binding(self):
        runtime = RUNTIME + "&sslrootcert=system"
        self.assertEqual(
            c.validate_target(OWNER, runtime), c.validate_target(OWNER, RUNTIME)
        )
        self.assertEqual(
            parse_qs(urlsplit(c.hardened(OWNER)).query)["sslrootcert"],
            ["/etc/ssl/cert.pem"],
        )

    def test_system_ca_remains_forbidden_for_supplied_owner_connection(self):
        with self.assertRaises(c.Refused):
            c.validate_target(OWNER + "&sslrootcert=system", RUNTIME)
        with self.assertRaises(c.Refused):
            c.hardened(OWNER + "&sslrootcert=system")

    def test_runtime_reference_still_rejects_custom_or_duplicate_ca(self):
        for query in [
            "&sslrootcert=/tmp/forged.pem",
            "&sslrootcert=system&sslrootcert=/etc/ssl/cert.pem",
        ]:
            with self.subTest(query=query), self.assertRaises(c.Refused):
                c.validate_target(OWNER, RUNTIME + query)
