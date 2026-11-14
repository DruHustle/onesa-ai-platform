"""Release profiles accept implemented hosted adapters and reject fallback AI."""

import unittest

import hosted
from evidence import Rejected


class ServingProfileTests(unittest.TestCase):
    def profile(
        self, model="cloudflare", embedding="cloudflare", environment="staging"
    ):
        return {
            "ONESA_ENVIRONMENT": environment,
            "ONESA_MODEL_BACKEND": model,
            "ONESA_EMBEDDING_BACKEND": embedding,
        }

    def test_cloudflare_and_existing_real_serving_profiles_are_accepted(self):
        for model in ("cloudflare", "ollama", "vllm"):
            for embedding in ("cloudflare", "http"):
                with self.subTest(model=model, embedding=embedding):
                    hosted.require_full_serving_profile(self.profile(model, embedding))

    def test_mock_lexical_missing_and_wrong_environment_cannot_qualify(self):
        for settings in (
            self.profile(model="mock"),
            self.profile(embedding="lexical"),
            self.profile(model="unknown"),
            self.profile(embedding="unknown"),
            self.profile(environment="production"),
            self.profile(environment="development"),
            {},
        ):
            with self.subTest(settings=settings), self.assertRaises(Rejected):
                hosted.require_full_serving_profile(settings)
