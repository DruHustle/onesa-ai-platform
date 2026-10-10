"""Only synthetic documentation fixtures may receive test grants."""

import unittest

from configure_test_demo import synthetic_demo


class DemoGrantTests(unittest.TestCase):
    def test_current_and_historical_synthetic_fixtures(self):
        self.assertTrue(synthetic_demo("documentation-demo@example.com"))
        self.assertTrue(
            synthetic_demo("documentation-demo-0123456789abcdef@example.com")
        )

    def test_real_or_arbitrary_accounts_are_rejected(self):
        for email in [
            "owner@onesa.eu",
            "documentation-demo@onesa.eu",
            "documentation-demo-other@example.com",
            "user@example.com",
            "documentation-demo@example.com.extra",
        ]:
            self.assertFalse(synthetic_demo(email))


if __name__ == "__main__":
    unittest.main()
