"""Docs uses the existing exact-source installer; fixtures grant no trust."""

import copy
import unittest

import oracle_owner as owner
import test_oracle_install as fixtures


class DocsInstallTests(unittest.TestCase):
    DOCS = True
    setUp = fixtures.InstallTests.setUp
    put = fixtures.InstallTests.put
    seal = fixtures.InstallTests.seal
    validate = fixtures.InstallTests.validate

    def test_exact_docs_source_installs_separately_without_commissioning(self):
        _manifest, target, payloads, _ci = self.validate()
        self.assertEqual(target.name, "ai-docs-" + self.manifest["source_tree"])
        self.assertIn("oracle_docs_owner.py", payloads)
        self.assertIn("runners/oracle_docs_runner.py", payloads)
        self.assertFalse(target.exists())

    def test_caller_source_pin_or_expanded_runtime_or_producer_pin_cannot_replace_closure(
        self,
    ):
        baseline = copy.deepcopy(self.policy)
        for field, value in [
            (
                "native_source_pins",
                {
                    **baseline["toolchain"]["native_source_pins"],
                    "unreviewed.py": "a" * 64,
                },
            ),
            (
                "native_runtime_pins",
                {
                    **baseline["toolchain"]["native_runtime_pins"],
                    "unreviewed_runtime": "b" * 64,
                },
            ),
            ("native_producer_sha256", "c" * 64),
            ("source_tree", "d" * 40),
            ("transport_guard_sha256", "e" * 64),
        ]:
            with self.subTest(field=field):
                self.policy = copy.deepcopy(baseline)
                self.policy["toolchain"][field] = value
                self.seal()
                with self.assertRaises(owner.Rejected):
                    self.validate()

    def test_application_profile_or_renewed_context_cannot_be_smuggled_into_docs_installation(
        self,
    ):
        baseline = copy.deepcopy(self.policy)
        key = "DruHustle/onesa-ai-platform:docs-public"
        for mutate in [
            lambda p: p["components"].update(
                {"DruHustle/onesa-ai-platform:frontend": p["components"][key]}
            ),
            lambda p: p["components"][key].update(qualification_attempt_limit=2),
            lambda p: p["components"][key].update(
                publication_mechanism="caller-supplied-json"
            ),
            lambda p: p["components"][key]["required_checks"]["operations"].remove(
                "backup_restore"
            ),
        ]:
            self.policy = copy.deepcopy(baseline)
            mutate(self.policy)
            self.seal()
            with self.assertRaises(owner.Rejected):
                self.validate()

    def test_changed_installer_or_failed_current_ci_fails_before_installation(self):
        self.github.failed = True
        with self.assertRaises(owner.Rejected):
            self.validate()
        self.github.failed = False
        self.put("oracle_docs_owner.py", b"unreviewed owner adapter")
        with self.assertRaises(owner.Rejected):
            self.validate()


if __name__ == "__main__":
    unittest.main()
