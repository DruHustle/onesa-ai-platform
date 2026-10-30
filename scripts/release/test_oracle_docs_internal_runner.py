"""Real-key private journals with disposable provider/native stand-ins only."""

import copy
import json
import os
import unittest
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import oracle_docs_internal_conditional as conditional
import oracle_docs_internal_runner as docs
import oracle_owner as owner
import test_oracle_owner as fixtures


class PrivateRunnerTests(unittest.TestCase):
    open = fixtures.OwnerStoreTests.open
    settings = fixtures.OwnerStoreTests.settings
    commission_fixture = fixtures.OwnerStoreTests.commission_fixture

    @classmethod
    def setUpClass(cls):
        fixtures.OwnerStoreTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.OwnerStoreTests.setUp(self)
        self.store.db.close()
        profile = self.policy["components"].pop("DruHustle/onesa-company-portal:api")
        profile["publication_mechanism"] = (
            "existing-isolated-owner-cloudflare-pages-cli"
        )
        self.binding.update(
            repository="DruHustle/onesa-ai-platform", component="docs-internal"
        )
        self.policy["components"]["DruHustle/onesa-ai-platform:docs-internal"] = profile
        (self.root / "policy.json").write_bytes(owner.canonical(self.policy))
        trust = json.loads((self.root / "trust.json").read_bytes())
        trust["policy_sha256"] = owner.file_digest(self.root / "policy.json")
        (self.root / "trust.json").write_bytes(owner.canonical(trust))
        self.commission_fixture()
        self.store = self.open()
        self.addCleanup(self.store.db.close)
        self.enterContext(patch.object(docs, "ROOT", self.root))
        private = owner.private
        self.enterContext(
            patch.object(
                docs.owner,
                "private",
                side_effect=lambda path, **kw: private(
                    path, **{"uid": os.getuid(), **kw}
                ),
            )
        )
        self.context = self.store.issue_context(self.binding)["record"]
        self.provider_id = str(uuid4())
        self.configuration = {
            "account_id": "a" * 32,
            "project_id": str(uuid4()),
            "team_origin": "https://fixture.cloudflareaccess.com",
        }
        self.spec = {
            "environment": "staging",
            "artifact": {
                "file_manifest_sha256": "b" * 64,
                "served_asset_paths": ["/", "/generated/provenance.json"],
            },
        }
        self.plan = {"provider": self.configuration}
        self.enterContext(patch.object(docs, "plan", return_value=self.plan))
        self.enterContext(
            patch.object(docs, "publication_spec", return_value=self.spec)
        )
        self.operation = self.store.put(
            "documentation-preview-intent", self.binding, {}
        )["record"]
        folder = docs.operation_folder(self.binding, self.operation["id"])
        folder.mkdir(mode=0o700, parents=True)
        self.intent = folder / "intent.json"
        self.intent.write_bytes(
            owner.canonical(
                {
                    "binding": self.binding,
                    "operation_id": self.operation["id"],
                    "prepared": self.spec,
                    "provider_create_budget": 1,
                    "automatic_retry": False,
                }
            )
        )
        self.intent.chmod(0o600)
        self.row = {
            "id": self.provider_id,
            "project_id": self.configuration["project_id"],
            "environment": "preview",
            "deployment_trigger": {
                "metadata": {
                    "commit_hash": self.binding["candidate_commit"],
                    "commit_message": "onesa-oracle:"
                    + self.operation["id"]
                    + ":"
                    + self.spec["artifact"]["file_manifest_sha256"],
                    "branch": "onesa-oracle-" + self.binding["candidate_commit"][:12],
                }
            },
            "latest_stage": {"name": "deploy", "status": "success"},
            "url": "https://"
            + self.provider_id[:8]
            + ".onesa-engineering-docs.pages.dev",
            "created_on": self.operation["issued_at"],
        }
        self.enterContext(
            patch.object(docs, "operation_matches", side_effect=lambda *_: [self.row])
        )
        self.provider_get = self.enterContext(
            patch.object(
                docs.provider, "get", side_effect=lambda *_: {"result": self.row}
            )
        )

    def observation(self):
        return docs.deployment_for(self.store, self.operation, production=False)

    def test_actual_provider_and_durable_source_artifact_are_required(self):
        actual = self.observation()
        self.assertEqual(actual["deployment_id"], self.provider_id)
        self.assertEqual(actual["source_revision"], self.binding["candidate_commit"])
        self.assertEqual(actual["asset_count"], 2)
        self.assertEqual(actual["target"], "preview")
        self.assertFalse(self.store.db.execute("SELECT * FROM deployments").fetchall())

    def test_wrong_provider_source_environment_artifact_readiness_or_time_refused(self):
        baseline = copy.deepcopy(self.row)
        changes = [
            lambda r: r.update(project_id=str(uuid4())),
            lambda r: r.update(environment="production"),
            lambda r: r.update(url="https://foreign.example.invalid"),
            lambda r: r["deployment_trigger"]["metadata"].update(commit_hash="c" * 40),
            lambda r: r["deployment_trigger"]["metadata"].update(commit_message="fake"),
            lambda r: r["deployment_trigger"]["metadata"].update(branch="main"),
            lambda r: r["latest_stage"].update(status="failure"),
            lambda r: r["latest_stage"].update(name="build"),
            lambda r: r.update(created_on=self.operation["expires_at"]),
            lambda r: r.update(
                created_on=(self.store.clock() - timedelta(days=1)).isoformat()
            ),
        ]
        for mutation in changes:
            self.row = copy.deepcopy(baseline)
            mutation(self.row)
            with self.subTest(row=self.row), self.assertRaises(owner.Rejected):
                self.observation()

    def test_changed_journal_is_never_rebound_to_new_source_or_retried(self):
        baseline = json.loads(self.intent.read_bytes())
        for key, value in [
            ("binding", {**self.binding, "candidate_commit": "c" * 40}),
            ("operation_id", str(uuid4())),
            ("prepared", {**self.spec, "environment": "production"}),
            ("provider_create_budget", 2),
            ("provider_create_budget", True),
            ("automatic_retry", True),
        ]:
            self.intent.write_bytes(owner.canonical({**baseline, key: value}))
            with self.subTest(key=key), self.assertRaises(owner.Rejected):
                self.observation()
        self.provider_get.assert_not_called()

    def test_conditional_inspection_preserves_records_and_has_no_authority(self):
        before = self.store.db.execute("SELECT count(*) FROM records").fetchone()[0]
        empty = conditional.inspect(self.store, self.context["id"])
        self.assertIsNone(empty["metadata_record_id"])
        self.assertEqual(
            self.store.db.execute("SELECT count(*) FROM records").fetchone()[0], before
        )
        metadata = self.store.put(
            conditional.METADATA,
            self.binding,
            {"metadata": {"synthetic_fixture": True}},
            parent=self.context["id"],
        )["record"]
        handed = self.store.put(
            conditional.HANDOFF,
            self.binding,
            {
                "metadata_record_id": metadata["id"],
                "conditional": {"authorization_run_id": 123},
            },
            parent=self.context["id"],
        )["record"]
        count = self.store.db.execute("SELECT count(*) FROM records").fetchone()[0]
        with patch.object(conditional, "verify", return_value={"synthetic": True}):
            actual = conditional.inspect(self.store, self.context["id"])
        self.assertEqual(actual["metadata_record_id"], metadata["id"])
        self.assertEqual(actual["handoff_record_id"], handed["id"])
        self.assertFalse(actual["production_deployment_authorized"])
        self.assertEqual(actual["provider_writes"], 0)
        self.assertEqual(
            self.store.db.execute("SELECT count(*) FROM records").fetchone()[0], count
        )
        self.store.revoke(metadata["id"])
        with self.assertRaises(owner.Rejected):
            conditional.inspect(self.store, self.context["id"])

    def test_qualification_phases_never_pass_a_missing_native_or_conditional_gate(self):
        prepared = {"custody": "private-owner-build-not-actions"}
        observed = {"id": str(uuid4())}
        with (
            patch.object(docs, "prepare", return_value=prepared),
            patch.object(docs, "project", return_value={}),
            patch.object(
                docs.native, "staging_observation", return_value=observed
            ) as native,
            patch.object(
                conditional, "current", return_value={"synthetic": True}
            ) as handoff,
            patch.object(
                docs, "preview_for_binding", return_value={"id": self.provider_id}
            ),
            patch.object(
                docs, "rollback_readiness", return_value={"synthetic": True}
            ) as rollback,
        ):
            for phase in ["staging", "operations"]:
                result = docs.runner(
                    self.store, phase, self.binding, {"context_id": self.context["id"]}
                )
                self.assertTrue(all(v == "PASS" for v in result["checks"].values()))
                self.assertEqual(type(result["workflow_run_id"]), int)
                self.assertEqual(result["workflow_run_id"], 0)
                self.assertEqual(result["native_observation_id"], observed["id"])
                for prerequisite in [native, handoff, rollback]:
                    prerequisite.side_effect = owner.Rejected("Synthetic failed gate")
                    with self.assertRaises(owner.Rejected):
                        docs.runner(
                            self.store,
                            phase,
                            self.binding,
                            {"context_id": self.context["id"]},
                        )
                    prerequisite.side_effect = None
        self.assertEqual(
            self.store.db.execute(
                "SELECT count(*) FROM records WHERE kind='qualification'"
            ).fetchone()[0],
            0,
        )


if __name__ == "__main__":
    unittest.main()
