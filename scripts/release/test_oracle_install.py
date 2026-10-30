"""Disposable installer provenance tests; these fixtures confer no trust."""

import base64
import copy
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import oracle_ai_runner as runner
import oracle_install as installer
import oracle_owner as verifier


class Source:
    def __init__(self, files):
        self.files = files
        self.failed = False
        self.truncated = False
        self.mode = "100644"

    def owner(self):
        return verifier.OWNER

    def qualify(self, binding):
        verifier.require(not self.failed, "Real CI fixture failed")
        return [{"run_id": 123, "run_attempt": 1}]

    def api(self, path):
        if "/git/trees/" in path:
            return {
                "truncated": self.truncated,
                "tree": [
                    {
                        "type": "blob",
                        "mode": self.mode,
                        "path": name,
                        "sha": hashlib.sha1(data).hexdigest(),
                    }
                    for name, data in self.files.items()
                ],
            }
        data = next(
            data
            for data in self.files.values()
            if hashlib.sha1(data).hexdigest() == path.rsplit("/", 1)[1]
        )
        return {"encoding": "base64", "content": base64.b64encode(data).decode()}


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            dir=Path.home()
            if os.getuid() == 0
            else "/private/tmp"
            if Path("/private/tmp").exists()
            else None
        )
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.root.chmod(0o700)
        self.manifest = {
            "schema_version": 1,
            "repository": "DruHustle/onesa-ai-platform",
            "candidate_commit": "a" * 40,
            "source_tree": "",
            "files": {},
            "policy_sha256": "",
            "tool_source_sha256": "",
        }
        files = {}
        source_root = self.root / "synthetic-source"
        source_root.mkdir(mode=0o700)
        repo = Path(__file__).resolve().parents[2]
        is_private_docs = getattr(self, "PRIVATE_DOCS", False)
        is_docs = is_private_docs or getattr(self, "DOCS", False)
        for local, source in (
            installer.PRIVATE_DOCS_ALLOWED
            if is_private_docs
            else installer.DOCS_ALLOWED
            if is_docs
            else installer.ALLOWED
        ).items():
            data = (repo / source).read_bytes()
            files[source] = data
            self.put(local, data)
            self.manifest["files"][local] = hashlib.sha256(data).hexdigest()
        files["onesa-ai-platform-backend/app/twin_files.py"] = (
            b"# synthetic source parser fixture only\n"
        )
        for resource in runner.PROBE_RESOURCE_FILES:
            files[resource] = (repo / resource).read_bytes()
        if is_docs:
            import oracle_docs_contract as contract

            for resource in contract.source_closure(
                "docs-internal" if is_private_docs else "docs-public"
            ):
                files[resource] = (repo / resource).read_bytes()
        if is_private_docs:
            for name in [
                "scripts/release/free_gate.py",
                "scripts/release/evidence.py",
                "scripts/release/qualify.py",
                "infra/oracle/cloudflare-tools/upstream.json",
            ]:
                files[name] = (repo / name).read_bytes()
        for name, data in files.items():
            path = source_root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        subprocess.run(
            ["git", "init", "--quiet", str(source_root)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(source_root), "add", "."], check=True, capture_output=True
        )
        tree = subprocess.check_output(
            ["git", "-C", str(source_root), "write-tree"], text=True
        ).strip()
        self.manifest["source_tree"] = tree
        archive = subprocess.check_output(
            ["git", "-C", str(source_root), "archive", tree]
        )
        self.put("tool-source.tar", archive)
        self.manifest["tool_source_sha256"] = hashlib.sha256(archive).hexdigest()
        self.github = Source(files)
        target = installer.INSTALL_PARENT / ("ai-" + tree)
        self.policy = {
            "schema_version": 1,
            "components": {},
            "toolchain": {
                "source_commit": "a" * 40,
                "source_tree": tree,
                "source_sha256": self.manifest["tool_source_sha256"],
                "probe_image": "sha256:" + "1" * 64,
                "cli_image": "sha256:" + "2" * 64,
                "builder_image": "sha256:" + "3" * 64,
                "builder_sha256": self.manifest["files"][
                    "runners/oracle_frontend_build.py"
                ],
                "transport_guard_sha256": self.manifest["files"][
                    "runners/oracle_vercel_transport_guard.cjs"
                ],
                "probe_files": runner.probe_source_files(
                    {
                        name: hashlib.sha256(data).hexdigest()
                        for name, data in files.items()
                    }
                ),
            },
        }
        for component, script in [
            ("api", "oracle_ai_runner.py"),
            ("frontend", "oracle_ai_frontend.py"),
        ]:
            self.policy["components"]["DruHustle/onesa-ai-platform:" + component] = {
                "qualification_attempt_limit": 1,
                "runners": {
                    phase: {
                        "path": str(target / "runners" / script),
                        "sha256": self.manifest["files"]["runners/" + script],
                        "timeout_seconds": 1800,
                    }
                    for phase in verifier.PHASES
                },
                "required_checks": {
                    phase: sorted(verifier.REQUIRED_CHECKS[phase])
                    for phase in verifier.PHASES
                },
            }
        if is_docs:
            import oracle_docs_contract as contract

            runtime = {
                "node": "4" * 64,
                "openssl": "5" * 64,
                "browser_packages": "6" * 64,
            }
            native_files = {
                name: hashlib.sha256(files[name]).hexdigest()
                for name in contract.SOURCE_CLOSURE
            }
            self.policy["toolchain"] = {
                "source_commit": "a" * 40,
                "source_tree": tree,
                "source_sha256": self.manifest["tool_source_sha256"],
                "cli_image": "sha256:" + "2" * 64,
                "cli_image_security_path": "/var/lib/onesa/release-verification/ai-docs/artifacts/"
                + tree
                + "/toolchain/cli-security.json",
                "transport_guard_sha256": self.manifest["files"][
                    "runners/oracle_vercel_transport_guard.cjs"
                ],
                "docs_project_id": "prj_fixture",
                "vercel_team_id": "team_fixture",
                "native_source_pins": native_files,
                "native_runtime_pins": runtime,
                "native_producer_sha256": contract.producer_digest(
                    native_files, runtime
                ),
            }
            self.policy["components"] = {
                "DruHustle/onesa-ai-platform:docs-public": {
                    "qualification_attempt_limit": 1,
                    "publication_mechanism": "existing-isolated-owner-vercel-cli",
                    "runners": {
                        phase: {
                            "path": str(
                                installer.INSTALL_PARENT
                                / ("ai-docs-" + tree)
                                / "runners/oracle_docs_runner.py"
                            ),
                            "sha256": self.manifest["files"][
                                "runners/oracle_docs_runner.py"
                            ],
                            "timeout_seconds": 1800,
                        }
                        for phase in verifier.PHASES
                    },
                    "required_checks": {
                        phase: sorted(verifier.REQUIRED_CHECKS[phase])
                        for phase in verifier.PHASES
                    },
                }
            }
        if is_private_docs:
            import oracle_docs_contract as contract

            closure = {
                name: hashlib.sha256(files[name]).hexdigest()
                for name in contract.source_closure("docs-internal")
            }
            tool = self.policy["toolchain"]
            tool.pop("vercel_team_id")
            tool.update(
                cli_image_security_path="/var/lib/onesa/release-verification/ai-docs-internal/artifacts/"
                + tree
                + "/toolchain/cli-security.json",
                cli_distribution_sha256="95783b16eadfa64161f0fd7c453f3c424a21c855c9afc445ea4a5703c6b512fe",
                docs_project_id="11111111-1111-4111-8111-111111111111",
                cloudflare_account_id="1" * 32,
                protected_source_bundle_sha256="7" * 64,
                conditional_source_pins={
                    name: hashlib.sha256(files[name]).hexdigest()
                    for name in [
                        "scripts/release/free_gate.py",
                        "scripts/release/evidence.py",
                        "scripts/release/qualify.py",
                    ]
                },
                native_source_pins=closure,
                native_producer_sha256=contract.producer_digest(
                    closure, runtime, component="docs-internal"
                ),
                transport_guard_sha256=self.manifest["files"][
                    "runners/oracle_cloudflare_transport_guard.cjs"
                ],
            )
            profile = self.policy["components"].pop(
                "DruHustle/onesa-ai-platform:docs-public"
            )
            profile["publication_mechanism"] = (
                "existing-isolated-owner-cloudflare-pages-cli"
            )
            for phase in verifier.PHASES:
                profile["runners"][phase].update(
                    path=str(
                        installer.INSTALL_PARENT
                        / ("ai-docs-internal-" + tree)
                        / "runners/oracle_docs_internal_runner.py"
                    ),
                    sha256=self.manifest["files"][
                        "runners/oracle_docs_internal_runner.py"
                    ],
                )
            self.policy["components"]["DruHustle/onesa-ai-platform:docs-internal"] = (
                profile
            )
        self.seal()

    def put(self, name, data):
        p = self.root / name
        p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        p.write_bytes(data)
        p.chmod(0o600)

    def seal(self):
        data = verifier.canonical(self.policy)
        self.put("policy.json", data)
        self.manifest["policy_sha256"] = hashlib.sha256(data).hexdigest()
        data = verifier.canonical(self.manifest)
        self.put("manifest.json", data)
        self.pin = hashlib.sha256(data).hexdigest()

    def validate(self):
        return installer.validate(self.root, self.pin, self.github, uid=os.getuid())

    @unittest.skipUnless(os.getuid() == 0, "Root custody ancestor policy")
    def test_shared_writable_parent_still_refused(self):
        shared = self.root / "shared-parent"
        shared.mkdir(mode=0o700)
        shared.chmod(0o777)
        child = shared / "custody"
        child.mkdir(mode=0o700)
        with self.assertRaisesRegex(verifier.Rejected, "ancestors"):
            verifier.private(child, directory=True, uid=0)

    def test_exact_main_bytes_and_complete_policy(self):
        m, _target, files, ci = self.validate()
        self.assertEqual(m, self.manifest)
        self.assertEqual(ci[0]["run_id"], 123)
        self.assertIn("policy.json", files)

    def test_tamper_wrong_pin_and_unreviewed_blob(self):
        self.put("oracle_owner.py", b"candidate replacement")
        with self.assertRaises(verifier.Rejected):
            self.validate()
        self.manifest["files"]["oracle_owner.py"] = hashlib.sha256(
            b"candidate replacement"
        ).hexdigest()
        self.seal()
        with self.assertRaises(verifier.Rejected):
            self.validate()

    def test_ci_tree_and_source_type_fail_closed(self):
        for field, value in [("failed", True), ("truncated", True), ("mode", "120000")]:
            original = getattr(self.github, field)
            setattr(self.github, field, value)
            with self.subTest(field=field), self.assertRaises(verifier.Rejected):
                self.validate()
            setattr(self.github, field, original)

    def test_incomplete_policy_and_extra_component_refused(self):
        self.policy["components"]["DruHustle/onesa-ai-platform:api"]["required_checks"][
            "staging"
        ].remove("persistence")
        self.seal()
        with self.assertRaises(verifier.Rejected):
            self.validate()

    def scoped_policy(self):
        for kind in ["api", "frontend"]:
            original = self.policy["components"]["DruHustle/onesa-ai-platform:" + kind]
            for mode in ["foundation", "twins", "cybersecurity"]:
                component = kind if mode == "foundation" else mode + "-" + kind
                profile = copy.deepcopy(original)
                profile["release_mode"] = mode
                self.policy["components"][
                    "DruHustle/onesa-ai-platform:" + component
                ] = profile

    def test_six_literal_modes_install_the_same_pinned_runners_with_one_context_each(
        self,
    ):
        self.scoped_policy()
        self.seal()
        result = self.validate()
        self.assertEqual(result[1].name, "ai-" + self.manifest["source_tree"])
        self.assertIn("runners/oracle_release_profiles.py", result[2])

    def test_scoped_mode_changes_missing_profiles_and_expanded_attempts_are_refused(
        self,
    ):
        self.scoped_policy()
        baseline = copy.deepcopy(self.policy)
        for change in ["wrong-mode", "missing", "extra", "two-attempts"]:
            self.policy = copy.deepcopy(baseline)
            key = "DruHustle/onesa-ai-platform:twins-api"
            if change == "wrong-mode":
                self.policy["components"][key]["release_mode"] = "cybersecurity"
            elif change == "missing":
                del self.policy["components"][key]
            elif change == "extra":
                self.policy["components"]["DruHustle/onesa-ai-platform:other-api"] = (
                    copy.deepcopy(self.policy["components"][key])
                )
            else:
                self.policy["components"][key]["qualification_attempt_limit"] = 2
            self.seal()
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate()

    def test_alias_and_mode_refused(self):
        p = self.root / "oracle_owner.py"
        data = p.read_bytes()
        p.unlink()
        other = self.root / "other"
        other.write_bytes(data)
        other.chmod(0o600)
        p.symlink_to(other)
        with self.assertRaises(verifier.Rejected):
            self.validate()

    def test_dry_run_performs_no_install_or_authority_write(self):
        with patch.object(installer, "INSTALL_PARENT", self.root / "not-created"):
            # Regenerate paths in the checked policy for this disposable location.
            for component, script in [
                ("api", "oracle_ai_runner.py"),
                ("frontend", "oracle_ai_frontend.py"),
            ]:
                for r in self.policy["components"][
                    "DruHustle/onesa-ai-platform:" + component
                ]["runners"].values():
                    r["path"] = str(
                        installer.INSTALL_PARENT
                        / ("ai-" + self.manifest["source_tree"])
                        / "runners"
                        / script
                    )
            self.seal()
            result = installer.install(
                self.root, self.pin, self.github, dry_run=True, uid=os.getuid()
            )
            self.assertEqual(result["state"], "INSTALLATION_READY")
            self.assertFalse(installer.INSTALL_PARENT.exists())


class IsolatedInstallerEntryTests(unittest.TestCase):
    def test_isolated_python_resolves_the_bundled_verifier(self):
        result = subprocess.run(
            [sys.executable, "-I", str(Path(installer.__file__)), "--help"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(b"--manifest-pin", result.stdout)
