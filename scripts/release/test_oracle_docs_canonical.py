"""Disposable canonical public Docs contracts, never installed/live acceptance."""

import base64
import copy
import hashlib
import json
import subprocess
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import oracle_ai_runner as parser
import oracle_docs_contract as contract
import oracle_docs_driver as driver
import oracle_docs_native as native
import oracle_docs_owner as docs_owner
import oracle_docs_runner as docs
import oracle_install as installer
import oracle_owner as owner
import oracle_release_profiles as profiles
import test_oracle_canonical_application as application
import test_oracle_docs_install as install_fixture
import test_oracle_docs_internal_install as private_install_fixture
import test_oracle_docs_native as native_fixture
import test_oracle_docs_runner as runner_fixture

SourceFixture = application.SourceFixture
SCOPE = "DruHustle/onesa-ug:platform:docs-public"


def canonical_install(f):
    """Real product Git/tar bytes, synthetic read-only GitHub protocol responses."""
    source = SourceFixture(owner, product="platform", branch="main")
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
    profile = f.policy["components"].pop("DruHustle/onesa-ai-platform:docs-public")
    f.policy["components"] = {SCOPE: profile}
    target = installer.INSTALL_PARENT / ("ai-docs-canonical-" + s["source_tree"])
    for phase in profile["runners"].values():
        phase["path"] = str(target / "runners/oracle_docs_runner.py")
    f.policy["toolchain"].update(
        source_binding=copy.deepcopy(s),
        source_tree=s["source_tree"],
        source_archives=application.pins(source),
        cli_image_security_path=str(
            docs.ROOT / "artifacts" / s["source_tree"] / "toolchain/cli-security.json"
        ),
    )
    for name, data in source.archives.items():
        f.put("source-artifacts/" + name + ".zip", base64.b64decode(data))
    f.seal()
    return source


class CanonicalDocsInstallTests(unittest.TestCase):
    def setUp(self):
        self.f = f = install_fixture.DocsInstallTests()
        application.private_fixture_setup(f)
        self.addCleanup(f.doCleanups)
        self.source = canonical_install(f)

    def test_real_product_archive_installs_only_explicit_public_scope_without_commissioning(
        self,
    ):
        manifest, target, payloads, ci = self.f.validate()
        self.assertEqual(target.name, "ai-docs-canonical-" + manifest["source_tree"])
        self.assertNotEqual(manifest["source_tree"], manifest["product_source_tree"])
        self.assertEqual(ci[0]["source"], self.source.source)
        self.assertTrue(ci[0]["verification_only"])
        self.assertFalse(ci[0]["release_authorized"])
        self.assertEqual(
            set(payloads) - set(installer.DOCS_ALLOWED),
            {
                "policy.json",
                "tool-source.tar",
                *("source-artifacts/" + name + ".zip" for name in self.source.archives),
            },
        )
        self.assertFalse(target.exists())
        self.assertFalse((self.f.root / "records.sqlite").exists())
        self.assertFalse((self.f.root / "signing.pem").exists())

    def test_source_only_policy_and_application_or_protected_profiles_cannot_borrow_docs(
        self,
    ):
        baseline = copy.deepcopy(self.f.policy)
        for change in ("source-only", "mixed", "application", "protected", "schema1"):
            self.f.policy = copy.deepcopy(baseline)
            if change == "source-only":
                self.f.policy = copy.deepcopy(self.source.policy)
            elif change == "mixed":
                self.f.policy["components"]["DruHustle/onesa-ug:platform:api"] = (
                    copy.deepcopy(baseline["components"][SCOPE])
                )
            elif change in {"application", "protected"}:
                name = "api" if change == "application" else "docs-internal"
                self.f.policy["components"] = {
                    "DruHustle/onesa-ug:platform:" + name: baseline["components"][SCOPE]
                }
            else:
                self.f.policy["schema_version"] = 1
            self.f.seal()
            with self.subTest(change=change), self.assertRaises(owner.Rejected):
                self.f.validate()

    def test_complete_canonical_identity_and_installed_artifacts_are_required(self):
        original = copy.deepcopy(self.f.manifest)
        for field, value in (
            ("repository_id", 1),
            ("repository_id", True),
            ("product", "portal"),
            ("source_path", "onesa-robot"),
            ("branch", "staging"),
            ("source_tree", "f" * 40),
            ("product_source_tree", "e" * 40),
            ("repository", "DruHustle/onesa-ai-platform"),
        ):
            self.f.manifest = {**original, field: value}
            self.f.seal()
            with (
                self.subTest(field=field, value=value),
                self.assertRaises(owner.Rejected),
            ):
                self.f.validate()
        self.f.manifest = original
        self.f.seal()
        archive = next((self.f.root / "source-artifacts").glob("*.zip"))
        raw = archive.read_bytes()
        archive.unlink()
        with self.assertRaises(FileNotFoundError):
            self.f.validate()
        archive.write_bytes(raw + b"changed")
        archive.chmod(0o600)
        with self.assertRaises(owner.Rejected):
            self.f.validate()

    def test_legacy_application_installer_cannot_borrow_public_docs_policy(self):
        app = application.CanonicalInstallTests()
        app.setUp()
        self.addCleanup(app.doCleanups)
        template = copy.deepcopy(self.f.policy["components"][SCOPE])
        app.fixture.policy["components"] = {SCOPE: template}
        app.fixture.seal()
        with self.assertRaises(owner.Rejected):
            app.fixture.validate()
        with self.assertRaises(profiles.ProfileError):
            profiles.validate_mode(
                {**self.source.source, "component": "docs-public"},
                "foundation",
                app.fixture.policy,
            )

    def test_canonical_protected_installer_cannot_relabel_a_legacy_policy(self):
        private = private_install_fixture.PrivateInstallTests()
        application.private_fixture_setup(private)
        self.addCleanup(private.doCleanups)
        private.manifest.update(self.source.source)
        private.seal()
        with self.assertRaises(owner.Rejected):
            private.validate()


class CanonicalDocsNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        native_fixture.NativeCustodyTests.setUpClass()

    def setUp(self):
        self.f = f = native_fixture.NativeCustodyTests()
        application.private_fixture_setup(f)
        self.addCleanup(f.doCleanups)
        f.store.db.close()
        self.source = SourceFixture(owner, product="platform", branch="main")
        self.source.github.owner = f.ci.owner
        self.source.github.token = f.ci.token
        f.ci = self.source.github
        f.binding.update(self.source.source)
        profile = f.policy["components"].pop("DruHustle/onesa-ai-platform:docs-public")
        profile["publication_mechanism"] = "existing-isolated-owner-vercel-cli"
        f.policy.update(schema_version=2, components={SCOPE: profile})
        f.policy["toolchain"].update(
            source_binding=copy.deepcopy(self.source.source),
            source_commit=f.binding["candidate_commit"],
            source_tree=f.binding["source_tree"],
            source_sha256=f.binding["source_sha256"],
            source_archives=application.pins(self.source),
        )
        (f.root / "policy.json").write_bytes(owner.canonical(f.policy))
        trust = json.loads((f.root / "trust.json").read_bytes())
        trust["policy_sha256"] = owner.file_digest(f.root / "policy.json")
        (f.root / "trust.json").write_bytes(owner.canonical(trust))
        f.commission_fixture()
        self.installed = f.root / "installed"
        self.installed.mkdir(mode=0o700)
        (self.installed / "oracle_owner.py").write_bytes(
            Path(owner.__file__).read_bytes()
        )
        (self.installed / "oracle_owner.py").chmod(0o600)
        artifacts = self.installed / "source-artifacts"
        artifacts.mkdir(mode=0o700)
        for name, value in self.source.archives.items():
            p = artifacts / (name + ".zip")
            p.write_bytes(base64.b64decode(value))
            p.chmod(0o600)
        self.enterContext(
            patch.object(owner, "__file__", str(self.installed / "oracle_owner.py"))
        )
        f.store = f.open()
        self.addCleanup(f.store.db.close)

    def test_real_signed_native_chain_keeps_commissioning_and_one_reserved_context(
        self,
    ):
        self.f.test_valid_zero_run_native_receipt_is_not_authorization_and_context_consumes_once()
        rows = self.f.store.db.execute("SELECT DISTINCT scope FROM records").fetchall()
        self.assertEqual(rows, [(SCOPE,)])
        self.assertGreaterEqual(
            self.source.calls.count(self.source.prefix + "branches/main"), 4
        )

    def test_source_bound_registration_still_requires_separate_native_possession(self):
        self.f.test_registration_is_untrusted_until_separate_commission_and_possession()

    def test_relabelled_root_subtree_or_native_key_cannot_import(self):
        f = self.f
        registered, _context, challenge = f.session()
        for field, value in (
            ("repository", "DruHustle/onesa-ai-platform"),
            ("repository_id", 1),
            ("source_tree", "e" * 40),
            ("product_source_tree", "d" * 40),
            ("component", "docs-internal"),
        ):
            with self.subTest(field=field), self.assertRaises(owner.Rejected):
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
        f.store.revoke(registered["id"])
        with self.assertRaises(owner.Rejected):
            native.import_observation(
                f.store, owner.canonical(f.envelope(registered, challenge))
            )

    def test_changed_main_refuses_preview_before_provider_or_intent(self):
        self.source.api_values[self.source.prefix + "branches/main"]["commit"][
            "sha"
        ] = "e" * 40
        downstream = SimpleNamespace(
            prepare=unittest.mock.Mock(), create_preview=unittest.mock.Mock()
        )
        with (
            patch.object(docs_owner, "for_binding", return_value=downstream),
            self.assertRaises(owner.Rejected),
        ):
            docs_owner.publish_preview(self.f.store, self.f.binding)
        downstream.prepare.assert_not_called()
        downstream.create_preview.assert_not_called()
        self.assertEqual(
            self.f.store.db.execute("SELECT count(*) FROM records").fetchone()[0], 0
        )

    def test_changed_fixed_archive_refuses_native_registration_without_records(self):
        archive = next((self.installed / "source-artifacts").glob("*.zip"))
        archive.write_bytes(archive.read_bytes() + b"changed")
        with self.assertRaises(owner.Rejected):
            self.f.registered()
        self.assertEqual(
            self.f.store.db.execute("SELECT count(*) FROM records").fetchone()[0], 0
        )

    def test_changed_main_after_challenge_cannot_complete_qualification(self):
        f = self.f
        registered, context, challenge = f.session()
        native.import_observation(
            f.store, owner.canonical(f.envelope(registered, challenge))
        )
        self.source.api_values[self.source.prefix + "branches/main"]["commit"][
            "sha"
        ] = "e" * 40
        with self.assertRaises(owner.Rejected):
            native.complete_qualification(f.store, context["id"])
        self.assertEqual(
            f.store.db.execute(
                "SELECT count(*) FROM records WHERE kind='qualification'"
            ).fetchone()[0],
            0,
        )
        self.assertFalse((f.root / "provider-count").exists())

    def test_component_selection_and_context_cannot_borrow_an_application_policy(self):
        f = self.f
        self.assertIsNotNone(driver.for_component(f.store, "docs-public"))
        with self.assertRaises(owner.Rejected):
            driver.for_component(f.store, "docs-internal")
        original = copy.deepcopy(f.policy)
        for name in ("api", "frontend", "docs-internal"):
            f.store.policy = copy.deepcopy(original)
            f.store.policy["components"]["DruHustle/onesa-ug:platform:" + name] = (
                copy.deepcopy(original["components"][SCOPE])
            )
            with self.subTest(name=name), self.assertRaises(owner.Rejected):
                f.store.issue_context(f.binding)
        self.assertEqual(
            f.store.db.execute("SELECT count(*) FROM records").fetchone()[0], 0
        )

    def test_changed_main_after_authorization_blocks_provider_creation(self):
        f = self.f
        registered, context, challenge = f.session()
        native.import_observation(
            f.store, owner.canonical(f.envelope(registered, challenge))
        )
        qualification = native.complete_qualification(f.store, context["id"])["record"]
        authorization = f.store.authorize(qualification["id"])["record"]
        self.source.api_values[self.source.prefix + "branches/main"]["commit"][
            "sha"
        ] = "e" * 40
        with self.assertRaises(owner.Rejected):
            f.store.deploy(authorization["id"])
        self.assertFalse((f.root / "provider-count").exists())
        self.assertEqual(
            f.store.db.execute("SELECT count(*) FROM deployments").fetchone()[0], 0
        )


