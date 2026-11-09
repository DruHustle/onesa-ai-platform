"""Real local source/Ed25519 boundaries; no installed or hosted acceptance."""

import base64
import copy
import datetime as dt
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import oracle_ai_frontend as frontend
import oracle_ai_runner as runner
import oracle_frontend_build as builder
import oracle_install as installer
import oracle_owner as owner
import oracle_release_profiles as profiles
import test_oracle_install as install_fixture
import test_oracle_owner as store_fixture

# Keep the credential-free canonical protocol fixture inside this product.
from source_protocol_fixtures import SourceFixture


def pins(source):
    return {
        name: hashlib.sha256(base64.b64decode(data)).hexdigest()
        for name, data in source.archives.items()
    }


def private_fixture_setup(fixture):
    """Reuse the synthetic store with a real, private temporary parent."""
    original = tempfile.TemporaryDirectory

    def temporary(*args, **kwargs):
        if kwargs.get("dir") is None:
            kwargs["dir"] = Path.home()
        return original(*args, **kwargs)

    with patch.object(tempfile, "TemporaryDirectory", side_effect=temporary):
        fixture.setUp()


class CanonicalInstallTests(unittest.TestCase):
    def setUp(self):
        self.fixture = f = install_fixture.InstallTests()
        private_fixture_setup(f)
        self.addCleanup(f.doCleanups)
        self.source = source = SourceFixture(owner, product="platform", branch="main")
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
                == source.prefix
                + "git/trees/"
                + s["product_source_tree"]
                + "?recursive=1"
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
        f.policy["components"] = {
            key.replace(
                profiles.REPOSITORY + ":", profiles.CANONICAL_REPOSITORY + ":platform:"
            ): value
            for key, value in f.policy["components"].items()
        }
        target = installer.INSTALL_PARENT / ("ai-canonical-" + s["source_tree"])
        for name, value in f.policy["components"].items():
            script = (
                "oracle_ai_runner.py"
                if name.endswith(":api")
                else "oracle_ai_frontend.py"
            )
            for phase in value["runners"].values():
                phase["path"] = str(target / "runners" / script)
        f.policy["toolchain"].update(
            source_binding=copy.deepcopy(s),
            source_tree=s["source_tree"],
            source_archives=pins(source),
        )
        for name, data in source.archives.items():
            f.put("source-artifacts/" + name + ".zip", base64.b64decode(data))
        f.seal()

    def test_exact_main_root_and_product_tar_remain_separate_and_non_authorizing(self):
        manifest, target, payloads, ci = self.fixture.validate()
        self.assertEqual(target.name, "ai-canonical-" + manifest["source_tree"])
        self.assertNotEqual(manifest["source_tree"], manifest["product_source_tree"])
        self.assertEqual(ci[0]["source"], self.source.source)
        self.assertTrue(ci[0]["verification_only"])
        self.assertFalse(ci[0]["release_authorized"])
        self.assertEqual(
            len([key for key in payloads if key.startswith("source-artifacts/")]), 2
        )
        self.assertFalse(
            any(
                (self.fixture.root / name).exists()
                for name in ("records.sqlite", "signing.pem", "installation.json")
            )
        )

    def test_source_policy_alone_is_not_component_commissioning(self):
        self.fixture.policy = copy.deepcopy(self.source.policy)
        self.fixture.seal()
        with self.assertRaises(owner.Rejected):
            self.fixture.validate()

    def test_foreign_main_root_subtree_and_fixed_zip_tampering_fail_closed(self):
        for key, value in [
            ("repository_id", 1),
            ("product", "portal"),
            ("source_path", "onesa-robot"),
            ("branch", "staging"),
            ("source_tree", "f" * 40),
            ("product_source_tree", "e" * 40),
        ]:
            original = self.fixture.manifest[key]
            self.fixture.manifest[key] = value
            self.fixture.seal()
            with self.subTest(key=key), self.assertRaises(owner.Rejected):
                self.fixture.validate()
            self.fixture.manifest[key] = original
        self.fixture.seal()
        archive = (
            self.fixture.root
            / "source-artifacts"
            / (next(iter(self.source.archives)) + ".zip")
        )
        archive.write_bytes(archive.read_bytes() + b"changed")
        with self.assertRaises(owner.Rejected):
            self.fixture.validate()

    def test_native_profiles_stay_literal_and_docs_cannot_borrow_application_source(
        self,
    ):
        for names in (profiles.LEGACY, profiles.SCOPED, profiles.EXPANDED):
            policy = copy.deepcopy(self.fixture.policy)
            template = copy.deepcopy(next(iter(policy["components"].values())))
            policy["components"] = {}
            for name in names:
                value = copy.deepcopy(template)
                if names != profiles.LEGACY:
                    value["release_mode"] = profiles.PROFILES[name][1]
                policy["components"][
                    profiles.CANONICAL_REPOSITORY + ":platform:" + name
                ] = value
            self.assertEqual(profiles.policy_components(policy), names)
            for name in names:
                profiles.validate_mode(
                    {**self.source.source, "component": name},
                    profiles.PROFILES[name][1],
                    policy,
                )
        # Public Docs now has a separate canonical source consumer. It still
        # cannot enter any literal AI application profile or borrow its policy.
        with self.assertRaises(profiles.ProfileError):
            profiles.validate_mode(
                {**self.source.source, "component": "docs-public"},
                "foundation",
                self.fixture.policy,
            )
        with self.assertRaises(profiles.ProfileError):
            profiles.validate_mode(
                {**self.source.source, "component": "docs-internal"},
                "foundation",
                self.fixture.policy,
            )
        for component in (
            "worker",
            "portal",
            "unknown",
        ):
            with self.subTest(component=component), self.assertRaises(owner.Rejected):
                self.source.github.qualify(
                    {**self.source.source, "component": component}, self.source.archives
                )

    def test_failed_first_attempt_and_missing_required_checks_cannot_install(self):
        self.source.run["run_attempt"] = 2
        with self.assertRaises(owner.Rejected):
            self.fixture.validate()
        self.source.run["run_attempt"] = 1
        item = next(iter(self.fixture.policy["components"].values()))
        item["required_checks"]["staging"].remove("persistence")
        self.fixture.seal()
        with self.assertRaises(owner.Rejected):
            self.fixture.validate()

    def test_real_actions_custody_refusal_remains_before_api(self):
        github = owner.GitHub("synthetic-only")
        with (
            patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}),
            patch.object(github, "api") as api,
        ):
            with self.assertRaisesRegex(
                owner.Rejected, "Owner custody cannot run in Actions"
            ):
                github.owner()
            api.assert_not_called()


class CanonicalStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store_fixture.OwnerStoreTests.setUpClass()

    def setUp(self):
        self.fixture = f = store_fixture.OwnerStoreTests()
        private_fixture_setup(f)
        self.addCleanup(f.doCleanups)
        f.store.db.close()
        self.source = SourceFixture(owner, product="platform", branch="main")
        self.source.github.owner = f.ci.owner
        f.ci = self.source.github
        self.binding = {**f.binding, **self.source.source, "component": "api"}
        template = copy.deepcopy(next(iter(f.policy["components"].values())))
        template["qualification_attempt_limit"] = 1
        f.policy = {
            "schema_version": 2,
            "components": {
                profiles.CANONICAL_REPOSITORY + ":platform:" + name: copy.deepcopy(
                    template
                )
                for name in profiles.LEGACY
            },
            "toolchain": {
                "source_binding": copy.deepcopy(self.source.source),
                "source_commit": self.binding["candidate_commit"],
                "source_tree": self.binding["source_tree"],
                "source_sha256": self.binding["source_sha256"],
                "source_archives": pins(self.source),
            },
        }
        (f.root / "policy.json").write_bytes(owner.canonical(f.policy))
        trust = json.loads((f.root / "trust.json").read_bytes())
        trust["policy_sha256"] = owner.file_digest(f.root / "policy.json")
        (f.root / "trust.json").write_bytes(owner.canonical(trust))
        f.commission_fixture()
        installed = f.root / "installed"
        installed.mkdir(mode=0o700)
        (installed / "oracle_owner.py").write_bytes(Path(owner.__file__).read_bytes())
        (installed / "oracle_owner.py").chmod(0o600)
        (installed / "source-artifacts").mkdir(mode=0o700)
        for name, data in self.source.archives.items():
            path = installed / "source-artifacts" / (name + ".zip")
            path.write_bytes(base64.b64decode(data))
            path.chmod(0o600)
        self.enterContext(
            patch.object(owner, "__file__", str(installed / "oracle_owner.py"))
        )
        self.store = f.open()
        self.addCleanup(self.store.db.close)
        self.installed = installed

    def test_real_signed_chain_rechecks_fixed_source_and_does_not_reuse_context(self):
        context = self.store.issue_context(self.binding)["record"]["id"]
        with self.assertRaises(owner.Rejected):
            self.store.issue_context(
                {
                    **self.binding,
                    "configuration_sha256": {
                        "staging": "2" * 64,
                        "production": "3" * 64,
                    },
                }
            )
        qualification = self.store.qualify(context)
        self.assertEqual(qualification["record"]["workflow_run_id"], 0)
        self.assertTrue(
            qualification["record"]["details"]["ci"][0]["verification_only"]
        )
        authorization = self.store.authorize(qualification["record"]["id"])
        accepted = self.store.deploy(authorization["record"]["id"])
        self.assertEqual(accepted["record"]["binding"], self.binding)
        self.assertEqual(
            self.store.db.execute(
                "SELECT scope FROM records WHERE id=?", (context,)
            ).fetchone()[0],
            profiles.CANONICAL_REPOSITORY + ":platform:api",
        )
        self.assertEqual((self.fixture.root / "provider-count").read_text(), "1")
        self.assertGreaterEqual(
            self.source.calls.count(self.source.prefix + "branches/main"), 4
        )

    def test_changed_installed_zip_never_qualifies(self):
        context = self.store.issue_context(self.binding)["record"]["id"]
        archive = next((self.installed / "source-artifacts").glob("*.zip"))
        archive.write_bytes(archive.read_bytes() + b"changed")
        with self.assertRaises(owner.Rejected):
            self.store.qualify(context)
        self.assertEqual(
            self.store.db.execute(
                "SELECT COUNT(*) FROM records WHERE kind='qualification'"
            ).fetchone()[0],
            0,
        )
        self.assertFalse((self.fixture.root / "provider-count").exists())

    def test_changed_main_after_qualification_refuses_authorization(self):
        context = self.store.issue_context(self.binding)["record"]["id"]
        qualification = self.store.qualify(context)["record"]["id"]
        self.source.api_values[self.source.prefix + "branches/main"]["commit"][
            "sha"
        ] = "e" * 40
        with self.assertRaises(owner.Rejected):
            self.store.authorize(qualification)
        self.assertFalse((self.fixture.root / "provider-count").exists())
        self.assertEqual(
            self.store.db.execute(
                "SELECT COUNT(*) FROM records WHERE kind='authorization'"
            ).fetchone()[0],
            0,
        )

    def test_changed_main_after_authorization_refuses_provider_creation(self):
        context = self.store.issue_context(self.binding)["record"]["id"]
        qualification = self.store.qualify(context)["record"]["id"]
        authorization = self.store.authorize(qualification)["record"]["id"]
        self.source.api_values[self.source.prefix + "branches/main"]["commit"][
            "sha"
        ] = "e" * 40
        with self.assertRaises(owner.Rejected):
            self.store.deploy(authorization)
        self.assertFalse((self.fixture.root / "provider-count").exists())
        self.assertEqual(
            self.store.db.execute("SELECT COUNT(*) FROM deployments").fetchone()[0], 0
        )

    def test_actual_runner_custody_refuses_a_writable_ancestor(self):
        shared = self.fixture.root / "writable"
        shared.mkdir(mode=0o700)
        child = shared / "private-record.json"
        child.write_bytes(b"{}")
        child.chmod(0o600)
        shared.chmod(0o777)
        try:
            with self.assertRaisesRegex(runner.Refused, "CUSTODY_ANCESTOR"):
                runner.private(child, uid=os.getuid())
        finally:
            shared.chmod(0o700)


class RetainedVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store_fixture.OwnerStoreTests.setUpClass()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.home())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Distinct real verifier bytes and module identity, not a mocked digest.
        self.original = self.root / "original_owner.py"
        self.original.write_bytes(
            Path(owner.__file__).read_bytes()
            + b"\n# Original synthetic installed verifier version.\n"
        )
        self.original.chmod(0o600)
        spec = importlib.util.spec_from_file_location(
            "original_ai_verifier_fixture", self.original
        )
        self.original_owner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.original_owner)
        self.fixture = f = store_fixture.OwnerStoreTests()
        with patch.object(store_fixture, "o", self.original_owner):
            private_fixture_setup(f)
        self.addCleanup(f.doCleanups)
        f.store.db.close()
        f.binding["repository"] = profiles.REPOSITORY
        profile = next(iter(f.policy["components"].values()))
        f.policy["components"] = {profiles.REPOSITORY + ":api": profile}
        (f.root / "policy.json").write_bytes(owner.canonical(f.policy))
        trust = json.loads((f.root / "trust.json").read_bytes())
        trust["policy_sha256"] = owner.file_digest(f.root / "policy.json")
        (f.root / "trust.json").write_bytes(owner.canonical(trust))
        with patch.object(store_fixture, "o", self.original_owner):
            f.commission_fixture()
            f.store = f.open()
        self.addCleanup(f.store.db.close)
        context = f.store.issue_context(f.binding)["record"]["id"]
        qualification = f.store.qualify(context)["record"]["id"]
        authorization = f.store.authorize(qualification)["record"]["id"]
        accepted = f.store.deploy(authorization)
        self.operation = accepted["record"]["parent"]
        self.context = context
        self.qualification = qualification
        self.authorization = authorization
        self.authorization_envelope = f.store.get(authorization)
        self.authorization_record = self.authorization_envelope["record"]
        self.attempt = self.authorization_record["details"]["attempt_id"]
        self.consumer = {
            **f.binding,
            **SourceFixture(owner, product="platform", branch="main").source,
            "candidate_commit": "d" * 40,
        }
        self.retained = {
            "binding": f.binding,
            "operation_id": self.operation,
            "verifier_store": str(f.root),
            "verifier_path": str(self.original),
        }
        self.registry = {"installations": {str(f.root): {**trust, "active": True}}}
        self.enterContext(
            patch.object(runner, "private", side_effect=lambda p, **kw: Path(p))
        )
        self.enterContext(
            patch.object(
                runner,
                "read",
                side_effect=lambda p: (
                    self.registry
                    if str(p) == "/etc/onesa/oracle-release-trust.json"
                    else json.loads(Path(p).read_bytes())
                ),
            )
        )

    def inspect(self):
        return runner.verify_retained_dependency(
            self.consumer, self.retained, {"verifier_store": "not-the-original-store"}
        )

    def signed_authorization(self, details):
        """Issue malformed fixture bytes signed with the original synthetic key."""
        envelope = copy.deepcopy(self.authorization_envelope)
        envelope["record"] = {
            **copy.deepcopy(self.authorization_record),
            "details": details,
        }
        envelope["signature"]["value"] = base64.b64encode(
            self.original_owner.signed_bytes(
                self.fixture.root / "signing.pem",
                self.fixture.root / "public.pem",
                owner.canonical(envelope["record"]),
            )
        ).decode()
        self.fixture.store.db.execute(
            "UPDATE records SET envelope=? WHERE id=?",
            (owner.canonical(envelope).decode(), self.authorization),
        )

    def test_original_verifier_key_and_chain_are_read_without_new_authority_or_store_writes(
        self,
    ):
        before = {
            p.name: p.read_bytes() for p in self.fixture.root.iterdir() if p.is_file()
        }
        names = set(self.fixture.root.iterdir())
        self.assertNotEqual(runner.sha(runner.VERIFIER), runner.sha(self.original))
        with self.assertRaisesRegex(runner.Refused, "ISSUER_CUSTODY_PIN_CHANGED"):
            runner.verify_invocation(
                self.retained["binding"],
                {"operation_id": self.operation, "read_only": True},
                "production",
                {"verifier_store": str(self.fixture.root)},
                dependency=True,
            )
        records = self.inspect()
        self.assertEqual(records[0]["kind"], "production-verification")
        self.assertTrue(all(r["binding"] == self.retained["binding"] for r in records))
        attempts = [r for r in records if r["kind"] == "authorization-attempt"]
        self.assertEqual([r["id"] for r in attempts], [self.attempt])
        self.assertEqual(attempts[0]["parent"], self.qualification)
        self.assertEqual(
            before,
            {
                p.name: p.read_bytes()
                for p in self.fixture.root.iterdir()
                if p.is_file()
            },
        )
        self.assertEqual(names, set(self.fixture.root.iterdir()))

    def test_foreign_or_relabelled_record_uncommissioned_anchor_and_changed_original_fail(
        self,
    ):
        original_binding = self.retained["binding"]
        for key, value in [
            ("repository", profiles.CANONICAL_REPOSITORY),
            ("candidate_commit", "f" * 40),
            ("component", "frontend"),
            ("target_environment", "staging"),
        ]:
            self.retained["binding"] = {**original_binding, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.inspect()
        self.retained["binding"] = original_binding
        self.registry["installations"][str(self.fixture.root)]["active"] = False
        with self.assertRaises(runner.Refused):
            self.inspect()
        self.registry["installations"][str(self.fixture.root)]["active"] = True
        self.original.write_bytes(self.original.read_bytes() + b"# changed\n")
        with self.assertRaisesRegex(runner.Refused, "ISSUER_CUSTODY_PIN_CHANGED"):
            self.inspect()

    def test_retained_reader_cannot_authorize_mutation_or_ignore_revocation(self):
        for phase in ("staging", "operations", "deploy"):
            with self.subTest(phase=phase), self.assertRaises(runner.Refused):
                runner.verify_invocation(
                    self.retained["binding"],
                    {"operation_id": self.operation, "read_only": True},
                    phase,
                    {"verifier_store": str(self.fixture.root)},
                    dependency=True,
                    retained_verifier=str(self.original),
                    consumer_binding=self.consumer,
                )
        self.fixture.store.revoke(self.context)
        with self.assertRaises(runner.Refused):
            self.inspect()

    def test_original_attempt_revocation_refuses_an_accepted_dependency(self):
        self.assertEqual(self.inspect()[0]["kind"], "production-verification")
        self.fixture.store.revoke(self.attempt)
        row = self.fixture.store.db.execute(
            "SELECT kind,revoked FROM records WHERE id=?", (self.attempt,)
        ).fetchone()
        self.assertEqual(row, ("authorization-attempt", 1))
        with self.assertRaisesRegex(runner.Refused, "MISSING_OR_REVOKED"):
            self.inspect()

    def test_missing_malformed_and_ancestor_attempt_references_are_refused(self):
        original = self.authorization_record["details"]
        cases = [
            None,
            [],
            {k: v for k, v in original.items() if k != "attempt_id"},
            {**original, "decision": "reject"},
            {**original, "physical_hardware_authorized": True},
            *(
                {**original, "attempt_id": value}
                for value in [None, [], "not-a-uuid", self.qualification]
            ),
        ]
        for details in cases:
            with self.subTest(details=details):
                self.signed_authorization(details)
                with self.assertRaises(ValueError):
                    self.inspect()
                self.signed_authorization(original)
        self.fixture.store.db.execute("DELETE FROM records WHERE id=?", (self.attempt,))
        with self.assertRaisesRegex(runner.Refused, "MISSING_OR_REVOKED"):
            self.inspect()

    def test_signed_companion_must_match_kind_source_parent_and_pending_decision(self):
        binding = self.retained["binding"]
        for change in [
            {"kind": "authorization-companion"},
            {"binding": {**binding, "candidate_commit": "f" * 40}},
            {"parent": self.context},
            {"details": {"decision": "approve"}},
            {"details": []},
        ]:
            with self.subTest(change=change):
                value = {
                    "kind": "authorization-attempt",
                    "binding": binding,
                    "details": {"decision": "PENDING"},
                    "parent": self.qualification,
                    **change,
                }
                companion = self.fixture.store.put(**value)["record"]["id"]
                self.signed_authorization(
                    {**self.authorization_record["details"], "attempt_id": companion}
                )
                with self.assertRaises(runner.Refused):
                    self.inspect()
                self.signed_authorization(self.authorization_record["details"])

    def test_attempt_signature_is_checked_and_unrelated_new_attempt_is_not_authority(
        self,
    ):
        newer = self.fixture.store.put(
            "authorization-attempt",
            self.retained["binding"],
            {"decision": "PENDING"},
            parent=self.qualification,
        )["record"]["id"]
        with patch.object(
            runner, "now", return_value=owner.timestamp() + dt.timedelta(days=2)
        ):
            records = self.inspect()
        self.assertIn(self.attempt, {r["id"] for r in records})
        self.assertNotIn(newer, {r["id"] for r in records})
        envelope = self.fixture.store.get(self.attempt, historical=True)
        envelope["record"]["details"]["decision"] = "changed without signature"
        self.fixture.store.db.execute(
            "UPDATE records SET envelope=? WHERE id=?",
            (owner.canonical(envelope).decode(), self.attempt),
        )
        with self.assertRaises(runner.Refused):
            self.inspect()


class CanonicalProviderTests(unittest.TestCase):
    def setUp(self):
        self.source = SourceFixture(owner, product="platform", branch="main").source
        self.binding = {
            **self.source,
            "component": "frontend",
            "source_sha256": "d" * 64,
        }

    def test_full_provider_source_and_main_ref_are_required_for_preview(self):
        row = {
            "id": "dpl_fixture",
            "projectId": "prj_fixture",
            "target": None,
            "meta": {
                "githubCommitSha": self.binding["candidate_commit"],
                "githubCommitRef": "main",
                **profiles.source_metadata(self.binding),
            },
        }
        with patch.object(frontend, "provider", return_value=row):
            frontend.check_deployment(
                row["id"], self.binding, "staging", {"project_id": "prj_fixture"}
            )
            for key in list(profiles.source_metadata(self.binding)) + [
                "githubCommitRef"
            ]:
                old = row["meta"].pop(key)
                with self.subTest(key=key), self.assertRaises(runner.Refused):
                    frontend.check_deployment(
                        row["id"],
                        self.binding,
                        "staging",
                        {"project_id": "prj_fixture"},
                    )
                row["meta"][key] = old

    def test_canonical_paths_are_distinct_from_all_preserved_legacy_paths(self):
        for name in profiles.EXPANDED:
            current = {**self.binding, "component": name}
            old = {
                "repository": profiles.REPOSITORY,
                "component": name,
                "candidate_commit": "a" * 40,
            }
            self.assertNotEqual(profiles.scope(current), profiles.scope(old))
            self.assertNotEqual(
                profiles.artifact_folder(current, "/private/root"),
                profiles.artifact_folder(old, "/private/root"),
            )
            self.assertNotEqual(
                profiles.configuration_folder(current, "/private/root"),
                profiles.configuration_folder(old, "/private/root"),
            )
            self.assertNotEqual(
                profiles.plan_path(
                    current, "/private/api.json", "/private/frontend.json"
                ),
                profiles.plan_path(old, "/private/api.json", "/private/frontend.json"),
            )


class CanonicalBuildMetadataTests(unittest.TestCase):
    """Real source tar/metadata hashes; a synthetic Docker response, not a build."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.home())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir(mode=0o700)
        files = {
            "onesa-ai-platform-backend/app/twin_files.py": b"# synthetic backend\n",
            "onesa-ai-platform-frontend/apps/chat/vercel.json": b'{"version":2}',
        }
        for name, data in files.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for command in (
            ["git", "init", "--quiet", str(self.source)],
            ["git", "-C", str(self.source), "add", "."],
        ):
            subprocess.run(command, check=True, capture_output=True)
        product_tree = (
            subprocess.check_output(["git", "-C", str(self.source), "write-tree"])
            .decode()
            .strip()
        )
        with tarfile.open(self.root / "source.tar", "w") as archive:
            for name, data in files.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                member.mode = 0o644
                archive.addfile(member, io.BytesIO(data))
        self.binding = {
            **SourceFixture(owner, product="platform", branch="main").source,
            "product_source_tree": product_tree,
            "component": "frontend",
            "source_sha256": runner.sha(self.root / "source.tar"),
        }
        self.tool = "sha256:" + "d" * 64
        self.metadata = {
            "projectId": "prj_fixture",
            "orgId": "team_fixture",
            "projectName": "synthetic-only",
            "settings": {
                "framework": "nextjs",
                "rootDirectory": profiles.frontend_root(self.binding),
                "buildCommand": None,
                "installCommand": None,
                "outputDirectory": None,
                "nodeVersion": "24.x",
            },
            "public_environment": {
                "NEXT_PUBLIC_ONESA_DOCUMENTATION_URL": "https://docs.onesa.eu",
                "NEXT_PUBLIC_ONESA_ENGINEERING_DOCUMENTATION_URL": "",
            },
        }
        self.builds = []

    def docker(self, args, **kwargs):
        if args[1:3] == ["image", "inspect"]:
            return subprocess.CompletedProcess(
                args,
                0,
                json.dumps(
                    [
                        {
                            "Id": self.tool,
                            "Architecture": "amd64",
                            "Config": {"Labels": {"org.onesa.vercel-cli": builder.CLI}},
                        }
                    ]
                ).encode(),
            )
        self.assertEqual(args[1], "run")
        self.assertIn("--read-only", args)
        self.assertNotIn("--token", args)
        work = Path(
            next(
                arg.removesuffix(":/workspace:rw")
                for arg in args
                if arg.endswith(":/workspace:rw")
            )
        )
        project = json.loads((work / ".vercel/project.json").read_bytes())
        self.assertEqual(project["settings"]["rootDirectory"], frontend.APP_ROOT)
        self.assertEqual(
            json.loads((work / ".vercel/deployment-project.json").read_bytes())[
                "settings"
            ],
            self.metadata["settings"],
        )
        self.builds.append(args)
        output = work / ".vercel/output"
        (output / "static").mkdir(parents=True)
        (output / "config.json").write_text('{"version":3}')
        (output / "static/app.js").write_bytes(b"// synthetic output\n")
        return subprocess.CompletedProcess(args, 0)

    def test_product_relative_build_keeps_canonical_provider_metadata_and_hashes(self):
        for environment in runner.ENV:
            with patch.object(builder.subprocess, "run", side_effect=self.docker):
                receipt = builder.build(
                    self.root,
                    self.binding,
                    self.metadata,
                    self.tool,
                    environment=environment,
                )
            self.assertEqual(receipt["state"], "BUILT_NOT_QUALIFIED_OR_AUTHORIZED")
            self.assertEqual(receipt["binding"], self.binding)
            self.assertFalse(receipt["provider_credentials_mounted"])
            self.assertEqual("--prod" in self.builds[-1], environment == "production")
            with tarfile.open(receipt["artifact_path"]) as archive:
                project = archive.extractfile(".vercel/project.json").read()
                self.assertEqual(
                    json.loads(project)["settings"], self.metadata["settings"]
                )
                self.assertEqual(
                    hashlib.sha256(project).hexdigest(),
                    receipt["deployment_metadata_files"][".vercel/project.json"],
                )
            self.assertEqual(
                receipt["artifact_sha256"], runner.sha(receipt["artifact_path"])
            )

    def test_old_or_foreign_provider_root_fails_before_build_and_product_tree_cannot_be_root(
        self,
    ):
        for root in (frontend.APP_ROOT, "onesa-robot/frontend", "../outside"):
            metadata = copy.deepcopy(self.metadata)
            metadata["settings"]["rootDirectory"] = root
            with (
                patch.object(builder.subprocess, "run") as docker,
                self.assertRaises(runner.Refused),
            ):
                builder.build(self.root, self.binding, metadata, self.tool)
            docker.assert_not_called()
        with (
            patch.object(builder.subprocess, "run") as docker,
            self.assertRaises(runner.Refused),
        ):
            builder.build(
                self.root,
                {**self.binding, "product_source_tree": self.binding["source_tree"]},
                self.metadata,
                self.tool,
            )
        docker.assert_not_called()


class GenerationTransitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / "retained.env"
        self.original = {
            "ONESA_MODEL_BACKEND": "cloudflare",
            "ONESA_MODEL_NAME": runner.PREVIOUS_GENERATION,
            "ONESA_MODEL_BASE_URL": "https://api.cloudflare.com/client/v4/accounts/"
            + "a" * 32
            + "/ai/v1",
            "ONESA_MODEL_API_KEY": "synthetic-generation-only",
            "ONESA_EMBEDDING_BACKEND": "cloudflare",
            "ONESA_EMBEDDING_NAME": "@cf/qwen/qwen3-embedding-0.6b",
            "ONESA_EMBEDDING_REVISION": "cf-qwen3-mrl256-v1",
            "ONESA_EMBEDDING_API_KEY": "synthetic-embedding-only",
            "ONESA_DIGITAL_TWINS_ENABLED": "true",
            "ONESA_CYBERSECURITY_ENABLED": "true",
        }
        self.binding = {
            **SourceFixture(owner, product="platform", branch="main").source,
            "component": "twins-api",
        }
        self.retained = {
            "repository": profiles.REPOSITORY,
            "component": "api",
            "candidate_commit": "d" * 40,
            "target_environment": "production",
            "configuration_sha256": {},
        }
        self.plan = {
            "binding": self.binding,
            "mode": "twins",
            "generation_transition": runner.GENERATION_TRANSITION,
            "rollback": {"binding": self.retained},
        }
        self.seal()
        self.prepared = {**self.original, "ONESA_MODEL_NAME": runner.CURRENT_GENERATION}
        self.enterContext(
            patch.object(runner, "private", side_effect=lambda p, **kw: Path(p))
        )
        self.enterContext(
            patch.object(runner, "candidate_environment", return_value=self.file)
        )
        self.enterContext(
            patch.object(
                runner,
                "now",
                return_value=dt.datetime(2026, 11, 7, tzinfo=dt.timezone.utc),
            )
        )

    def seal(self):
        self.file.write_text(
            "".join(key + "=" + value + "\n" for key, value in self.original.items())
        )
        self.retained["configuration_sha256"] = {
            env: runner.sha(self.file) for env in runner.ENV
        }

    def test_fixed_generation_change_preserves_both_enabled_features_and_embeddings(
        self,
    ):
        for env in runner.ENV:
            self.assertTrue(
                runner.generation_transition(
                    self.plan, self.original, self.prepared, env
                )
            )
        self.assertEqual(
            profiles.enabled_features(self.prepared, "twins"),
            {"twins", "cybersecurity"},
        )

    def test_provider_credentials_embedding_features_and_unreviewed_models_cannot_piggyback(
        self,
    ):
        for key in self.prepared:
            changed = {**self.prepared, key: "changed"}
            with self.subTest(key=key), self.assertRaises(runner.Refused):
                runner.generation_transition(
                    self.plan, self.original, changed, "production"
                )
        self.plan["mode"] = "identity"
        with self.assertRaises(runner.Refused):
            runner.generation_transition(
                self.plan, self.original, self.prepared, "production"
            )

    def test_actual_cybersecurity_plan_loop_allows_only_validated_generation_change(
        self,
    ):
        """Configuration integration; image/probe and owner custody stay separate."""
        root = Path(self.temp.name)
        for name in ("source.tar", "image.tar.gz", "compose.yaml"):
            (root / name).write_bytes(b"synthetic " + name.encode())
        self.binding.update(
            component="cybersecurity-api",
            target_environment="production",
            source_sha256=runner.sha(root / "source.tar"),
            build_sha256=runner.sha(root / "image.tar.gz"),
            artifact_digest="sha256:" + "e" * 64,
            configuration_sha256={},
        )
        self.plan.update(
            schema_version=1,
            mode="cybersecurity",
            baseline_runtime_sha256={},
            compose_sha256=runner.sha(root / "compose.yaml"),
            migration_revision="20261026_cybersecurity",
            probe_image="sha256:" + "f" * 64,
            physical_hardware_authorized=False,
            processing_scope="owned-synthetic-release-verification",
            legal_publication_controls_unchanged=True,
        )
        live, prepared, old = {}, {}, {}
        for environment in runner.ENV:
            values = {
                **self.original,
                "ONESA_ENVIRONMENT": environment,
                "ONESA_SECURE_COOKIES": "true",
                "ONESA_REGISTRATION_MODE": "invitation",
                "ONESA_DATABASE_URL": "postgresql://synthetic/" + environment,
                "ONESA_DIGITAL_TWINS_ENABLED": "false",
            }
            for collection, label, row in (
                (live, "live", values),
                (old, "old", values),
                (
                    prepared,
                    "prepared",
                    {**values, "ONESA_MODEL_NAME": runner.CURRENT_GENERATION},
                ),
            ):
                path = root / (label + "-" + environment + ".env")
                path.write_text(
                    "".join(key + "=" + value + "\n" for key, value in row.items())
                )
                collection[environment] = path
            self.binding["configuration_sha256"][environment] = runner.sha(
                prepared[environment]
            )
            self.retained["configuration_sha256"][environment] = runner.sha(
                old[environment]
            )
            self.plan["baseline_runtime_sha256"][environment] = runner.sha(
                live[environment]
            )
        image = {
            "Id": self.binding["artifact_digest"],
            "Architecture": "arm64",
            "Config": {
                "Labels": {
                    "org.opencontainers.image.revision": self.binding[
                        "candidate_commit"
                    ],
                    "org.onesa.source-archive-sha256": self.binding["source_sha256"],
                }
            },
        }
        probe = {
            "Id": self.plan["probe_image"],
            "Config": {
                "Labels": {
                    "org.opencontainers.image.revision": self.binding[
                        "candidate_commit"
                    ]
                }
            },
        }
        with (
            patch.object(runner, "ENV", live),
            patch.object(runner, "COMPOSE", root / "compose.yaml"),
            patch.object(runner, "artifact_folder", return_value=root),
            patch.object(
                runner,
                "read",
                side_effect=lambda path: (
                    {} if Path(path).name == "scan.json" else self.plan
                ),
            ),
            patch.object(
                runner,
                "candidate_environment",
                side_effect=lambda binding, env: (
                    prepared[env] if binding == self.binding else old[env]
                ),
            ),
            patch.object(runner, "require_probe_policy") as policy,
            patch.object(
                runner,
                "docker",
                side_effect=lambda *args: json.dumps(
                    [image if args[-1] == self.binding["artifact_digest"] else probe]
                ).encode(),
            ),
            patch.object(runner, "image_security"),
            patch.object(
                runner,
                "trusted_toolchain",
                return_value={"source_commit": self.binding["candidate_commit"]},
            ),
            patch.object(runner, "verify_application_bytes") as application,
            patch.object(runner, "verify_probe_bytes") as probe_bytes,
        ):
            self.assertEqual(runner.validate_plan(self.binding), (root, self.plan))
            self.assertEqual(policy.call_count, 2)
            application.assert_called_once()
            probe_bytes.assert_called_once()
            changed = runner.runtime_values(prepared["production"])
            changed["ONESA_MODEL_API_KEY"] = "different-synthetic-key"
            prepared["production"].write_text(
                "".join(key + "=" + value + "\n" for key, value in changed.items())
            )
            self.binding["configuration_sha256"]["production"] = runner.sha(
                prepared["production"]
            )
            with self.assertRaisesRegex(
                runner.Refused, "GENERATION_ONLY_CONFIGURATION"
            ):
                runner.validate_plan(self.binding)

    def test_rollback_config_tamper_and_expiring_retired_profile_fail_closed(self):
        with (
            patch.object(
                runner,
                "now",
                return_value=dt.datetime(2026, 11, 19, 0, 0, 1, tzinfo=dt.timezone.utc),
            ),
            self.assertRaisesRegex(runner.Refused, "SUPPORTED_ROLLBACK"),
        ):
            runner.generation_transition(
                self.plan, self.original, self.prepared, "production"
            )
        self.file.write_text(self.file.read_text() + "ONESA_NEW_PROVIDER=unreviewed\n")
        with self.assertRaisesRegex(runner.Refused, "ROLLBACK_CONFIGURATION_CHANGED"):
            runner.generation_transition(
                self.plan, self.original, self.prepared, "production"
            )

    def test_an_already_supported_bound_rollback_is_not_rejected_by_old_model_date(
        self,
    ):
        current = copy.deepcopy(self.original)
        self.original["ONESA_MODEL_NAME"] = runner.CURRENT_GENERATION
        self.seal()
        with patch.object(
            runner,
            "now",
            return_value=dt.datetime(2026, 11, 21, tzinfo=dt.timezone.utc),
        ):
            self.assertTrue(
                runner.generation_transition(
                    self.plan, current, self.prepared, "production"
                )
            )


if __name__ == "__main__":
    unittest.main()
