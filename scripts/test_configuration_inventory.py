"""Disclosure and boundary tests for read-only AI provider inspection."""

import json
import unittest

import configuration_inventory as inventory


class ConfigurationInventoryTests(unittest.TestCase):
    def test_only_allowlisted_origins_can_be_reported(self):
        for value in (
            "https://user:private@platform.onesa.eu",
            "https://platform.onesa.eu/?private=value",
            "https://platform.onesa.eu.evil.test",
            "http://platform.onesa.eu",
            "https://platform.onesa.eu:bad",
            "https://platform.onesa.eu/private",
            "https://example.invalid",
        ):
            self.assertIsNone(inventory.public_origin(value))
        self.assertEqual(
            inventory.public_origin("https://platform.onesa.eu"),
            "https://platform.onesa.eu",
        )

    def test_secrets_and_invalid_nonsecret_values_never_appear(self):
        private = "synthetic-secret-must-not-be-printed"
        report = inventory.settings_report(
            {
                "ONESA_DATABASE_URL": "postgresql+psycopg://" + private,
                "ONESA_MODEL_API_KEY": private,
                "ONESA_METRICS_TOKEN": private,
                "ONESA_AUTH_DELIVERY_KEY": private,
                "ONESA_ENVIRONMENT": private,
                "ONESA_PUBLIC_ORIGIN": "https://user:" + private + "@platform.onesa.eu",
            }
        )
        self.assertNotIn(private, json.dumps(report))
        self.assertEqual(report["ONESA_ENVIRONMENT"]["status"], "invalid")
        self.assertEqual(report["ONESA_PUBLIC_ORIGIN"]["status"], "invalid")
        self.assertEqual(report["ONESA_AUTH_DELIVERY_KEY"]["status"], "invalid")
        self.assertTrue(report["ONESA_DATABASE_URL"]["driver_scheme_supported"])
        self.assertEqual(report["ONESA_MODEL_BASE_URL"]["status"], "missing")

    def test_identifiers_do_not_accept_arbitrary_provider_text(self):
        self.assertIsNone(inventory.identifier("token=value with spaces"))
        self.assertEqual(inventory.identifier("srv-test123"), "srv-test123")


if __name__ == "__main__":
    unittest.main()
