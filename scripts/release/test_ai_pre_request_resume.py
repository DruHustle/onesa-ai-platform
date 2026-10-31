"""Disposable negative proofs and real concurrent SQLite reservation checks."""

import copy
import hashlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import Mock, patch

import oracle_ai_pre_request_resume as extension
import oracle_ai_runner as runner
import oracle_owner as owner


class ZeroRequestTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="onesa-zero-request-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "plan.json"
        self.actual = {"image": "retained-image", "container_id": "retained-container"}
        self.plan = {"baseline": {"production": self.actual.copy()}}
        self.path.write_text(json.dumps(self.plan))
        self.config = {
            "plan": str(self.path),
            "plan_sha256": hashlib.sha256(self.path.read_bytes()).hexdigest(),
            "binding": {"candidate_commit": "a" * 40},
            "operation": "existing-operation",
            "authorization": "existing-authorization",
            "failure_sha256": "f" * 64,
        }
        self.failure = {
            "phase": "deploy",
            "status": "FAILED_NOT_QUALIFIED",
            "diagnostic_only": True,
            "provider_retry_allowed": False,
            "failure_code": "OPERATIONS_ALERT_OR_UNQUALIFIED_SAMPLE",
            "candidate_commit": "a" * 40,
            "component": "api",
            "record_ids": {
                "authorization_id": "existing-authorization",
                "operation_id": "existing-operation",
            },
            "observed_at": "2026-10-31T00:14:20+00:00",
        }

    def proof(self, **kwargs):
        return extension.zero_request_evidence(
            self.config,
            self.plan,
            self.failure,
            operation_exists=False,
            actual=self.actual,
            **kwargs,
        )

    def test_proves_zero_calls_without_issuing_authority(self):
        proof = self.proof()
        self.assertEqual(proof["prior_provider_requests"], 0)
        self.assertTrue(proof["provider_operation_directory_absent"])

    def test_any_operation_directory_blocks_continuation(self):
        with self.assertRaisesRegex(ValueError, "INSPECTION_ONLY"):
            extension.zero_request_evidence(
                self.config,
                self.plan,
                self.failure,
                operation_exists=True,
                actual=self.actual,
            )

    def test_changed_plan_blocks_continuation(self):
        self.path.write_text("modified")
        with self.assertRaisesRegex(ValueError, "SELECTED_PLAN_CHANGED"):
            self.proof()

    def test_changed_running_production_blocks_continuation(self):
        with self.assertRaisesRegex(ValueError, "PRODUCTION_CHANGED"):
            extension.zero_request_evidence(
                self.config,
                self.plan,
                self.failure,
                operation_exists=False,
                actual={"image": "different"},
            )

    def test_wrong_source_component_phase_or_intent_cannot_claim_zero(self):
        for key, value in [
            ("candidate_commit", "b" * 40),
            ("component", "frontend"),
            ("phase", "production"),
            ("diagnostic_only", False),
            ("provider_retry_allowed", True),
            (
                "record_ids",
                {"authorization_id": "other", "operation_id": "existing-operation"},
            ),
        ]:
            old = copy.deepcopy(self.failure)
            self.failure[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.proof()
            self.failure = old

    def test_post_request_or_unknown_failure_is_refused(self):
        self.failure["failure_code"] = (
            "PROVIDER_REQUEST_NOT_ACCEPTED_INSPECT_EXISTING_OPERATION"
        )
        with self.assertRaisesRegex(ValueError, "ONLY_PROVEN_PRE_REQUEST"):
            self.proof()


class AtomicClaimTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="onesa-resume-claim-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "fixture.sqlite"
        with sqlite3.connect(self.path) as db:
            db.executescript(
                "CREATE TABLE deployments(id TEXT PRIMARY KEY,state TEXT); CREATE TABLE records(id INTEGER PRIMARY KEY,kind TEXT,parent TEXT); INSERT INTO deployments VALUES('operation','request-recorded');"
            )

    def connect(self):
        return sqlite3.connect(self.path, timeout=5, isolation_level=None)

    def reserve(self, db):
        def create():
            db.execute(
                "INSERT INTO records(kind,parent) VALUES('pre-request-resume-attempt','operation')"
            )
            return {"fixture": True}

        return extension.claim(db, "operation", create)

    def test_single_reservation_survives_interrupted_client(self):
        db = self.connect()
        self.reserve(db)
        db.close()
        db = self.connect()
        try:
            with self.assertRaisesRegex(ValueError, "ALREADY_RESERVED"):
                self.reserve(db)
        finally:
            db.close()

    def test_two_simultaneous_attempts_reserve_only_once(self):
        barrier = threading.Barrier(2)

        def attempt(_):
            db = self.connect()
            try:
                barrier.wait(timeout=5)
                self.reserve(db)
                return "reserved"
            except ValueError:
                return "refused"
            finally:
                db.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertCountEqual(results, ["reserved", "refused"])
        with self.connect() as db:
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM records").fetchone(), (1,)
            )

    def test_deployed_or_accepted_state_never_reserves(self):
        for state in ["deployed-unverified", "accepted"]:
            db = self.connect()
            try:
                db.execute("UPDATE deployments SET state=?", (state,))
                with (
                    self.subTest(state=state),
                    self.assertRaisesRegex(ValueError, "NOT_UNISSUED"),
                ):
                    self.reserve(db)
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM records").fetchone(), (0,)
                )
            finally:
                db.close()

    def test_failed_record_signing_rolls_back_before_execution(self):
        db = self.connect()
        try:

            def failure():
                db.execute(
                    "INSERT INTO records(kind,parent) VALUES('pre-request-resume-attempt','operation')"
                )
                raise RuntimeError("fixture-signing-failed")

            with self.assertRaises(RuntimeError):
                extension.claim(db, "operation", failure)
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM records").fetchone(), (0,)
            )
        finally:
            db.close()


