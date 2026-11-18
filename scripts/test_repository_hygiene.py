"""Guard the narrow public fixture exception in the publication scanner."""

import unittest

from scripts import repository_hygiene as hygiene


class PublicationFixtureTests(unittest.TestCase):
    PATH = "onesa-ai-platform-backend/tests/test_embedding_service.py"

    def test_historical_public_synthetic_value_is_not_a_secret(self):
        self.assertEqual(
            hygiene.secrets(b'        embedding_api_key="synthetic-embedding-key",\n', self.PATH),
            [],
        )

    def test_changed_fixture_still_requires_review(self):
        findings = hygiene.secrets(
            b'        embedding_api_key="synthetic-embedding-key-not-approved",\n',
            self.PATH,
        )
        self.assertIn("credential-assignment", findings)

    def test_fixture_literal_in_other_source_still_requires_review(self):
        findings = hygiene.secrets(
            b'embedding_api_key="synthetic-embedding-key"\n',
            "onesa-ai-platform-backend/app/config.py",
        )
        self.assertIn("credential-assignment", findings)

    def test_realistic_long_credential_still_requires_review(self):
        findings = hygiene.secrets(
            b'embedding_api_key="actualValue1234567890ABCDEFG"\n', self.PATH
        )
        self.assertIn("credential-assignment", findings)


if __name__ == "__main__":
    unittest.main()
