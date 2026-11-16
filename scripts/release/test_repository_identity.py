"""Local checkouts cannot silently change release policy or repository identity."""

import runpy
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class CheckoutIdentityTests(unittest.TestCase):
    def test_renamed_checkout_keeps_canonical_evidence_and_qualification(self):
        with tempfile.TemporaryDirectory() as directory:
            scripts = (
                Path(directory) / "arbitrary-review-folder" / "scripts" / "release"
            )
            scripts.mkdir(parents=True)
            for name in ("evidence.py", "qualify.py"):
                with self.subTest(script=name):
                    target = scripts / name
                    shutil.copyfile(ROOT / "scripts" / "release" / name, target)
                    module = runpy.run_path(str(target))
                    self.assertEqual(module["PRODUCT"], "onesa-ai-platform")
                    if name == "evidence.py":
                        self.assertEqual(
                            module["REPOSITORY"], "DruHustle/onesa-ai-platform"
                        )
                        self.assertEqual(module["POLICY"]["ci"], "ci.yml")


if __name__ == "__main__":
    unittest.main()
