"""Actual temporary signed-ledger scope tests; never hosted release authority."""

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import oracle_ai_runner as runner
import oracle_owner as owner
import oracle_release_profiles as profiles
import test_oracle_owner as fixtures


class ProfileLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.OwnerStoreTests.setUpClass()

    def setUp(self):
        self.fixture = fixtures.OwnerStoreTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        template = copy.deepcopy(next(iter(f.policy["components"].values())))
        f.store.db.close()
        f.binding["repository"] = profiles.REPOSITORY
        f.policy["components"] = {}
        for name, (_kind, mode) in profiles.PROFILES.items():
            profile = copy.deepcopy(template)
            profile.update(qualification_attempt_limit=1, release_mode=mode)
            f.policy["components"][profiles.REPOSITORY + ":" + name] = profile
        profiles.policy_components(f.policy)
        (f.root / "policy.json").write_bytes(owner.canonical(f.policy))
        trust = json.loads((f.root / "trust.json").read_bytes())
        trust["policy_sha256"] = owner.file_digest(f.root / "policy.json")
        (f.root / "trust.json").write_bytes(owner.canonical(trust))
        f.store = f.open()
        f.addCleanup(f.store.db.close)

    def binding(self, name):
        return {**self.fixture.binding, "component": name}

    def test_each_fixed_scope_gets_one_unique_context_without_configuration_renewal(
        self,
    ):
        store = self.fixture.store
        contexts = {
            name: store.issue_context(self.binding(name))["record"]["id"]
            for name in profiles.SCOPED
        }
        self.assertEqual(len(set(contexts.values())), 6)
        for name in profiles.SCOPED:
            changed = self.binding(name)
            changed["configuration_sha256"] = {
                "staging": "2" * 64,
                "production": "3" * 64,
            }
            with self.subTest(component=name), self.assertRaises(owner.Rejected):
                store.issue_context(changed)
        q = store.qualify(contexts["twins-api"])
        self.assertEqual(q["record"]["binding"]["component"], "twins-api")
        self.assertEqual(q["record"]["workflow_run_id"], 0)
        self.assertEqual(q["record"]["details"]["ci"][0]["run_id"], 123)
        with self.assertRaises(owner.Rejected):
            store.qualify(contexts["twins-api"])
        with self.assertRaises(owner.Rejected):
            store.get(
                contexts["twins-api"], "context", self.binding("cybersecurity-api")
            )
        states = dict(store.db.execute("SELECT id,state FROM contexts"))
        self.assertEqual(states[contexts["twins-api"]], "consumed")
        self.assertTrue(
            all(
                states[value] == "issued"
                for name, value in contexts.items()
                if name != "twins-api"
            )
        )

    def test_changed_source_after_context_reservation_never_qualifies(self):
        store = self.fixture.store
        context = store.issue_context(self.binding("cybersecurity-api"))["record"]["id"]
        self.fixture.ci.source = "b" * 40
        with self.assertRaises(owner.Rejected):
            store.qualify(context)
        self.assertEqual(
            store.db.execute(
                "SELECT state FROM contexts WHERE id=?", (context,)
            ).fetchone()[0],
            "reserved",
        )
        self.assertEqual(
            store.db.execute(
                "SELECT count(*) FROM records WHERE kind='qualification'"
            ).fetchone()[0],
            0,
        )

    def test_accepted_rollback_uses_its_original_commissioned_store_without_transfer(
        self,
    ):
        f = self.fixture
        binding = self.binding("api")
        context = f.store.issue_context(binding)["record"]["id"]
        qualification = f.store.qualify(context)["record"]["id"]
        authorization = f.store.authorize(qualification)["record"]["id"]
        accepted = f.store.deploy(authorization)
        operation = accepted["record"]["parent"]
        root = f.root / "artifact-root"
        folder = profiles.artifact_folder(binding, root) / "observations" / context
        folder.mkdir(parents=True, mode=0o700)
        proof = {
            "binding": binding,
            "operation_id": context,
            "candidate_image": binding["artifact_digest"],
            "status": "PASS",
            "synthetic_database_restore": "PASS",
            "twins_disabled": True,
            "cybersecurity_disabled": True,
            "schema_revision": "20261026_cybersecurity",
            "production_writes": 0,
        }
        path = folder / "forward-check-receipt.json"
        path.write_bytes(owner.canonical(proof))
        trust = json.loads((f.root / "trust.json").read_bytes())
        registry = {"installations": {str(f.root): {**trust, "active": True}}}
        new_binding = {**self.binding("twins-api"), "candidate_commit": "b" * 40}
        plan = {
            "binding": new_binding,
            "verifier_store": str(f.root / "new-store-not-an-approval"),
            "mode": "twins",
            "rollback": {
                "binding": binding,
                "image": binding["artifact_digest"],
                "operation_id": operation,
                "verifier_store": str(f.root),
            },
        }
        count = f.store.db.execute("SELECT count(*) FROM records").fetchone()[0]
        with (
            patch.object(runner, "ROOT", root),
            patch.object(runner, "private", side_effect=lambda p, **kw: Path(p)),
            patch.object(
                runner,
                "read",
                side_effect=lambda p: (
                    registry
                    if str(p) == "/etc/onesa/oracle-release-trust.json"
                    else json.loads(Path(p).read_bytes())
                ),
            ),
        ):
            self.assertEqual(
                runner.accepted_rollback_proof(plan), owner.file_digest(path)
            )
            self.assertEqual(
                f.store.db.execute("SELECT count(*) FROM records").fetchone()[0], count
            )
            for key, value in [
                ("repository", "DruHustle/onesa-company-portal"),
                ("target_environment", "staging"),
                ("candidate_commit", "b" * 40),
                ("artifact_digest", "sha256:" + "9" * 64),
            ]:
                changed = copy.deepcopy(plan)
                changed["rollback"]["binding"][key] = value
                with self.subTest(key=key), self.assertRaises(ValueError):
                    runner.accepted_rollback_proof(changed)
            registry["installations"][str(f.root)]["active"] = False
            with self.assertRaises(runner.Refused):
                runner.accepted_rollback_proof(plan)
            registry["installations"][str(f.root)]["active"] = True
            f.store.revoke(context)
            with self.assertRaises(runner.Refused):
                runner.accepted_rollback_proof(plan)


if __name__ == "__main__":
    unittest.main()
