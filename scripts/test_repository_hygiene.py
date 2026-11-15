import unittest

from repository_hygiene import secrets


class RepositoryHygieneTests(unittest.TestCase):
    def test_exact_historical_synthetic_fixture_is_path_scoped(self):
        fixture = b'embedding_api_key="synthetic-embedding-key"'
        self.assertNotIn(
            "credential-assignment",
            secrets(
                fixture, "onesa-ai-platform-backend/tests/test_embedding_service.py"
            ),
        )
        self.assertIn("credential-assignment", secrets(fixture, "app/config.py"))

    def test_other_long_credentials_remain_detected_in_test_paths(self):
        credential = (
            b'embedding_api_key="real-looking-value-that-is-not-a-test-fixture"'
        )
        self.assertIn(
            "credential-assignment",
            secrets(
                credential, "onesa-ai-platform-backend/tests/test_embedding_service.py"
            ),
        )


if __name__ == "__main__":
    unittest.main()
