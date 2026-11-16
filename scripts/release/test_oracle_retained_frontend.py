"""Retained UI is inspected under its original accepted binding, never redeployed."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import oracle_ai_frontend as f


class RetainedFrontendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.receipt = self.root / "frontend-production-build.json"
        self.old = {
            "repository": f.r.profiles.REPOSITORY,
            "component": "frontend",
            "candidate_commit": "a" * 40,
            "source_tree": "b" * 40,
            "source_sha256": "c" * 64,
            "artifact_digest": "sha256:" + "d" * 64,
            "target_environment": "production",
        }
        self.receipt.write_text(
            json.dumps(
                {
                    "binding": self.old,
                    "artifact_sha256": "d" * 64,
                    "environment": "production",
                }
            )
        )
        self.old["build_sha256"] = hashlib.sha256(self.receipt.read_bytes()).hexdigest()
        self.binding = {
            "repository": self.old["repository"],
            "component": "twins-api",
            "candidate_commit": "e" * 40,
        }
        self.plan = {
            "retained_frontend": {
                "binding": self.old,
                "source": self.old["candidate_commit"],
                "deployment_id": "dpl_synthetic_retained",
                "operation_id": str(uuid4()),
                "verifier_store": "/synthetic/original-owner-store",
            }
        }
        self.metadata = {
            "environment": "production",
            "provider": {
                "source": self.old["candidate_commit"],
                "deployment_id": "dpl_synthetic_retained",
            },
        }
        self.chain = [
            {
                "kind": "production-verification",
                "id": str(uuid4()),
                "details": {
                    "observations": {
                        "deployment_id": "dpl_synthetic_retained",
                        "runtime_source": self.old["candidate_commit"],
                        "artifact_sha256": "d" * 64,
                    }
                },
            }
        ]

    def inspect(self, plan=None, metadata=None, chain=None, error=None):
        with (
            patch.object(
                f.r, "private", side_effect=lambda path, **_kwargs: Path(path)
            ),
            patch.object(f, "artifact_folder", return_value=self.root),
            patch.object(
                f.r,
                "verify_invocation",
                return_value=self.chain if chain is None else chain,
                side_effect=error,
            ) as verify,
            patch.object(f, "verify_static") as static,
            patch.object(f, "provider") as provider,
            patch.object(f, "create") as create,
        ):
            result = f.verify_retained_frontend(
                self.binding,
                self.plan if plan is None else plan,
                self.metadata if metadata is None else metadata,
            )
            verify.assert_called_once_with(
                self.old,
                {
                    "operation_id": self.plan["retained_frontend"]["operation_id"],
                    "read_only": True,
                },
                "production",
                {"verifier_store": "/synthetic/original-owner-store"},
                dependency=True,
            )
            static.assert_called_once()
            provider.assert_not_called()
            create.assert_not_called()
            return result

    def test_accepted_retained_artifact_is_read_back_under_original_authority(self):
        result = self.inspect()
        self.assertEqual(result["binding"], self.old)
        self.assertNotEqual(
            result["binding"]["candidate_commit"], self.binding["candidate_commit"]
        )
        self.assertTrue(result["served_static_artifact_verified"])
        self.assertFalse(result["authority_transferred"])
        self.assertEqual(result["new_frontend_deployment_requests"], 0)

    def test_wrong_source_environment_component_or_provider_is_refused(self):
        for field, value in [
            ("source", "e" * 40),
            ("deployment_id", "dpl_other"),
            ("component", "twins-api"),
            ("environment", "staging"),
            ("repository", "foreign/repository"),
        ]:
            plan, metadata = copy.deepcopy(self.plan), copy.deepcopy(self.metadata)
            if field in {"source", "deployment_id"}:
                metadata["provider"][field] = value
            elif field == "environment":
                metadata[field] = value
            else:
                plan["retained_frontend"]["binding"][field] = value
            with (
                self.subTest(field=field),
                self.assertRaises((f.r.Refused, ValueError)),
            ):
                self.inspect(plan=plan, metadata=metadata)

    def test_unaccepted_or_modified_build_and_wrong_accepted_artifact_fail_closed(self):
        with self.assertRaises(f.r.Refused):
            self.inspect(error=f.r.Refused("SYNTHETIC_REVOKED_OR_UNACCEPTED_CHAIN"))
        for field, value in [
            ("artifact_sha256", "f" * 64),
            ("runtime_source", "f" * 40),
            ("deployment_id", "dpl_other"),
        ]:
            chain = copy.deepcopy(self.chain)
            chain[0]["details"]["observations"][field] = value
            with self.subTest(field=field), self.assertRaises(f.r.Refused):
                self.inspect(chain=chain)
        self.receipt.write_text("{}")
        with self.assertRaises(f.r.Refused):
            self.inspect()


if __name__ == "__main__":
    unittest.main()
