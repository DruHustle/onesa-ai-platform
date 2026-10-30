"""Private fixtures confer neither infrastructure trust nor release authority."""

import copy
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import oracle_owner as owner
import test_oracle_install as fixtures


class PrivateInstallTests(unittest.TestCase):
    PRIVATE_DOCS = True
    setUp = fixtures.InstallTests.setUp
    put = fixtures.InstallTests.put
    seal = fixtures.InstallTests.seal
    validate = fixtures.InstallTests.validate

    def test_independent_private_installation_is_only_preparation(self):
        _manifest, target, payloads, _ci = self.validate()
        self.assertEqual(
            target.name, "ai-docs-internal-" + self.manifest["source_tree"]
        )
        self.assertIn("runners/oracle_docs_internal_publish.py", payloads)
        self.assertIn("runners/oracle_cloudflare_transport_guard.cjs", payloads)
        self.assertFalse(target.exists())
        with tempfile.TemporaryDirectory() as directory:
            for name, data in payloads.items():
                if name.endswith((".py", ".cjs")):
                    path = Path(directory) / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            run = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    "import runpy,sys;runpy.run_path(sys.argv[1],run_name='__import_only__');print('PRIVATE_INSTALLED_IMPORTS_ONLY')",
                    str(Path(directory) / "runners/oracle_docs_internal_runner.py"),
                ],
                capture_output=True,
                timeout=15,
                env={"PATH": os.defpath},
                check=False,
            )
            self.assertEqual(run.returncode, 0, run.stderr.decode())
            self.assertEqual(run.stdout, b"PRIVATE_INSTALLED_IMPORTS_ONLY\n")

    def test_native_closure_conditional_source_vendor_and_scope_changes_refused(self):
        baseline = copy.deepcopy(self.policy)
        for mutate in [
            lambda p: p["toolchain"].update(cloudflare_account_id="wrong-account"),
            lambda p: p["toolchain"].update(cli_distribution_sha256="0" * 64),
            lambda p: p["toolchain"].update(conditional_source_pins={}),
            lambda p: p["toolchain"]["native_source_pins"].pop(
                "scripts/docs/internal-native.mjs"
            ),
            lambda p: p["toolchain"].update(protected_source_bundle_sha256="not-a-pin"),
            lambda p: p["components"][
                "DruHustle/onesa-ai-platform:docs-internal"
            ].update(qualification_attempt_limit=2),
            lambda p: p["components"]["DruHustle/onesa-ai-platform:docs-internal"][
                "required_checks"
            ]["operations"].remove("backup_restore"),
            lambda p: p["components"].update(
                {
                    "DruHustle/onesa-ai-platform:docs-public": p["components"][
                        "DruHustle/onesa-ai-platform:docs-internal"
                    ]
                }
            ),
        ]:
            self.policy = copy.deepcopy(baseline)
            mutate(self.policy)
            self.seal()
            with self.subTest(policy=self.policy), self.assertRaises(owner.Rejected):
                self.validate()

    def test_candidate_changed_publisher_is_not_installed_even_if_manifest_relabelled(
        self,
    ):
        self.put("runners/oracle_docs_internal_publish.py", b"unreviewed transport")
        with self.assertRaises(owner.Rejected):
            self.validate()
        self.github.failed = True
        with self.assertRaises(owner.Rejected):
            self.validate()


if __name__ == "__main__":
    unittest.main()
