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
        # Build the synthetic high-entropy value at runtime so repository secret
        # scanners do not mistake the test fixture itself for a committed credential.
        token = bytes(
            (
                82, 52, 110, 100, 48, 109, 75, 57, 86, 55, 109, 50, 81, 56, 112, 53,
                76, 49, 120, 54, 67, 51, 122, 48, 66, 52, 110, 56, 83, 50, 119, 54,
                89, 57,
            )
        )
        credential = b'embedding_api_key="' + token + b'"'
        self.assertIn(
            "credential-assignment",
            secrets(
                credential, "onesa-ai-platform-backend/tests/test_embedding_service.py"
            ),
        )


if __name__ == "__main__":
    unittest.main()