class CanonicalDocsPrepareTests(unittest.TestCase):
    def setUp(self):
        self.f = f = install_fixture.DocsInstallTests()
        application.private_fixture_setup(f)
        self.addCleanup(f.doCleanups)
        # Extend the real disposable Git tree with the existing static config.
        relative = "onesa-ai-platform-frontend/apps/docs/vercel.json"
        raw = (Path(__file__).resolve().parents[2] / relative).read_bytes()
        source = f.root / "synthetic-source"
        (source / relative).write_bytes(raw)
        f.github.files[relative] = raw
        subprocess.run(
            ["git", "-C", str(source), "add", "."], check=True, capture_output=True
        )
        tree = subprocess.check_output(
            ["git", "-C", str(source), "write-tree"], text=True
        ).strip()
        archive = subprocess.check_output(["git", "-C", str(source), "archive", tree])
        f.manifest.update(
            source_tree=tree, tool_source_sha256=hashlib.sha256(archive).hexdigest()
        )
        f.put("tool-source.tar", archive)
        f.policy["toolchain"]["source_sha256"] = f.manifest["tool_source_sha256"]
        self.source = canonical_install(f)
        root = f.root / "publication-journal"
        root.mkdir(mode=0o700)
        self.enterContext(patch.object(docs, "ROOT", root))
        self.enterContext(patch.object(docs, "PLAN", f.root / "docs-plan.json"))
        self.enterContext(
            patch.object(owner, "__file__", str(f.root / "oracle_owner.py"))
        )
        self.store = SimpleNamespace(root=f.root, policy=f.policy, github=f.github)
        self.result = {
            "source": self.source.source,
            "actions_build_run_id": 100,
            "verification_only": True,
            "release_authorized": False,
            "artifacts": [
                {"name": "onesa-public-docs-staging", "file_manifest_sha256": "d" * 64},
                {
                    "name": "onesa-public-docs-production",
                    "file_manifest_sha256": "e" * 64,
                },
            ],
        }
        self.binding = {
            **self.source.source,
            "component": "docs-public",
            "source_sha256": f.manifest["tool_source_sha256"],
            "build_sha256": owner.digest(self.result),
            "artifact_digest": "sha256:" + "e" * 64,
            "configuration_sha256": {},
            "target_environment": "production",
        }
        folder = root / "artifacts" / self.binding["source_tree"]
        (folder / "build-100").mkdir(mode=0o700, parents=True)
        (folder / "source.tar").write_bytes(archive)
        (folder / "source.tar").chmod(0o600)
        archives = {}
        # The already-qualified reader has its own real ZIP/protocol suite. Here
        # its output is stubbed to test the installed file/pin/tar interface only.
        for identifier in range(300, 303):
            path = folder / "build-100" / (str(identifier) + ".zip")
            path.write_bytes(b"synthetic reader boundary " + str(identifier).encode())
            path.chmod(0o600)
            archives[str(identifier)] = {
                "path": str(path),
                "sha256": owner.file_digest(path),
            }
        self.plan = {
            "schema_version": 2,
            "verifier_store": str(f.root),
            "binding": self.binding,
            "build_run_id": 100,
            "archives": archives,
            "source_archive": str(folder / "source.tar"),
            "provider": {
                "project_id": "prj_fixture",
                "team_id": "team_fixture",
                "project_settings_sha256": "f" * 64,
                "production_alias": docs.ORIGIN,
            },
            "rollback": {},
            "vercel_configuration_sha256": hashlib.sha256(raw).hexdigest(),
        }
        self.seal_plan()
        self.reader = self.enterContext(
            patch.object(docs.builds, "read_build", return_value=self.result)
        )

    def seal_plan(self):
        self.binding["configuration_sha256"] = {
            env: owner.digest(
                {
                    "plan": {
                        key: value
                        for key, value in self.plan.items()
                        if key != "binding"
                    },
                    "environment": env,
                }
            )
            for env in ("staging", "production")
        }
        self.f.put("docs-plan.json", owner.canonical(self.plan))

    def test_real_product_tar_and_private_fixed_files_feed_complete_reader_identity(
        self,
    ):
        result = docs.prepare(self.store, self.binding)
        self.assertEqual(result, self.result)
        self.assertFalse(result["release_authorized"])
        args, kwargs = self.reader.call_args
        self.assertIs(args[0], self.f.github)
        self.assertEqual(args[1], self.source.source)
        self.assertEqual(set(args[3]), {300, 301, 302})
        self.assertEqual(kwargs["source_archives"], self.source.archives)
        self.assertIs(kwargs["require_local_checks"], True)
        self.assertFalse((self.f.root / "records.sqlite").exists())

    def test_product_tree_cannot_be_relabelled_before_reader_or_provider(self):
        self.binding["product_source_tree"] = "e" * 40
        self.store.policy["toolchain"]["source_binding"] = contract.source_identity(
            self.binding
        )
        self.seal_plan()
        with self.assertRaises(parser.Refused) as failure:
            docs.prepare(self.store, self.binding)
        self.assertIn("TREE", str(failure.exception))
        self.reader.assert_not_called()

    def test_changed_private_doc_archive_or_missing_installed_source_zip_refuses_before_reader(
        self,
    ):
        path = Path(self.plan["archives"]["300"]["path"])
        raw = path.read_bytes()
        path.write_bytes(raw + b"changed")
        with self.assertRaisesRegex(owner.Rejected, "ARCHIVE_BYTES_CHANGED"):
            docs.prepare(self.store, self.binding)
        path.write_bytes(raw)
        next((self.f.root / "source-artifacts").glob("*.zip")).unlink()
        with self.assertRaises(FileNotFoundError):
            docs.prepare(self.store, self.binding)
        self.reader.assert_not_called()

    def test_unreviewed_static_config_or_schema1_relabel_fails_before_reader(self):
        self.plan["vercel_configuration_sha256"] = "f" * 64
        self.seal_plan()
        with self.assertRaisesRegex(owner.Rejected, "HOST_CONFIGURATION_CHANGED"):
            docs.prepare(self.store, self.binding)
        self.plan["schema_version"] = 1
        self.seal_plan()
        with self.assertRaisesRegex(owner.Rejected, "EXACT_DOCS_PLAN_REQUIRED"):
            docs.prepare(self.store, self.binding)
        self.reader.assert_not_called()


