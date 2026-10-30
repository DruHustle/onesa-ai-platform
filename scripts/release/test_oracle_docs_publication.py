"""Real-key disposable publication journals; never hosted or production evidence."""

import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import oracle_docs_native as native
import oracle_docs_owner as publication
import oracle_owner as owner
import test_oracle_docs_native as fixtures


class PublicationTests(unittest.TestCase):
    open = fixtures.NativeCustodyTests.open
    settings = fixtures.NativeCustodyTests.settings
    commission_fixture = fixtures.NativeCustodyTests.commission_fixture
    sign = fixtures.NativeCustodyTests.sign
    registered = fixtures.NativeCustodyTests.registered
    session = fixtures.NativeCustodyTests.session
    envelope = fixtures.NativeCustodyTests.envelope

    @classmethod
    def setUpClass(cls):
        fixtures.NativeCustodyTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.NativeCustodyTests.setUp(self)
        self.interrupt = False
        self.wrong = False

        def create(_store, _operation):
            # An actual second call fails this exclusive disposable provider stand-in.
            with (self.root / "provider-count").open("x") as file:
                file.write("1")
            if self.interrupt:
                raise owner.Rejected("SYNTHETIC_PROVIDER_ACK_INTERRUPTED")

        def inspect(_store, operation):
            return {
                "operation_id": operation["id"],
                "binding": self.binding,
                "workflow_run_id": False if self.wrong else 0,
                "environment": "staging",
                "production_deployment_authorized": False,
                "deployment_id": "synthetic-provider-fixture-only",
            }

        self.enterContext(
            patch.object(
                publication,
                "for_binding",
                return_value=SimpleNamespace(
                    prepare=lambda *_args: {"synthetic_build_only": True},
                    create_preview=create,
                    inspect_preview=inspect,
                ),
            )
        )

    def qualification(self):
        registered, context, challenge = self.session()
        native.import_observation(
            self.store, owner.canonical(self.envelope(registered, challenge))
        )
        return native.complete_qualification(self.store, context["id"])["record"]

    def test_simultaneous_preview_requests_create_once(self):
        barrier = threading.Barrier(2)

        def publish(_):
            store = self.open()
            try:
                barrier.wait(timeout=10)
                return publication.publish_preview(store, self.binding)
            finally:
                store.db.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(publish, range(2)))
        self.assertEqual(sum("record" in result for result in results), 1)
        self.assertEqual(
            sum(
                result.get("state")
                == "EXISTING_PREVIEW_OPERATION_INSPECT_ONLY_NO_DUPLICATE_REQUEST"
                for result in results
            ),
            1,
        )
        self.assertEqual((self.root / "provider-count").read_text(), "1")

    def test_interrupted_preview_retains_intent_and_inspection_cannot_create_again(
        self,
    ):
        self.interrupt = True
        with self.assertRaises(owner.Rejected):
            publication.publish_preview(self.store, self.binding)
        again = publication.publish_preview(self.store, self.binding)
        self.assertEqual(
            again["state"],
            "EXISTING_PREVIEW_OPERATION_INSPECT_ONLY_NO_DUPLICATE_REQUEST",
        )
        receipt = publication.receipt_for(
            self.store, again["operation_id"], reconcile=True
        )["record"]
        self.assertTrue(receipt["details"]["reconciled_read_only"])
        self.assertFalse(receipt["details"]["production_deployment_authorized"])
        self.assertEqual((self.root / "provider-count").read_text(), "1")

    def test_run_zero_is_an_integer_and_malformed_observations_cannot_be_receipts(self):
        self.wrong = True
        with self.assertRaises(owner.Rejected):
            publication.publish_preview(self.store, self.binding)
        self.assertEqual(
            self.store.db.execute(
                "SELECT count(*) FROM records WHERE kind='documentation-preview-receipt'"
            ).fetchone()[0],
            0,
        )

    def test_full_preflight_target_has_time_for_the_matrix_but_no_release_authority(
        self,
    ):
        preview = self.store.put(
            publication.RECEIPT, self.binding, {"synthetic": True}
        )["record"]
        docs = SimpleNamespace(
            preview_for_binding=lambda *_: preview,
            target_for_observation=lambda *_args, **_kwargs: {"synthetic_target": True},
        )
        with patch.object(publication, "for_binding", return_value=docs):
            target = publication.native_preflight(self.store, self.binding)["record"]
        self.assertEqual(
            datetime.fromisoformat(target["expires_at"])
            - datetime.fromisoformat(target["issued_at"]),
            timedelta(seconds=900),
        )
        self.assertFalse(target["details"]["qualification_reserved"])
        self.assertFalse(target["details"]["production_deployment_authorized"])
        self.assertEqual(target["details"]["hosted_acceptance"], "NOT_PERFORMED")
        self.assertEqual(
            self.store.db.execute("SELECT count(*) FROM contexts").fetchone()[0], 0
        )
        self.assertEqual(
            self.store.db.execute("SELECT count(*) FROM deployments").fetchone()[0], 0
        )
        self.assertEqual(
            self.store.db.execute(
                "SELECT count(*) FROM records WHERE kind IN ('qualification','authorization','native-observation')"
            ).fetchone()[0],
            0,
        )

    def test_deployment_preserves_real_receipt_and_waits_for_separate_native_production(
        self,
    ):
        qualified = self.qualification()
        authorization = self.store.authorize(qualified["id"])["record"]
        pending = self.store.deploy(authorization["id"])
        self.assertEqual(pending["state"], "deployed-unverified")
        self.assertEqual(
            self.store.db.execute(
                "SELECT count(*) FROM records WHERE kind='production-verification'"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.store.deploy(authorization["id"])["action"],
            "INSPECT_ONLY_NO_DUPLICATE_REQUEST",
        )
        self.assertEqual((self.root / "provider-count").read_text(), "1")
        self.settings({"check": "affected_workflows"})
        with self.assertRaises(owner.Rejected):
            self.store.inspect(pending["operation_id"], observe=True)
        self.assertEqual(
            self.store.inspect(pending["operation_id"])["state"], "deployed-unverified"
        )
        self.settings({})
        self.assertEqual(
            self.store.inspect(pending["operation_id"], observe=True)["record"]["kind"],
            "production-verification",
        )
        self.assertEqual((self.root / "provider-count").read_text(), "1")

    def test_interrupted_deploy_is_reconciled_with_one_read_only_provider_receipt(self):
        qualified = self.qualification()
        authorization = self.store.authorize(qualified["id"])["record"]
        self.settings({"interrupt": True})
        with self.assertRaises(owner.Rejected):
            self.store.deploy(authorization["id"])
        operation = self.store.deploy(authorization["id"])
        self.assertEqual(operation["state"], "request-recorded")
        self.settings({})
        self.store.inspect(operation["operation_id"], observe=True)
        self.store.inspect(operation["operation_id"], observe=True)
        rows = self.store.db.execute(
            "SELECT id FROM records WHERE kind='deployment-receipt'"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertTrue(
            self.store.get(rows[0][0])["record"]["details"]["reconciled_read_only"]
        )
        self.assertEqual((self.root / "provider-count").read_text(), "1")

    def test_maximum_record_lifetime_uses_one_clock_instant(self):
        initial = owner.timestamp()
        calls = []

        def clock():
            result = initial + timedelta(microseconds=len(calls))
            calls.append(result)
            return result

        self.store.clock = clock
        record = self.store.put("disposable-max-lifetime", self.binding, {}, ttl=86400)[
            "record"
        ]
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.store.get(record["id"])["record"]["id"], record["id"])