class PreflightDecisionTests(TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.addCleanup(self.db.close)
        self.db.executescript(
            "CREATE TABLE deployments(id TEXT PRIMARY KEY,state TEXT);"
            "CREATE TABLE contexts(id TEXT PRIMARY KEY,state TEXT);"
            "CREATE TABLE records(sequence INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT,kind TEXT,scope TEXT,parent TEXT);"
            "INSERT INTO deployments VALUES('operation','request-recorded');"
            "INSERT INTO contexts VALUES('context','consumed');"
            "INSERT INTO records(id,kind,scope) VALUES('original-attempt','authorization-attempt','DruHustle/onesa-ai-platform:api');"
        )
        self.binding = {
            "repository": "DruHustle/onesa-ai-platform",
            "component": "api",
            "candidate_commit": "a" * 40,
        }
        self.records = {
            "operation": {
                "id": "operation",
                "parent": "authorization",
                "details": {
                    "authorization": "authorization",
                    "provider_request_budget": 1,
                    "automatic_retry": False,
                },
            },
            "authorization": {
                "id": "authorization",
                "parent": "qualification",
                "details": {"attempt_id": "original-attempt"},
            },
            "qualification": {"id": "qualification", "parent": "context"},
        }
        self.revoked = False
        self.reads = []

        def get(identifier, _kind, binding):
            self.assertEqual(binding, self.binding)
            self.reads.append((identifier, self.db.in_transaction))
            if identifier == "authorization" and self.revoked:
                raise owner.Rejected("synthetic signed authorization revoked")
            return {"record": copy.deepcopy(self.records[identifier])}

        self.store = SimpleNamespace(
            root=self.root,
            db=self.db,
            get=Mock(side_effect=get),
            put=Mock(),
            github=SimpleNamespace(qualify=Mock()),
            runner=Mock(),
        )
        actual = {"image": "retained-image", "container_id": "retained-container"}
        plan = {
            "mode": "foundation",
            "verifier_store": str(self.root),
            "baseline": {"production": actual},
        }
        plan_path = self.root / "plan.json"
        plan_path.write_text(json.dumps(plan))
        failure = {
            "phase": "deploy",
            "status": "FAILED_NOT_QUALIFIED",
            "diagnostic_only": True,
            "provider_retry_allowed": False,
            "failure_code": "OPERATIONS_ALERT_OR_UNQUALIFIED_SAMPLE",
            "candidate_commit": self.binding["candidate_commit"],
            "component": "api",
            "record_ids": {
                "authorization_id": "authorization",
                "operation_id": "operation",
            },
            "observed_at": "2026-10-31T00:14:20+00:00",
        }
        failure_path = self.root / "failure.json"
        failure_path.write_text(json.dumps(failure))
        config = {
            "store": str(self.root),
            "installation": str(self.root),
            "files": {},
            "binding": self.binding,
            "operation": "operation",
            "authorization": "authorization",
            "qualification": "qualification",
            "plan": str(plan_path),
            "plan_sha256": extension.digest(plan_path),
            "failure": str(failure_path),
            "failure_sha256": extension.digest(failure_path),
        }
        config_path = self.root / "config.json"
        config_path.write_text(json.dumps(config))
        registry_path = self.root / "synthetic-registry.json"
        registry_path.write_text(
            json.dumps(
                {
                    "installations": {
                        str(self.root): {
                            "active": True,
                            "pre_request_resume": {
                                "active": True,
                                "path": str(Path(extension.__file__).resolve()),
                                "sha256": extension.digest(extension.__file__),
                                "configuration": str(config_path),
                                "configuration_sha256": extension.digest(config_path),
                            },
                        }
                    }
                }
            )
        )
        # Real command/preflight/reservation code, disposable custody and no token,
        # commissioning registry, production filesystem or provider access.
        self.enterContext(
            patch.object(
                extension,
                "private",
                side_effect=lambda path, **_: (
                    registry_path
                    if str(path) == "/etc/onesa/oracle-release-trust.json"
                    else Path(path)
                ),
            )
        )
        self.enterContext(patch.object(os, "geteuid", return_value=0))
        self.enterContext(
            patch.dict(os.environ, {"SUDO_USER": "ubuntu", "GITHUB_ACTIONS": ""})
        )
        self.enterContext(
            patch.object(sys, "argv", ["resume", "execute", "--store", str(self.root)])
        )
        self.enterContext(
            patch.object(sys, "stdin", io.StringIO('{"owner_token":"synthetic-only"}'))
        )
        self.enterContext(patch.object(sys, "path", list(sys.path)))
        self.enterContext(patch.object(owner, "Store", return_value=self.store))
        self.enterContext(patch.object(owner, "GitHub"))
        self.enterContext(
            patch.object(runner, "validate_plan", return_value=(self.root, plan))
        )
        self.enterContext(
            patch.object(
                runner, "inventory", return_value={runner.TARGET["production"]: actual}
            )
        )
        self.enterContext(
            patch.object(runner, "summary", side_effect=lambda value: value)
        )
        self.enterContext(
            patch.object(
                runner, "read", return_value={"checked_at": "2026-10-31T00:21:00+00:00"}
            )
        )

    def assert_no_reservation_or_provider_call(self):
        self.store.put.assert_not_called()
        self.assertEqual(
            [call.args[0] for call in self.store.runner.call_args_list], ["operations"]
        )
        self.assertEqual(
            self.db.execute("SELECT state FROM deployments").fetchone(),
            ("request-recorded",),
        )
        self.assertEqual(
            self.db.execute("SELECT state FROM contexts").fetchone(), ("consumed",)
        )
        self.assertEqual(
            self.db.execute(
                "SELECT count(*) FROM records WHERE kind='pre-request-resume-attempt'"
            ).fetchone(),
            (0,),
        )
        self.assertFalse(self.db.in_transaction)

    def test_owner_decision_during_ci_preflight_blocks_reservation_and_provider(self):
        def supersede(_binding):
            self.db.execute(
                "INSERT INTO records(id,kind,scope) VALUES('newer-attempt','authorization-attempt','DruHustle/onesa-ai-platform:api')"
            )

        self.store.github.qualify.side_effect = supersede
        with self.assertRaisesRegex(ValueError, "OWNER_DECISION_SUPERSEDED"):
            extension.main()
        self.assert_no_reservation_or_provider_call()
        for identifier in self.records:
            self.assertIn((identifier, True), self.reads)

    def test_revocation_during_operations_preflight_revalidates_signed_chain(self):
        def revoke(*_):
            self.revoked = True

        self.store.runner.side_effect = revoke
        with self.assertRaisesRegex(owner.Rejected, "authorization revoked"):
            extension.main()
        self.assert_no_reservation_or_provider_call()
        self.assertIn(("authorization", True), self.reads)


if __name__ == "__main__":
    main(verbosity=2)