class CanonicalDocsPublicationTests(unittest.TestCase):
    def setUp(self):
        self.deployment_for = docs.deployment_for
        self.f = f = runner_fixture.DriverTests()
        application.private_fixture_setup(f)
        self.addCleanup(f.doCleanups)
        self.source = SourceFixture(owner, product="platform", branch="main").source
        f.binding.update(self.source)
        f.spec["source"] = copy.deepcopy(self.source)
        f.spec["artifact"]["files"] = 2
        f.operation.update(
            issued_at=(owner.timestamp() - timedelta(minutes=1)).isoformat(),
            expires_at=(owner.timestamp() + timedelta(minutes=5)).isoformat(),
        )

    def test_canonical_preview_keeps_full_source_metadata_and_one_create(self):
        self.f.test_preview_uses_existing_isolated_cli_with_explicit_preview_target()
        args = self.f.commands[0]
        metadata = dict(
            args[index + 1].split("=", 1)
            for index, token in enumerate(args)
            if token == "--meta"
        )
        for key, value in contract.source_metadata(self.f.binding).items():
            self.assertEqual(metadata[key], value)
        folder = docs.operation_folder(self.f.binding, self.f.operation["id"])
        scope = json.loads((folder / "transport/scope.json").read_bytes())
        self.assertEqual(
            {key: scope[key] for key in owner.AI_SOURCE_FIELDS}, self.source
        )
        self.assertEqual(scope["component"], "docs-public")

    def test_retained_canonical_journal_is_get_only_and_requires_complete_identity(
        self,
    ):
        row = self.f.retained()
        row["meta"].update(contract.source_metadata(self.f.binding))
        with (
            patch.object(docs, "target", return_value=("prj_fixture", "team_fixture")),
            patch.object(docs, "provider_get", return_value=row),
            patch.object(subprocess, "run") as process,
        ):
            result = docs.inspect_retained_publications(self.f.store)
            self.assertFalse(result[0]["production_acceptance_claimed"])
            self.assertEqual(result[0]["provider_writes"], 0)
            process.assert_not_called()
            for field in contract.source_metadata(self.f.binding):
                value = row["meta"].pop(field)
                with (
                    self.subTest(field=field),
                    self.assertRaises((owner.Rejected, KeyError)),
                ):
                    docs.inspect_retained_publications(self.f.store)
                row["meta"][field] = value

    def test_old_uncertain_journal_blocks_new_canonical_source_before_create(self):
        f = self.f
        old = {
            "repository": "DruHustle/onesa-ai-platform",
            "component": "docs-public",
            "candidate_commit": "e" * 40,
            "source_tree": "f" * 40,
        }
        operation = str(uuid4())
        folder = docs.operation_folder(old, operation)
        folder.mkdir(mode=0o700, parents=True)
        docs.durable(
            folder / "intent.json",
            owner.canonical(
                {
                    "binding": old,
                    "operation_id": operation,
                    "prepared": {
                        **f.spec,
                        "source": contract.source_identity(old),
                        "environment": "production",
                    },
                    "provider_create_budget": 1,
                    "automatic_retry": False,
                }
            ),
        )
        original = (folder / "intent.json").read_bytes()
        with (
            patch.object(docs, "target", return_value=("prj_fixture", "team_fixture")),
            patch.object(subprocess, "run") as process,
        ):
            with self.assertRaisesRegex(owner.Rejected, "OUTCOME_UNCERTAIN"):
                docs.create_publication(f.store, f.operation, production=True)
            process.assert_not_called()
        self.assertEqual((folder / "intent.json").read_bytes(), original)
        self.assertFalse(docs.operation_folder(f.binding, f.operation["id"]).exists())

    def test_unknown_or_relabelled_journal_cannot_hide_behind_canonical_source(self):
        row = self.f.retained()
        row["meta"].update(contract.source_metadata(self.f.binding))
        path = (
            docs.operation_folder(self.f.binding, self.f.operation["id"])
            / "intent.json"
        )
        baseline = json.loads(path.read_bytes())
        for field in owner.AI_SOURCE_FIELDS:
            altered = copy.deepcopy(baseline)
            altered["prepared"]["source"].pop(field)
            path.write_bytes(owner.canonical(altered))
            with (
                patch.object(
                    docs, "target", return_value=("prj_fixture", "team_fixture")
                ),
                patch.object(docs, "provider_get") as request,
            ):
                with (
                    self.subTest(field=field),
                    self.assertRaises((owner.Rejected, KeyError)),
                ):
                    docs.inspect_retained_publications(self.f.store)
                request.assert_not_called()

    def test_canonical_provider_receipt_refuses_source_metadata_loss_or_relabeling(
        self,
    ):
        f = self.f
        folder = docs.operation_folder(f.binding, f.operation["id"])
        folder.mkdir(mode=0o700, parents=True)
        docs.durable(
            folder / "intent.json",
            owner.canonical(
                {
                    "binding": f.binding,
                    "operation_id": f.operation["id"],
                    "prepared": f.spec,
                }
            ),
        )
        row = {
            "id": "dpl_fixture",
            "projectId": "prj_fixture",
            "readyState": "READY",
            "target": None,
            "url": "onesa-docs-fixture.vercel.app",
            "createdAt": int(owner.timestamp().timestamp() * 1000),
            "meta": {
                **contract.source_metadata(f.binding),
                "onesaSourceRevision": f.binding["candidate_commit"],
                "onesaOracleOperation": f.operation["id"],
                "onesaArtifactManifest": "d" * 64,
            },
        }

        def get(_store, path):
            if path.startswith("/v6/deployments?"):
                return {"deployments": [{"uid": row["id"], "meta": row["meta"]}]}
            self.assertEqual(path, "/v13/deployments/dpl_fixture")
            return row

        with (
            patch.object(docs, "target", return_value=("prj_fixture", "team_fixture")),
            patch.object(docs, "plan", return_value={}),
            patch.object(docs, "project"),
            patch.object(docs, "provider_get", side_effect=get),
        ):
            observed = self.deployment_for(f.store, f.operation, production=False)
            self.assertEqual(observed["source"], self.source)
            for field in contract.source_metadata(f.binding):
                value = row["meta"].pop(field)
                with self.subTest(field=field), self.assertRaises(owner.Rejected):
                    self.deployment_for(f.store, f.operation, production=False)
                row["meta"][field] = value


if __name__ == "__main__":
    unittest.main()
