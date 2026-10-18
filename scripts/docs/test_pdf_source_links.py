"""Canonical PDF references cannot silently point to local or wrong-audience sites."""

import unittest

from pdf_links import validate_manual_source_links


class ManualSourceLinksTests(unittest.TestCase):
    def test_public_and_protected_sources_use_their_own_canonical_host(self):
        for scope, origin in [
            ("public", "https://docs.onesa.eu"),
            ("internal", "https://docs.engineering.onesa.eu"),
        ]:
            validate_manual_source_links(
                {origin + "/docs/engineering/EXAMPLE"},
                ["docs/engineering/EXAMPLE.md"],
                scope,
            )

    def test_local_and_wrong_audience_references_are_rejected(self):
        for origin in ["http://localhost:3201", "https://docs.onesa.eu"]:
            with self.subTest(origin=origin), self.assertRaises(AssertionError):
                validate_manual_source_links(
                    {origin + "/docs/engineering/EXAMPLE"},
                    ["docs/engineering/EXAMPLE.md"],
                    "internal",
                )

    def test_every_source_requires_a_reference(self):
        with self.assertRaises(AssertionError):
            validate_manual_source_links(
                {"https://docs.onesa.eu/docs/public/one"},
                ["docs/public/one.md", "docs/public/two.md"],
                "public",
            )
