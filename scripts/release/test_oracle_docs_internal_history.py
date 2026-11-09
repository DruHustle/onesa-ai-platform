"""Real signed, retained private journals across different verifier versions.

Only disposable keys, Git trees and provider observations are used. The original
verifier contains an execution trap: historical inspection must treat it as data.
"""

import base64
import copy
import hashlib
import json
import os
import subprocess
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import oracle_docs_internal_history as history
import oracle_docs_internal_publish as publish
import oracle_docs_internal_runner as docs
import oracle_install as installer
import oracle_owner as owner
import test_oracle_canonical_application as application
import test_oracle_owner as owner_fixture


def write(path, value):
    path.write_bytes(value if isinstance(value, bytes) else owner.canonical(value))
    path.chmod(0o600)


class HistoricalPrivateJournalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        owner_fixture.OwnerStoreTests.setUpClass()

    def fixture(self, *, canonical=False):
        f = owner_fixture.OwnerStoreTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.store.db.close()
        mapping = dict(installer.PRIVATE_DOCS_ALLOWED)
        if not canonical:
            # Both retained original installers predate these three helpers.
            for name in (
                "runners/oracle_identity_rollback.py",
                "runners/oracle_docs_internal_canonical.py",
                "runners/oracle_docs_internal_history.py",
            ):
                mapping.pop(name)
        product = Path(__file__).resolve().parents[2]
        files = {
            upstream: (product / upstream).read_bytes() for upstream in mapping.values()
        }
        files["scripts/release/oracle_owner.py"] += (
            b"\nraise AssertionError('retained verifier must never execute')\n"
        )
        files["onesa-ai-platform-backend/app/twin_files.py"] = b"# retained fixture\n"
        source_root = f.root / "original-source"
        source_root.mkdir(mode=0o700)
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
        archive = subprocess.check_output(
            ["git", "-C", str(source_root), "archive", tree]
        )
        archive_pin = hashlib.sha256(archive).hexdigest()
        f.binding.update(
            repository="DruHustle/onesa-ai-platform",
            component="docs-internal",
            source_tree=tree,
            source_sha256=archive_pin,
        )
        tool = {
            "source_commit": f.binding["candidate_commit"],
            "source_tree": tree,
            "source_sha256": archive_pin,
        }
        if canonical:
            source_fixture = application.SourceFixture(
                owner, product="platform", branch="main"
            )
            source = source_fixture.source
            source["product_source_tree"] = tree
            f.binding.update(source)
            tool.update(
                source_commit=source["candidate_commit"],
                source_tree=source["source_tree"],
                source_binding=copy.deepcopy(source),
                source_archives=application.pins(source_fixture),
            )
        parent = f.root / "installations"
        parent.mkdir(mode=0o700)
        directory = parent / (
            ("ai-docs-internal-canonical-" if canonical else "ai-docs-internal-")
            + tool["source_tree"]
        )
        directory.mkdir(mode=0o700)
        (directory / "runners").mkdir(mode=0o700)
        pins = {}
        for local, upstream in mapping.items():
            write(directory / local, files[upstream])
            pins[local] = owner.file_digest(directory / local)
        write(directory / "tool-source.tar", archive)
        profile = copy.deepcopy(next(iter(f.policy["components"].values())))
        profile.update(
            qualification_attempt_limit=1,
            publication_mechanism="existing-isolated-owner-cloudflare-pages-cli",
        )
        for phase in profile["runners"].values():
            phase.update(
                path=str(directory / "runners/oracle_docs_internal_runner.py"),
                sha256=pins["runners/oracle_docs_internal_runner.py"],
            )
        f.policy = {
            "schema_version": 2 if canonical else 1,
            "components": {owner.component_scope(f.binding): profile},
            "toolchain": tool,
        }
        for path in (f.root / "policy.json", directory / "policy.json"):
            write(path, f.policy)
        trust = json.loads((f.root / "trust.json").read_bytes())
        trust.update(
            policy_sha256=owner.file_digest(f.root / "policy.json"),
            verifier_sha256=pins["oracle_owner.py"],
            runner_root=str(directory / "runners"),
        )
        write(f.root / "trust.json", trust)
        receipt = {
            "state": "INSTALLED_NOT_COMMISSIONED",
            "repository": f.binding["repository"],
            "source": tool["source_commit"],
            "source_tree": tool["source_tree"],
            "policy_sha256": trust["policy_sha256"],
            "files": pins,
            "provider_requests": 0,
        }
        if canonical:
            receipt["source_binding"] = copy.deepcopy(tool["source_binding"])
        write(directory / "installation.json", receipt)
        f.commission_fixture()
        # The test signer uses a real key and the old provenance. It never
        # imports the deliberately non-executable retained source.
        with patch.object(owner, "__file__", str(directory / "oracle_owner.py")):
            f.store = f.open()
        self.addCleanup(f.store.db.close)
        f.store.clock = lambda: owner.timestamp() - timedelta(days=7)
        self.enterContext(patch.object(installer, "INSTALL_PARENT", parent))
        f.directory, f.receipt = directory, receipt
        f.journal_root = f.root / "project-journals"
        f.journal_root.mkdir(mode=0o700)
        self.enterContext(patch.object(docs, "ROOT", f.journal_root))
        return f

    def journal(self, f, *, production=True, accepted=True):
        s, b = f.store, f.binding
        context = s.put("context", b, {"ci": [{"run_id": 123}]})["record"]
        qualification = s.put("qualification", b, {}, parent=context["id"])["record"]
        attempt = s.put(
            "authorization-attempt",
            b,
            {"decision": "PENDING"},
            parent=qualification["id"],
        )["record"]
        authorization = s.put(
            "authorization",
            b,
            {
                "decision": "approve",
                "physical_hardware_authorized": False,
                "attempt_id": attempt["id"],
            },
            parent=qualification["id"],
        )["record"]
        kind = "deployment-intent" if production else "documentation-preview-intent"
        operation = s.put(
            kind,
            b,
            {"provider_request_budget": 1, "automatic_retry": False},
            parent=authorization["id"] if production else context["id"],
        )["record"]
        provider_id = str(uuid4())
        if production:
            s.db.execute(
                "INSERT INTO deployments(id,authorization,qualification,state) VALUES(?,?,?,?)",
                (
                    operation["id"],
                    authorization["id"],
                    qualification["id"],
                    "accepted" if accepted else "request-recorded",
                ),
            )
            if accepted:
                observations = {
                    "deployment_id": provider_id,
                    "operation_id": operation["id"],
                    "binding": b,
                    "environment": "production",
                    "workflow_run_id": 0,
                }
                s.put(
                    "deployment-receipt",
                    b,
                    {"observations": observations},
                    parent=operation["id"],
                )
                s.put(
                    "production-verification",
                    b,
                    {"observations": observations},
                    parent=operation["id"],
                )
        prepared = {
            "environment": "production" if production else "staging",
            "project_id": str(uuid4()),
            "artifact": {"file_manifest_sha256": "d" * 64},
        }
        folder = (
            f.journal_root
            / "artifacts"
            / b["source_tree"]
            / "operations"
            / operation["id"]
        )
        folder.mkdir(mode=0o700, parents=True)
        intent = {
            "binding": b,
            "operation_id": operation["id"],
            "verifier_store": str(f.root),
            "prepared": prepared,
            "provider_create_budget": 1,
            "automatic_retry": False,
        }
        write(folder / "intent.json", intent)
        row = {
            "id": provider_id,
            "project_id": prepared["project_id"],
            "environment": "production" if production else "preview",
            "deployment_trigger": {
                "metadata": {
                    "commit_hash": b["candidate_commit"],
                    "commit_message": "onesa-oracle:"
                    + operation["id"]
                    + ":"
                    + "d" * 64,
                    "branch": "main"
                    if production
                    else "onesa-oracle-" + b["candidate_commit"][:12],
                }
            },
            "latest_stage": {"name": "deploy", "status": "success"},
        }
        f.operation, f.context, f.row, f.intent = operation, context, row, intent
        f.intent_path = folder / "intent.json"
        return operation

    def inspect(self, f):
        return history.operation(
            f.root, f.binding, f.operation["id"], f.operation["kind"], uid=os.getuid()
        )

    def retained(self, f, rows=None):
        # The new publisher's shared project journal includes original stores.
        current = SimpleNamespace(root=f.root, uid=os.getuid())
        with patch.object(
            docs, "operation_matches", return_value=[f.row] if rows is None else rows
        ):
            return publish.inspect_retained(current)

    def test_original_and_canonical_signed_history_survives_new_verifier_without_authority(
        self,
    ):
        for canonical in (False, True):
            with self.subTest(canonical=canonical):
                f = self.fixture(canonical=canonical)
                self.journal(f)
                before = {
                    name: owner.file_digest(f.root / name)
                    for name in (
                        "signing.pem",
                        "public.pem",
                        "policy.json",
                        "trust.json",
                        "records.sqlite",
                        "fixture-anchor.json",
                    )
                }
                with self.assertRaisesRegex(
                    owner.Rejected, "Commissioned verifier/policy/key pin changed"
                ):
                    f.open()
                read_bytes = Path.read_bytes

                def no_signing_key(path, reader=read_bytes):
                    self.assertNotEqual(path.name, "signing.pem")
                    return reader(path)

                with (
                    patch.object(
                        owner, "Store", side_effect=AssertionError("no issuing Store")
                    ),
                    patch.object(
                        publish.system,
                        "docker",
                        side_effect=AssertionError("no provider writes"),
                    ),
                    patch.object(Path, "read_bytes", no_signing_key),
                ):
                    observed = self.inspect(f)
                    rows = self.retained(f)
                self.assertTrue(observed["historical_only"])
                self.assertFalse(observed["release_authorized"])
                self.assertEqual(observed["accepted_deployment_id"], f.row["id"])
                self.assertEqual(rows[0]["provider_writes"], 0)
                self.assertEqual(
                    before, {name: owner.file_digest(f.root / name) for name in before}
                )
                self.assertEqual(json.loads(f.intent_path.read_bytes()), f.intent)

    def test_original_unresolved_or_unaccepted_request_holds_new_publisher(self):
        f = self.fixture()
        self.journal(f, accepted=False)
        for rows in ([], [f.row, f.row], [f.row]):
            with self.subTest(rows=len(rows)), self.assertRaises(owner.Rejected):
                self.retained(f, rows)
        f.row["latest_stage"]["status"] = "active"
        with self.assertRaisesRegex(owner.Rejected, "STILL_ACTIVE"):
            self.retained(f)
        self.assertTrue(f.intent_path.exists())
        self.assertEqual(
            f.store.db.execute("SELECT state FROM deployments").fetchone()[0],
            "request-recorded",
        )

    def test_terminal_failed_preview_remains_history_and_never_becomes_a_grant(self):
        f = self.fixture()
        self.journal(f, production=False)
        f.store.db.execute(
            "UPDATE records SET revoked=1 WHERE id=?", (f.context["id"],)
        )
        f.row["latest_stage"]["status"] = "failure"
        observed = self.inspect(f)
        self.assertIsNone(observed["state"])
        self.assertFalse(observed["release_authorized"])
        self.assertEqual(self.retained(f)[0]["state"], "failure")

    def test_accepted_original_revoked_ancestor_or_changed_provider_receipt_still_holds(
        self,
    ):
        f = self.fixture()
        self.journal(f)
        f.store.db.execute(
            "UPDATE records SET revoked=1 WHERE id=?", (f.context["id"],)
        )
        with self.assertRaisesRegex(owner.Rejected, "ACCEPTANCE_REVOKED_OR_CHANGED"):
            self.retained(f)
        f.store.db.execute("UPDATE records SET revoked=0")
        f.row["id"] = str(uuid4())
        with self.assertRaisesRegex(owner.Rejected, "OBSERVATION_FIRST"):
            self.retained(f)

    def test_original_anchor_key_policy_source_helper_and_receipt_custody_stay_required(
        self,
    ):
        f = self.fixture()
        self.journal(f)
        for path in (
            f.anchor,
            f.root / "public.pem",
            f.root / "policy.json",
            f.directory / "policy.json",
            f.directory / "tool-source.tar",
            f.directory / "oracle_owner.py",
            f.directory / "runners/oracle_docs_internal_runner.py",
        ):
            raw = path.read_bytes()
            if path == f.anchor:
                changed = json.loads(raw)
                changed["installations"][str(f.root)]["active"] = False
                write(path, changed)
            else:
                write(path, raw + b"\nchanged\n")
            with (
                self.subTest(path=path.name),
                self.assertRaises((owner.Rejected, ValueError)),
            ):
                self.inspect(f)
            write(path, raw)
        for key, value in (
            ("source_tree", "f" * 40),
            ("source", "e" * 40),
            ("policy_sha256", "0" * 64),
            ("repository", "DruHustle/onesa-robot"),
        ):
            write(f.directory / "installation.json", {**f.receipt, key: value})
            with self.subTest(field=key), self.assertRaises(owner.Rejected):
                self.inspect(f)
        for path in ("../oracle_owner.py", "/foreign/helper.py", "runners/unknown.py"):
            changed = copy.deepcopy(f.receipt)
            changed["files"][path] = "a" * 64
            write(f.directory / "installation.json", changed)
            with self.subTest(path=path), self.assertRaises(owner.Rejected):
                self.inspect(f)
        changed = copy.deepcopy(f.receipt)
        changed["files"].pop("runners/oracle_docs_internal_provider.py")
        write(f.directory / "installation.json", changed)
        with self.assertRaises(owner.Rejected):
            self.inspect(f)

    def test_signed_index_signature_source_and_private_scope_cannot_be_substituted(
        self,
    ):
        f = self.fixture(canonical=True)
        self.journal(f)
        identifier = f.operation["id"]
        original = f.store.db.execute(
            "SELECT envelope FROM records WHERE id=?", (identifier,)
        ).fetchone()[0]
        for mutation in (
            lambda v: v["record"]["binding"].update(component="docs-public"),
            lambda v: v["signature"].update(key_id="0" * 64),
            lambda v: v["record"].update(workflow_run_id=123),
        ):
            value = json.loads(original)
            mutation(value)
            f.store.db.execute(
                "UPDATE records SET envelope=? WHERE id=?",
                (owner.canonical(value).decode(), identifier),
            )
            with self.assertRaises(owner.Rejected):
                self.inspect(f)
        f.store.db.execute(
            "UPDATE records SET envelope=? WHERE id=?", (original, identifier)
        )
        for component, product in (
            ("docs-public", "platform"),
            ("api", "platform"),
            ("docs-internal", "portal"),
        ):
            binding = {**f.binding, "component": component, "product": product}
            with (
                self.subTest(component=component, product=product),
                self.assertRaises(owner.Rejected),
            ):
                history.operation(
                    f.root, binding, identifier, "deployment-intent", uid=os.getuid()
                )
        f.store.db.execute(
            "UPDATE records SET scope='foreign' WHERE id=?", (identifier,)
        )
        with self.assertRaisesRegex(owner.Rejected, "SIGNED_INDEX_OR_SOURCE_CHANGED"):
            self.inspect(f)

    def test_original_intent_and_provider_source_environment_project_remain_bound(self):
        f = self.fixture()
        self.journal(f)
        original_row = copy.deepcopy(f.row)
        changes = [
            lambda r: r.update(project_id=str(uuid4())),
            lambda r: r.update(environment="preview"),
            lambda r: r["deployment_trigger"]["metadata"].update(commit_hash="e" * 40),
            lambda r: r["deployment_trigger"]["metadata"].update(
                commit_message="changed"
            ),
            lambda r: r["deployment_trigger"]["metadata"].update(branch="other"),
            lambda r: r["latest_stage"].update(name="build"),
        ]
        for change in changes:
            f.row = copy.deepcopy(original_row)
            change(f.row)
            with self.assertRaises(owner.Rejected):
                self.retained(f)
        f.row = original_row
        for key, value in (
            ("operation_id", str(uuid4())),
            ("automatic_retry", True),
            ("provider_create_budget", True),
            ("provider_create_budget", 2),
        ):
            write(f.intent_path, {**f.intent, key: value})
            with (
                self.subTest(field=key),
                self.assertRaisesRegex(owner.Rejected, "DURABLE_INTENT_CHANGED"),
            ):
                self.retained(f)

    def test_signed_acceptance_without_exact_receipt_or_with_cycle_is_not_terminal_proof(
        self,
    ):
        f = self.fixture()
        self.journal(f)
        receipt = f.store.db.execute(
            "SELECT id FROM records WHERE kind='deployment-receipt'"
        ).fetchone()[0]
        f.store.db.execute("DELETE FROM records WHERE id=?", (receipt,))
        with self.assertRaisesRegex(owner.Rejected, "PROVIDER_RECEIPT_MISSING"):
            self.inspect(f)
        # A correctly signed self-parent still cannot turn into an infinite read.
        original = f.store.db.execute(
            "SELECT envelope FROM records WHERE id=?", (f.operation["id"],)
        ).fetchone()[0]
        value = json.loads(original)
        value["record"]["parent"] = f.operation["id"]
        value["signature"]["value"] = base64.b64encode(
            owner.signed_bytes(
                f.root / "signing.pem",
                f.root / "public.pem",
                owner.canonical(value["record"]),
            )
        ).decode()
        f.store.db.execute(
            "UPDATE records SET envelope=?,parent=? WHERE id=?",
            (owner.canonical(value).decode(), f.operation["id"], f.operation["id"]),
        )
        with self.assertRaisesRegex(owner.Rejected, "CHAIN_CYCLE_OR_BOUND"):
            self.inspect(f)


if __name__ == "__main__":
    unittest.main()
