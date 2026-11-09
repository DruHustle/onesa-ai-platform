"""Real source trees and digest-bound metadata; no hosted/private publication."""

import base64
import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import free_gate
import oracle_docs_driver as driver
import oracle_docs_internal_canonical as metadata
import oracle_docs_internal_conditional as conditional
import oracle_docs_internal_runner as docs
import oracle_docs_native as native
import oracle_install as installer
import oracle_owner as owner
import test_oracle_canonical_application as application
import test_oracle_docs_canonical as public_fixture
import test_oracle_docs_internal_build as build_fixture
import test_oracle_docs_internal_install as install_fixture
from test_evidence import FINGERPRINT
from test_internal_docs_metadata import PRODUCER, DraftGitHub

SCOPE = "DruHustle/onesa-ug:platform:docs-internal"


def canonical_install(f):
    source = application.SourceFixture(owner, product="platform", branch="main")
    s = source.source
    s["product_source_tree"] = f.manifest["source_tree"]
    source.tree["tree"][0]["sha"] = s["product_source_tree"]
    for name, manifest in source.manifests.items():
        manifest["product_source_tree"] = s["product_source_tree"]
        source.repack(name)
    legacy = f.github

    def api(path):
        if (
            path
            == source.prefix + "git/trees/" + s["product_source_tree"] + "?recursive=1"
        ):
            return {**legacy.api(path), "sha": s["product_source_tree"]}
        if path.startswith(source.prefix + "git/blobs/"):
            return legacy.api(path)
        return source.api(path)

    source.github.api = api
    source.github.owner = legacy.owner
    f.github = source.github
    f.manifest.update(s)
    f.policy["schema_version"] = 2
    profile = f.policy["components"].pop("DruHustle/onesa-ai-platform:docs-internal")
    f.policy["components"] = {SCOPE: profile}
    target = installer.INSTALL_PARENT / (
        "ai-docs-internal-canonical-" + s["source_tree"]
    )
    for phase in profile["runners"].values():
        phase["path"] = str(target / "runners/oracle_docs_internal_runner.py")
    f.policy["toolchain"].update(
        source_binding=copy.deepcopy(s),
        source_tree=s["source_tree"],
        source_archives=application.pins(source),
        cli_image_security_path=str(
            docs.ROOT / "artifacts" / s["source_tree"] / "toolchain/cli-security.json"
        ),
    )
    f.policy["toolchain"]["conditional_source_pins"][
        "scripts/release/oracle_docs_internal_canonical.py"
    ] = f.manifest["files"]["runners/oracle_docs_internal_canonical.py"]
    for name, data in source.archives.items():
        f.put("source-artifacts/" + name + ".zip", base64.b64decode(data))
    f.seal()
    return source


