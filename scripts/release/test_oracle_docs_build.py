"""Disposable Actions metadata/ZIP controls; no provider or owner authority."""

import copy
import hashlib
import io
import json
import os
import stat
import unittest
import warnings
import zipfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import oracle_docs_build as docs
import oracle_owner as owner

NOW = datetime(2026, 10, 29, 2, tzinfo=timezone.utc)
SOURCE = {
    "repository": docs.REPOSITORY,
    "candidate_commit": "a" * 40,
    "source_tree": "b" * 40,
}


def archive(name, *, revision=None, label=None, extra=None, private=False):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as result:
        result.writestr(
            "generated/provenance.json",
            json.dumps(
                {
                    "revision": revision or SOURCE["candidate_commit"],
                    "classification": "internal" if private else "public",
                    "protected_document_sources": {} if private else None,
                    "policy_schema_version": 1,
                    "code_sha256": "d" * 64,
                    "sources": {"docs/public/fixture.md": "e" * 64},
                    "snapshot_sources": {},
                }
            ),
        )
        result.writestr(
            "index.html",
            '<div class="docs-audience" role="note">'
            + (label if label is not None else docs.ARTIFACTS[name])
            + "</div>",
        )
        for index in range(98):
            result.writestr("docs/public/fixture-" + str(index) + ".html", "fixture")
        if extra:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                result.writestr(*extra)
    return output.getvalue()


class GitHub:
    def __init__(self):
        self.qualifications = 0
        self.changed_source = False
        self.changed_artifacts = False
        self.artifact_reads = 0
        self.run = {
            "id": 100,
            "repository": {"full_name": docs.REPOSITORY},
            "head_repository": {"full_name": docs.REPOSITORY},
            "head_sha": SOURCE["candidate_commit"],
            "head_branch": "main",
            "path": ".github/workflows/docs-hosting.yml",
            "event": "workflow_dispatch",
            "run_attempt": 1,
            "status": "completed",
            "conclusion": "success",
            "actor": {"login": owner.OWNER},
            "triggering_actor": {"login": owner.OWNER},
            "updated_at": NOW.isoformat(),
        }
        self.job = {
            "id": 200,
            "run_id": 100,
            "name": "docs-hosting",
            "status": "completed",
            "conclusion": "success",
            "steps": [
                {"name": name, "status": "completed", "conclusion": status}
                for names, status in [
                    (docs.BUILD_STEPS, "success"),
                    (docs.PROVIDER_STEPS, "skipped"),
                ]
                for name in sorted(names)
            ],
        }
        self.items = []
        self.archives = {}
        for index, name in enumerate(docs.ARTIFACTS, start=300):
            self.items.append(
                {
                    "id": index,
                    "name": name,
                    "expired": False,
                    "workflow_run": {"id": 100, "head_sha": SOURCE["candidate_commit"]},
                }
            )
            self.set_archive(index, archive(name))

    def set_archive(self, id_, raw):
        self.archives[id_] = raw
        next(item for item in self.items if item["id"] == id_)["digest"] = (
            "sha256:" + hashlib.sha256(raw).hexdigest()
        )

    def owner(self):
        return owner.OWNER

    def qualify(self, source):
        self.qualifications += 1
        owner.require(source == SOURCE, "Source fixture mismatch")
        owner.require(
            not self.changed_source or self.qualifications == 1,
            "Current exact main required",
        )
        return [{"run_id": 99, "run_attempt": 1}]

    def api(self, path):
        prefix = "repos/" + docs.REPOSITORY + "/actions/runs/100"
        if path == prefix:
            return copy.deepcopy(self.run)
        if path == prefix + "/jobs?filter=latest&per_page=100":
            return {"total_count": 1, "jobs": [copy.deepcopy(self.job)]}
        if path == prefix + "/artifacts?per_page=100":
            self.artifact_reads += 1
            items = copy.deepcopy(self.items)
            if self.changed_artifacts and self.artifact_reads > 1:
                items[0]["expired"] = True
            return {"total_count": len(items), "artifacts": items}
        raise AssertionError("Unexpected fixture API path")


class DocsBuildTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, {"GITHUB_ACTIONS": ""}))
        self.github = GitHub()

    def read(self, run_id=100):
        return docs.read_build(
            self.github, SOURCE, run_id, self.github.archives, now=NOW
        )

    def test_genuine_build_stays_blocked_for_hosted_qualification_and_authority(self):
        result = self.read()
        self.assertEqual(result["actions_build_run_id"], 100)
        self.assertEqual(len(result["artifacts"]), 2)
        self.assertEqual(result["STAGING_VERIFIED"], "BLOCKED")
        self.assertEqual(self.github.qualifications, 2)
        for name in ["production", "application", "backend"]:
            self.assertIs(result[name + "_deployment_authorized"], False)

    def test_owner_run_zero_is_never_an_actions_build_id(self):
        for value in [0, -1, True, "100"]:
            with self.subTest(value=value), self.assertRaises(owner.Rejected):
                self.read(value)

    def test_actions_cannot_execute_the_external_reader(self):
        with (
            patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}),
            self.assertRaisesRegex(owner.Rejected, "EXTERNAL_DOCS"),
        ):
            self.read()

    def test_run_provenance_failures(self):
        for key, value in [
            ("head_sha", "c" * 40),
            ("head_branch", "dev"),
            ("event", "pull_request"),
            ("run_attempt", 2),
            ("run_attempt", True),
            ("path", ".github/workflows/ci.yml"),
            ("conclusion", "failure"),
            ("status", "in_progress"),
            ("actor", {"login": "another-owner"}),
            ("repository", {"full_name": "foreign/repository"}),
        ]:
            with self.subTest(key=key, value=value):
                self.github = GitHub()
                self.github.run[key] = value
                with self.assertRaises(owner.Rejected):
                    self.read()

    def test_failed_skipped_missing_checks_and_provider_execution_are_refused(self):
        for conclusion in ["failure", "skipped", "cancelled", None]:
            for name in docs.BUILD_STEPS:
                with self.subTest(name=name, conclusion=conclusion):
                    self.github = GitHub()
                    next(s for s in self.github.job["steps"] if s["name"] == name)[
                        "conclusion"
                    ] = conclusion
                    with self.assertRaises(owner.Rejected):
                        self.read()
        for name in docs.PROVIDER_STEPS:
            with self.subTest(provider=name):
                self.github = GitHub()
                next(s for s in self.github.job["steps"] if s["name"] == name)[
                    "conclusion"
                ] = "success"
                with self.assertRaises(owner.Rejected):
                    self.read()
        self.github = GitHub()
        self.github.job["steps"].pop(0)
        with self.assertRaises(owner.Rejected):
            self.read()

    def test_expired_future_build_and_wrong_job_are_refused(self):
        for delta in [timedelta(hours=6), timedelta(seconds=-1)]:
            self.github = GitHub()
            self.github.run["updated_at"] = (NOW - delta).isoformat()
            with self.assertRaises(owner.Rejected):
                self.read()
        self.github = GitHub()
        self.github.job["run_id"] = 101
        with self.assertRaises(owner.Rejected):
            self.read()

    def test_duplicate_named_check_cannot_hide_a_failed_check(self):
        duplicated = copy.deepcopy(self.github.job["steps"][0])
        duplicated["conclusion"] = "failure"
        self.github.job["steps"].insert(0, duplicated)
        with self.assertRaises(owner.Rejected):
            self.read()

    def test_additional_failed_step_cannot_hide_behind_job_success(self):
        self.github.job["steps"].append(
            {"name": "Additional check", "status": "completed", "conclusion": "failure"}
        )
        with self.assertRaises(owner.Rejected):
            self.read()

    def test_artifact_expiry_origin_digest_and_incomplete_sets_are_refused(self):
        for key, value in [
            ("expired", True),
            ("digest", "sha256:" + "0" * 64),
            ("workflow_run", {"id": 101, "head_sha": "c" * 40}),
            ("name", "private-docs"),
        ]:
            with self.subTest(key=key):
                self.github = GitHub()
                self.github.items[0][key] = value
                with self.assertRaises(owner.Rejected):
                    self.read()
        self.github = GitHub()
        self.github.items.pop()
        with self.assertRaises(owner.Rejected):
            self.read()

    def test_modified_internal_wrong_source_or_relabelled_archives_are_refused(self):
        name = "onesa-public-docs-staging"
        for changes in [
            {"revision": "c" * 40},
            {"private": True},
            {"label": "DEVELOPMENT · Public developer documentation"},
            {"label": docs.ARTIFACTS["onesa-public-docs-production"]},
            {"extra": ("index.html", "duplicate")},
            {"extra": ("../escape", "fixture")},
            {"extra": ("/absolute", "fixture")},
            {"extra": ("back\\slash", "fixture")},
            {"extra": ("generated/engineering-navigation.json", "private")},
        ]:
            with self.subTest(changes=changes):
                self.github = GitHub()
                self.github.set_archive(300, archive(name, **changes))
                with self.assertRaises(owner.Rejected):
                    self.read()
        symlink = zipfile.ZipInfo("link")
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.github = GitHub()
        self.github.set_archive(300, archive(name, extra=(symlink, "target")))
        with self.assertRaises(owner.Rejected):
            self.read()

    def test_source_or_artifact_change_during_read_is_refused(self):
        for flag in ["changed_source", "changed_artifacts"]:
            self.github = GitHub()
            setattr(self.github, flag, True)
            with self.subTest(flag=flag), self.assertRaises(owner.Rejected):
                self.read()

    def test_missing_provenance_and_incomplete_public_tree_are_refused(self):
        for missing in ["protected_document_sources", "code_sha256", "sources"]:
            self.github = GitHub()
            raw = self.github.archives[300]
            output = io.BytesIO()
            with (
                zipfile.ZipFile(io.BytesIO(raw)) as before,
                zipfile.ZipFile(output, "w") as after,
            ):
                for item in before.infolist():
                    value = before.read(item)
                    if item.filename == "generated/provenance.json":
                        provenance = json.loads(value)
                        del provenance[missing]
                        value = json.dumps(provenance).encode()
                    after.writestr(item, value)
            self.github.set_archive(300, output.getvalue())
            with self.subTest(missing=missing), self.assertRaises(owner.Rejected):
                self.read()
        self.github = GitHub()
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as result:
            result.writestr("index.html", "incomplete")
        self.github.set_archive(300, output.getvalue())
        with self.assertRaises(owner.Rejected):
            self.read()


if __name__ == "__main__":
    unittest.main()
