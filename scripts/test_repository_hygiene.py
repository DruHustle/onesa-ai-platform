"""Guard the narrow public fixture exception in the publication scanner."""

import unittest

from scripts import repository_hygiene as hygiene


class PublicationFixtureTests(unittest.TestCase):
    PATH = "onesa-ai-platform-backend/tests/test_embedding_service.py"
    FIXTURE = b'        embedding_api_key="synthetic-embedding-key",\n'

    def test_historical_public_synthetic_value_is_not_a_secret(self):
        self.assertEqual(hygiene.secrets(self.FIXTURE, self.PATH), [])

    def test_changed_fixture_still_requires_review(self):
        changed = b'embedding_api_key="synthetic-embedding-key-not-approved"\n'
        self.assertIn("credential-assignment", hygiene.secrets(changed, self.PATH))

    def test_fixture_prefix_with_other_data_still_requires_review(self):
        changed = b'embedding_api_key="synthetic-embedding-key:unexpected-tail",\n'
        self.assertIn("credential-assignment", hygiene.secrets(changed, self.PATH))

    def test_fixture_literal_in_other_source_still_requires_review(self):
        other_path = "onesa-ai-platform-backend/app/config.py"
        self.assertIn(
            "credential-assignment", hygiene.secrets(self.FIXTURE, other_path)
        )

    def test_realistic_long_credential_still_requires_review(self):
        actual = b'embedding_api_key="actualValue1234567890ABCDEFG"\n'
        self.assertIn("credential-assignment", hygiene.secrets(actual, self.PATH))


if __name__ == "__main__":
    unittest.main()