class CanonicalPrivateInstallTests(unittest.TestCase):
    def setUp(self):
        self.f = install_fixture.PrivateInstallTests()
        application.private_fixture_setup(self.f)
        self.addCleanup(self.f.doCleanups)
        self.source = canonical_install(self.f)

    def test_real_product_tree_installs_a_separate_protected_consumer_without_authority(
        self,
    ):
        manifest, target, payloads, ci = self.f.validate()
        self.assertEqual(
            target.name, "ai-docs-internal-canonical-" + manifest["source_tree"]
        )
        self.assertNotEqual(manifest["source_tree"], manifest["product_source_tree"])
        self.assertEqual(ci[0]["source"], self.source.source)
        self.assertFalse(ci[0]["release_authorized"])
        self.assertIn("runners/oracle_docs_internal_history.py", payloads)
        self.assertIn("runners/oracle_docs_internal_canonical.py", payloads)
        self.assertFalse(target.exists())
        for name in ("signing.pem", "records.sqlite", "installation.json"):
            self.assertFalse((self.f.root / name).exists())
        store = SimpleNamespace(policy=self.f.policy)
        self.assertIs(driver.for_component(store), docs)
        with self.assertRaises(owner.Rejected):
            driver.for_component(store, "docs-public")

    def test_application_public_foreign_or_mixed_grants_cannot_install_private_docs(
        self,
    ):
        baseline = copy.deepcopy(self.f.policy)
        for scope in (
            "DruHustle/onesa-ug:platform:docs-public",
            "DruHustle/onesa-ug:platform:api",
            "DruHustle/onesa-ug:portal:docs-internal",
            "DruHustle/onesa-ai-platform:docs-internal",
        ):
            self.f.policy = copy.deepcopy(baseline)
            self.f.policy["components"] = {scope: self.f.policy["components"][SCOPE]}
            self.f.seal()
            with self.subTest(scope=scope), self.assertRaises(owner.Rejected):
                self.f.validate()
        self.f.policy = copy.deepcopy(baseline)
        self.f.policy["components"]["DruHustle/onesa-ug:platform:docs-public"] = (
            copy.deepcopy(self.f.policy["components"][SCOPE])
        )
        self.f.seal()
        with self.assertRaises(owner.Rejected):
            self.f.validate()

    def test_complete_source_private_transport_native_closure_and_first_attempt_remain_required(
        self,
    ):
        baseline = copy.deepcopy(self.f.manifest)
        for field, value in (
            ("product", "portal"),
            ("branch", "dev"),
            ("source_tree", "f" * 40),
            ("product_source_tree", "e" * 40),
            ("repository_id", True),
        ):
            self.f.manifest = {**baseline, field: value}
            self.f.seal()
            with self.subTest(field=field), self.assertRaises(owner.Rejected):
                self.f.validate()
        self.f.manifest = baseline
        self.f.policy["toolchain"]["conditional_source_pins"].pop(
            "scripts/release/oracle_docs_internal_canonical.py"
        )
        self.f.seal()
        with self.assertRaises(owner.Rejected):
            self.f.validate()


class CanonicalPrivateBuildTests(build_fixture.PrivateBuildTests):
    def setUp(self):
        super().setUp()
        source = application.SourceFixture(
            owner, product="platform", branch="main"
        ).source
        self.source.update(source)
        self.provenance["revision"] = source["candidate_commit"]

    def test_complete_source_identity_does_not_relabel_original_private_document_bodies(
        self,
    ):
        original = copy.deepcopy(self.approved)
        value = self.inspect()
        self.assertEqual(value["schema_version"], 2)
        self.assertEqual(value["source"], self.source)
        self.assertEqual(self.approved, original)
        self.assertEqual(
            value["protected_source_bundle_sha256"], owner.digest(original)
        )
        self.assertFalse(value["qualification_or_publication_authorized"])
        for key in owner.AI_SOURCE_FIELDS:
            source = self.source.pop(key)
            with self.subTest(field=key), self.assertRaises((owner.Rejected, KeyError)):
                self.inspect()
            self.source[key] = source
        self.approved["docs/engineering/DEPLOYMENT.md"]["repository"] = "onesa-ug"
        with self.assertRaises(owner.Rejected):
            self.inspect()


