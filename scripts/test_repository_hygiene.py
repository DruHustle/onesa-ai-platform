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
        credentials = [
            b'embedding_api_key="real-looking-value-that-is-not-a-test-fixture"',
            b'embedding_api_key="test-looking-value-that-is-not-a-placeholder"',
            b'embedding_api_key="example-looking-value-that-is-not-an-example"',
            b'embedding_api_key="real-value-with-replace-in-the-middle"',
        ]
        for credential in credentials:
            with self.subTest(credential_length=len(credential)):
                self.assertIn(
                    "credential-assignment",
                    secrets(
                        credential,
                        "onesa-ai-platform-backend/tests/test_embedding_service.py",
                    ),
                )

    def test_high_entropy_credentials_remain_detected_in_test_paths(self):
        token = bytes(
            (
                82,
                52,
                110,
                100,
                48,
                109,
                75,
                57,
                86,
                55,
                109,
                50,
                81,
                56,
                112,
                53,
                76,
                49,
                120,
                54,
                67,
                51,
                122,
                48,
                66,
                52,
                110,
                56,
                83,
                50,
                119,
                54,
                89,
                57,
            )
        )
        credential = b'embedding_api_key="' + token + b'"'
        self.assertIn(
            "credential-assignment",
            secrets(
                credential, "onesa-ai-platform-backend/tests/test_embedding_service.py"
            ),
        )

    def test_explicit_replacement_prefixes_remain_ignored(self):
        for value in (
            b"replace-with-a-provider-key",
            b"replace_with_a_random_token",
            b"replace-if-provider-requires-it",
            b"replace_if_provider_requires_it",
        ):
            credential = b'embedding_api_key="' + value + b'"'
            with self.subTest(prefix=value[:12]):
                self.assertNotIn(
                    "credential-assignment",
                    secrets(credential, ".env.example"),
                )


if __name__ == "__main__":
    unittest.main()
