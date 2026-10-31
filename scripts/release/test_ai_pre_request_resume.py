"""Disposable negative proofs and real concurrent SQLite reservation checks."""

import copy
import hashlib
import json
import sqlite3
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import TestCase, main

import oracle_ai_pre_request_resume as extension


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


if __name__ == "__main__":
    main(verbosity=2)