class CanonicalPrivateNativeTests(unittest.TestCase):
    setUpClass = classmethod(
        public_fixture.CanonicalDocsNativeTests.setUpClass.__func__
    )

    def setUp(self):
        public_fixture.CanonicalDocsNativeTests.setUp(self)
        f = self.f
        f.store.db.close()
        profile = f.policy["components"].pop(public_fixture.SCOPE)
        profile["publication_mechanism"] = (
            "existing-isolated-owner-cloudflare-pages-cli"
        )
        f.policy["components"] = {SCOPE: profile}
        f.binding["component"] = "docs-internal"
        (f.root / "policy.json").write_bytes(owner.canonical(f.policy))
        trust = json.loads((f.root / "trust.json").read_bytes())
        trust["policy_sha256"] = owner.file_digest(f.root / "policy.json")
        (f.root / "trust.json").write_bytes(owner.canonical(trust))
        f.commission_fixture()
        f.store = f.open()
        self.addCleanup(f.store.db.close)
        # Only the actual browser/provider observation is a disposable stand-in;
        # commissioning, possession, signatures, source CI and records are real.
        substitute = sys.modules["oracle_docs_runner"]
        for name in (
            "preview_for_binding",
            "target_for_observation",
            "validate_native",
        ):
            self.enterContext(patch.object(docs, name, getattr(substitute, name)))

    def test_private_native_chain_requires_separate_commission_and_consumes_its_context_once(
        self,
    ):
        self.f.test_valid_zero_run_native_receipt_is_not_authorization_and_context_consumes_once()
        self.assertEqual(
            self.f.store.db.execute("SELECT DISTINCT scope FROM records").fetchall(),
            [(SCOPE,)],
        )
        self.assertEqual(
            self.f.store.db.execute("SELECT count(*) FROM deployments").fetchone()[0], 0
        )

    def test_public_app_foreign_product_and_relabelled_root_cannot_borrow_private_native_grants(
        self,
    ):
        f = self.f
        registered, _context, challenge = f.session()
        for field, value in (
            ("component", "docs-public"),
            ("component", "api"),
            ("product", "portal"),
            ("source_tree", "d" * 40),
            ("product_source_tree", "e" * 40),
            ("repository_id", True),
        ):
            with (
                self.subTest(field=field, value=value),
                self.assertRaises(owner.Rejected),
            ):
                native.import_observation(
                    f.store,
                    owner.canonical(
                        f.envelope(
                            registered, challenge, binding={**f.binding, field: value}
                        )
                    ),
                )
        self.assertEqual(
            f.store.db.execute(
                "SELECT count(*) FROM records WHERE kind=?", (native.OBSERVATION,)
            ).fetchone()[0],
            0,
        )

    def test_changed_main_after_private_authorization_cannot_create_a_provider_request(
        self,
    ):
        public_fixture.CanonicalDocsNativeTests.test_changed_main_after_authorization_blocks_provider_creation(
            self
        )


class CanonicalExternalCheckoutTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(
            dir=Path.home() if os.getuid() == 0 else None
        )
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.root.chmod(0o700)
        self.enterContext(patch.object(conditional, "ROOT", self.root))
        checkout = self.root / "unmoved"
        product = checkout / "onesa-ai-platform"
        product.mkdir(mode=0o700, parents=True)
        current = Path(__file__).resolve().parents[2]
        names = conditional.FILES | {
            "scripts/release/oracle_docs_internal_canonical.py"
        }
        for name in names:
            path = product / name
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.write_bytes((current / name).read_bytes())
            path.chmod(0o600)
        (checkout / "README.md").write_text("Synthetic canonical root\n")
        (checkout / ".gitignore").write_text("__pycache__/\n")
        subprocess.run(
            ["git", "init", "--quiet", str(checkout)], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(checkout), "add", "."], check=True, capture_output=True
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(checkout),
                "-c",
                "user.name=Disposable fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "Synthetic canonical conditional source",
            ],
            check=True,
            capture_output=True,
        )

        def git(ref):
            return subprocess.check_output(
                ["git", "-C", str(checkout), "rev-parse", ref], text=True
            ).strip()

        source = application.SourceFixture(
            owner, product="platform", branch="main"
        ).source
        source.update(
            candidate_commit=git("HEAD"),
            source_tree=git("HEAD^{tree}"),
            product_source_tree=git("HEAD:onesa-ai-platform"),
        )
        target = self.root / "checkouts" / source["candidate_commit"]
        target.parent.mkdir(mode=0o700)
        checkout.rename(target)
        self.checkout = target / "onesa-ai-platform"
        self.source = source
        self.binding = {**source, "component": "docs-internal"}
        self.calls = []

        def api(path):
            self.calls.append(path)
            return {
                "id": owner.CONSOLIDATED_REPOSITORY_ID,
                "full_name": owner.CONSOLIDATED_REPOSITORY,
            }

        self.store = SimpleNamespace(
            github=SimpleNamespace(api=api),
            policy={
                "toolchain": {
                    "conditional_source_pins": {
                        name: owner.file_digest(self.checkout / name) for name in names
                    }
                }
            },
        )
        private = owner.private
        self.enterContext(
            patch.object(
                owner,
                "private",
                side_effect=lambda path, **kw: private(
                    path, **{"uid": os.getuid(), **kw}
                ),
            )
        )

    def test_complete_clean_root_and_subtree_load_and_fixed_repository_identity_read(
        self,
    ):
        self.assertNotEqual(
            self.source["source_tree"], self.source["product_source_tree"]
        )
        self.assertEqual(
            conditional.checked_checkout(self.store, self.binding), self.checkout
        )
        gate, github = conditional.load(self.store, self.binding)
        self.assertEqual(gate.e.ROOT, self.checkout)
        # The source verifier reads the actual numeric repository identity at
        # this endpoint, not just paths below the repository prefix.
        self.assertEqual(
            github.api(metadata.PREFIX.rstrip("/"))["id"],
            owner.CONSOLIDATED_REPOSITORY_ID,
        )
        for path in (
            "repos/DruHustle/onesa-ai-platform",
            "repos/DruHustle/onesa-ug-foreign",
            "repos/DruHustle/onesa-ug/../other",
            "https://foreign.invalid",
        ):
            with self.subTest(path=path), self.assertRaises(owner.Rejected):
                github.api(path)
        self.assertEqual(len(self.calls), 1)

    def test_changed_product_tree_external_root_or_conditional_helper_is_refused(self):
        with self.assertRaises(owner.Rejected):
            conditional.checked_checkout(
                self.store, {**self.binding, "product_source_tree": "f" * 40}
            )
        root_file = self.checkout.parent / "README.md"
        root_file.write_text("changed root outside the product\n")
        with self.assertRaises(owner.Rejected):
            conditional.checked_checkout(self.store, self.binding)
        root_file.write_text("Synthetic canonical root\n")
        helper = self.checkout / "scripts/release/oracle_docs_internal_canonical.py"
        helper.write_bytes(helper.read_bytes() + b"\n# changed\n")
        with self.assertRaises(owner.Rejected):
            conditional.checked_checkout(self.store, self.binding)

    def test_hosted_metadata_binds_actual_root_product_main_and_workflow_bytes(self):
        gate, _github = conditional.load(self.store, self.binding)
        sha = self.source["candidate_commit"]
        environment = {
            "GITHUB_ACTIONS": "true",
            "RUNNER_ENVIRONMENT": "github-hosted",
            "RUNNER_OS": "Linux",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REPOSITORY": owner.CONSOLIDATED_REPOSITORY,
            "GITHUB_REPOSITORY_ID": str(owner.CONSOLIDATED_REPOSITORY_ID),
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_ACTOR": owner.OWNER,
            "GITHUB_TRIGGERING_ACTOR": owner.OWNER,
            "GITHUB_SHA": sha,
            "GITHUB_WORKFLOW_SHA": sha,
            "GITHUB_WORKFLOW_REF": owner.CONSOLIDATED_REPOSITORY
            + "/"
            + metadata.WORKFLOW_PATH
            + "@refs/heads/main",
        }
        self.assertEqual(metadata.action_source(environment, gate), self.source)
        for key, value in (
            ("GITHUB_WORKFLOW_SHA", "f" * 40),
            ("GITHUB_RUN_ATTEMPT", "2"),
            ("GITHUB_ACTOR", "other"),
            ("GITHUB_REF", "refs/heads/dev"),
            ("GITHUB_REPOSITORY_ID", "1"),
        ):
            with self.subTest(field=key), self.assertRaises(owner.Rejected):
                metadata.action_source({**environment, key: value}, gate)


class CanonicalMetadataTests(unittest.TestCase):
    def setUp(self):
        self.fixture = application.SourceFixture(
            owner, product="platform", branch="main"
        )
        self.source, self.source_archives = self.fixture.source, self.fixture.archives
        self.calls, self.binary, self.artifacts = [], {}, {}
        repo = {
            "full_name": self.source["repository"],
            "id": self.source["repository_id"],
        }
        self.runs = {}
        for identifier, minutes in ((701, 4), (702, 2)):
            created = self.fixture.now - timedelta(minutes=minutes)
            self.runs[identifier] = {
                "id": identifier,
                "repository": repo,
                "head_repository": repo,
                "head_sha": self.source["candidate_commit"],
                "head_branch": "main",
                "event": "workflow_dispatch",
                "path": metadata.WORKFLOW_PATH,
                "run_attempt": 1,
                "actor": {"login": owner.OWNER},
                "triggering_actor": {"login": owner.OWNER},
                "status": "completed",
                "conclusion": "success",
                "created_at": created.isoformat(),
                "updated_at": (created + timedelta(seconds=20)).isoformat(),
            }
        self.github = SimpleNamespace(api=self.api)
        self.native = DraftGitHub().metadata
        self.native.update(
            schema_version=3,
            repository=self.source["repository"],
            candidate_commit=self.source["candidate_commit"],
            source=copy.deepcopy(self.source),
            ci_run_id=self.fixture.run["id"],
        )
        self.native["staging"]["source_commit"] = self.source["candidate_commit"]
        self.enterContext(
            patch.object(
                free_gate, "_internal_docs_local_source", return_value=FINGERPRINT
            )
        )
        self.qualified = metadata.qualification(
            self.github,
            self.source,
            self.source_archives,
            self.runs[701],
            self.native,
            PRODUCER,
            free_gate,
        )
        self.pack(701, self.qualified)
        self.approved = metadata.decision(
            self.github,
            self.source,
            self.source_archives,
            self.runs[702],
            "approve",
            701,
            owner.digest(self.qualified),
            self.read_archive,
            free_gate,
        )
        self.pack(702, self.approved)

    def api(self, path):
        self.calls.append(path)
        if (
            path
            == metadata.PREFIX
            + "actions/workflows/"
            + metadata.WORKFLOW
            + "/runs?head_sha="
            + self.source["candidate_commit"]
            + "&per_page=100"
        ):
            return {
                "total_count": len(self.runs),
                "workflow_runs": copy.deepcopy(list(self.runs.values())),
            }
        for identifier, run in self.runs.items():
            prefix = metadata.PREFIX + "actions/runs/" + str(identifier)
            if path == prefix:
                return copy.deepcopy(run)
            if path == prefix + "/jobs?filter=latest&per_page=100":
                return {
                    "total_count": 1,
                    "jobs": [
                        {
                            "id": identifier + 1000,
                            "name": metadata.JOB,
                            "run_id": identifier,
                            "head_sha": self.source["candidate_commit"],
                            "run_attempt": 1,
                            "status": "completed",
                            "conclusion": "success",
                            "steps": [
                                {
                                    "name": name,
                                    "status": "completed",
                                    "conclusion": "success",
                                }
                                for name in (
                                    "Verify hosted execution, visibility and included-allowance policy",
                                    metadata.STEP,
                                    metadata.UPLOAD,
                                )
                            ],
                        }
                    ],
                }
            if path == prefix + "/artifacts?per_page=100":
                return {
                    "total_count": 1,
                    "artifacts": [copy.deepcopy(self.artifacts[identifier + 100])],
                }
        for identifier, value in self.artifacts.items():
            if path == metadata.PREFIX + "actions/artifacts/" + str(identifier):
                return copy.deepcopy(value)
        return self.fixture.api(path)

    def pack(self, run_id, value):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("record.json", owner.canonical(value))
        raw, identifier = output.getvalue(), run_id + 100
        self.binary[identifier] = raw
        self.artifacts[identifier] = {
            "id": identifier,
            "name": metadata.ARTIFACT,
            "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "size_in_bytes": len(raw),
            "expired": False,
            "workflow_run": {
                "id": run_id,
                "repository_id": self.source["repository_id"],
                "head_repository_id": self.source["repository_id"],
                "head_branch": "main",
                "head_sha": self.source["candidate_commit"],
            },
        }

    def read_archive(self, identifier):
        return self.binary[identifier]

    def verify(self):
        return metadata.verify(
            self.github,
            self.source,
            self.source_archives,
            702,
            self.native,
            PRODUCER,
            self.read_archive,
            free_gate,
        )

    def test_genuine_complete_source_and_actual_artifact_chain_remains_conditional(
        self,
    ):
        result = self.verify()
        self.assertEqual(result["authorization_run_id"], 702)
        self.assertEqual(result["qualification_run_id"], 701)
        self.assertFalse(result["production_deployment_authorized"])
        self.assertEqual(result["metadata_sha256"], owner.digest(self.native))
        for value in (self.qualified, self.approved):
            self.assertEqual(value["STAGING_VERIFIED"], "BLOCKED")
            self.assertIs(value["production_deployment_authorized"], False)
            self.assertIs(value["application_deployment_authorized"], False)
            self.assertIs(value["backend_deployment_authorized"], False)
        self.assertTrue(
            all(
                path == metadata.PREFIX.rstrip("/") or path.startswith(metadata.PREFIX)
                for path in self.calls
            )
        )
        self.assertFalse(
            any("/releases/" in path or "/deployments" in path for path in self.calls)
        )

    def test_public_application_foreign_or_forged_native_metadata_cannot_borrow_scope(
        self,
    ):
        for field, value in (
            ("delivery_scope", "docs-public"),
            ("production_deployment_authorized", True),
            ("schema_version", 2),
            ("repository", "DruHustle/onesa-ai-platform"),
            ("ci_run_id", self.fixture.run["id"] + 1),
        ):
            altered = {**self.native, field: value}
            with (
                self.subTest(field=field),
                self.assertRaises((owner.Rejected, free_gate.e.Rejected)),
            ):
                metadata.qualification(
                    self.github,
                    self.source,
                    self.source_archives,
                    self.runs[701],
                    altered,
                    PRODUCER,
                    free_gate,
                )
        for field, value in (
            ("product", "portal"),
            ("source_path", "onesa-company-portal"),
            ("source_tree", "f" * 40),
            ("product_source_tree", "e" * 40),
        ):
            altered = {**self.source, field: value}
            with self.subTest(source=field), self.assertRaises(owner.Rejected):
                metadata.qualification(
                    self.github,
                    altered,
                    self.source_archives,
                    self.runs[701],
                    self.native,
                    PRODUCER,
                    free_gate,
                )

    def test_revocation_newer_qualification_or_failed_first_attempt_blocks_handoff(
        self,
    ):
        for decision in ("revoke", "qualify"):
            self.approved["decision"] = decision
            self.pack(702, self.approved)
            with self.subTest(decision=decision), self.assertRaises(owner.Rejected):
                self.verify()
        self.approved["decision"] = "approve"
        self.pack(702, self.approved)
        self.runs[702]["run_attempt"] = 2
        with self.assertRaises(owner.Rejected):
            self.verify()
        self.runs[702]["run_attempt"] = 1
        self.fixture.jobs["jobs"][0]["conclusion"] = "skipped"
        with self.assertRaises(owner.Rejected):
            self.verify()

    def test_exact_archive_producer_and_latest_record_are_rechecked(self):
        original = self.binary[802]
        self.binary[802] += b"altered"
        with self.assertRaises(owner.Rejected):
            self.verify()
        self.binary[802] = original
        with self.assertRaises(owner.Rejected):
            metadata.verify(
                self.github,
                self.source,
                self.source_archives,
                702,
                self.native,
                "f" * 64,
                self.read_archive,
                free_gate,
            )
        self.runs[703] = {
            **self.runs[702],
            "id": 703,
            "created_at": (self.fixture.now - timedelta(seconds=30)).isoformat(),
            "updated_at": (self.fixture.now - timedelta(seconds=10)).isoformat(),
        }
        self.pack(703, self.qualified)
        with self.assertRaises(owner.Rejected):
            self.verify()


if __name__ == "__main__":
    unittest.main()
