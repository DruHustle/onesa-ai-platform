"""Exercise real archive and release boundaries; synthetic proofs authorize nothing."""

import copy
import hashlib
import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import evidence as e
import free_gate as f
from test_evidence import FINGERPRINT, SHA, run
from test_free_gate import GitHub


def archive(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as bundle:
        for name, content, mode in entries:
            item = zipfile.ZipInfo(name)
            item.external_attr = mode << 16
            bundle.writestr(item, content)
    return output.getvalue()


def site():
    entries = [
        (
            "generated/provenance.json",
            json.dumps({"revision": SHA, "classification": "public"}).encode(),
            0,
        ),
        ("index.html", b"qualified production context", 0),
    ]
    digest = hashlib.sha256()
    for name, content, _ in sorted(entries):
        digest.update(name.encode() + b"\0" + hashlib.sha256(content).digest())
    data = archive(entries)
    return data, {
        "build_sha256": digest.hexdigest(),
        "artifact_sha256": hashlib.sha256(data).hexdigest(),
    }


def acceptance(environment):
    registry = json.loads(
        (
            e.ROOT
            / "onesa-ai-platform-frontend/packages/onesa-design/onesa-applications.json"
        ).read_text()
    )
    links = [
        {"label": app["label"] + " ↗", "href": app["href"]}
        for app in registry["applications"]
    ]
    manifest = json.loads(
        (
            e.ROOT
            / "onesa-ai-platform-frontend/apps/docs/static/brand/icons/v1/sources.json"
        ).read_text()
    )
    icons = [
        {
            "path": "/favicon.ico"
            if file["name"].endswith(".ico")
            else "/brand/icons/v1/" + file["name"],
            "status": 200,
            "mime": file["mime"],
            "sha256": file["sha256"],
        }
        for file in manifest["products"][0]["files"]
        if file["name"] in {"onesa-docs.svg", "onesa-docs.ico", "onesa-docs-180.png"}
    ]
    return {
        "result": "PASS",
        "environment_context": environment,
        "origin": "https://onesa-docs-synthetic.vercel.app",
        "navigation": [
            {"view": view, "links": links} for view in ["desktop", "mobile"]
        ],
        "icons": icons,
        "accessibility": [
            {
                "route": "/synthetic-" + str(index),
                "mode": mode,
                "width": width,
                "violations": [],
            }
            for index in range(31)
            for mode in ["light", "dark"]
            for width in [320, 1440]
        ],
        "widths": [
            {"route": route, "mode": "dark", "width": width, "overflow": False}
            for route in ["/", "/architecture", "/downloads", "/api-explorer"]
            for width in [320, 390, 768, 1024, 1440]
        ],
        "links": 3084,
        "diagrams": 21,
        "pdfs": 11,
        "provenance": {"revision": SHA, "classification": "public"},
    }


class DocsGitHub(GitHub):
    def __init__(self):
        super().__init__()
        self.runs_by_id[20] = run(20, "docs-hosting.yml", branch="staging")
        self.runs_by_id[20]["created_at"] = datetime.now(timezone.utc).isoformat()
        self.site, proof = site()
        self.docs = {
            "schema_version": 1,
            "repository": e.REPOSITORY,
            "candidate_commit": SHA,
            "workflow_run_id": 20,
            "source_sha256": FINGERPRINT,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "target": "preview",
            "production_deployment_requested": False,
            "application_deployment_authorized": False,
            "backend_deployment_authorized": False,
            "scopes": {
                "public": {
                    **proof,
                    "classification": "public",
                    "status": "PASS",
                    "build_environment": "production",
                    "checks": {
                        name: "PASS"
                        for name in [
                            "classified_build",
                            "dependency_security",
                            "public_private_boundary",
                            "system_appearance_and_accessibility",
                            "diagrams_pdfs_navigation",
                            "hosted_preview_identity",
                            "hosted_preview_acceptance",
                        ]
                    },
                    "preview_artifact": copy.deepcopy(proof),
                    "hosted_acceptance": acceptance("staging"),
                    "production_acceptance": acceptance("production"),
                    "preview": {
                        "url": "https://onesa-docs-synthetic.vercel.app",
                        "project": "onesa-docs",
                        "projectId": f.PUBLIC_DOCS_PROJECT,
                        "deploymentId": "dpl_synthetic",
                        "target": None,
                        "state": "READY",
                        "sourceRevision": SHA,
                    },
                },
                "internal": {"classification": "internal", "status": "BLOCKED"},
            },
        }
        self.metadata = {
            "id": 201,
            "expired": False,
            "size_in_bytes": len(self.site),
            "digest": "sha256:" + proof["artifact_sha256"],
            "workflow_run": {"id": 20, "head_sha": SHA, "head_repository_id": 7},
        }

    def artifact(self, value, name):
        if name == "documentation-qualification":
            return copy.deepcopy(self.docs), {
                "run_id": 20,
                "record_sha256": e.digest(self.docs),
            }
        return super().artifact(value, name)

    def api(self, path, pages=False, binary=False):
        if path.endswith("/artifacts?per_page=100"):
            return [
                {
                    "artifacts": [
                        {"id": 201, "name": name}
                        for name in [
                            "onesa-public-docs-staging",
                            "onesa-public-docs-production",
                        ]
                    ]
                }
            ]
        if path.endswith("/artifacts/201/zip"):
            return self.site
        if path.endswith("/artifacts/201"):
            return self.metadata
        return super().api(path, pages)


class DocsScopeTests(unittest.TestCase):
    def setUp(self):
        self.github = DocsGitHub()
        self.fingerprint = patch.object(e, "source_hash", return_value=FINGERPRINT)
        self.fingerprint.start()
        self.addCleanup(self.fingerprint.stop)

    def prepare(self):
        self.github.record = f.qualification(
            self.github, SHA, self.github.run(30), 20, "docs-public"
        )
        self.github.approval = f.authorize(
            self.github,
            SHA,
            self.github.run(40),
            30,
            e.digest(self.github.record),
            None,
            "approve",
            "docs-public",
        )

    def test_archive_route_siblings_match_actual_producer_order_and_reject_changed_bytes(
        self,
    ):
        entries = [
            ("guide/intro.html", b"nested documentation route", 0),
            ("guide.html", b"documentation route index", 0),
            ("index.html", b"public homepage", 0),
        ]
        spec = importlib.util.spec_from_file_location(
            "docs_release_producer", e.ROOT / "scripts/docs/release_preview.py"
        )
        producer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(producer)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            for name, content, _ in entries:
                file = directory / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(content)
            expected_build = producer.build_digest(directory)
        text_order = hashlib.sha256()
        for name, content, _ in sorted(entries):
            text_order.update(name.encode() + b"\0" + hashlib.sha256(content).digest())
        self.assertNotEqual(expected_build, text_order.hexdigest())
        proof = {"build_sha256": expected_build}
        for changed in [False, True]:
            current = list(entries)
            if changed:
                current[0] = (current[0][0], b"altered nested documentation bytes", 0)
            self.github.site = archive(current)
            proof["artifact_sha256"] = hashlib.sha256(self.github.site).hexdigest()
            self.github.metadata.update(
                digest="sha256:" + proof["artifact_sha256"],
                size_in_bytes=len(self.github.site),
            )
            if changed:
                with self.assertRaisesRegex(
                    e.Rejected, "Public Docs build/artifact mismatch"
                ):
                    f.public_docs_artifact(
                        self.github,
                        self.github.run(20),
                        proof,
                        "onesa-public-docs-staging",
                    )
            else:
                result = f.public_docs_artifact(
                    self.github, self.github.run(20), proof, "onesa-public-docs-staging"
                )
                self.assertEqual(result["id"], 201)

    def test_docs_approval_grants_only_exact_public_docs(self):
        self.prepare()
        result = f.verify(self.github, SHA, 40, "docs-public")
        self.assertEqual(result["approval"]["delivery_scope"], "docs-public")
        self.assertFalse(result["approval"]["application_deployment_authorized"])
        self.assertFalse(result["approval"]["backend_deployment_authorized"])
        self.assertEqual(
            self.github.record["staging"]["retained_backend_commit"],
            f.RETAINED_APPLICATION_COMMIT,
        )
        for scope in ["full", "docs-internal"]:
            with self.subTest(scope=scope), self.assertRaises(e.Rejected):
                f.verify(self.github, SHA, 40, scope)

    def test_full_scope_cannot_accept_docs_producer_and_internal_local_build_is_insufficient(
        self,
    ):
        for scope in ["full", "docs-internal"]:
            with self.subTest(scope=scope), self.assertRaises(e.Rejected):
                f.qualification(self.github, SHA, self.github.run(30), 20, scope)

    def test_source_actor_scope_grants_target_and_provenance_fail_closed(self):
        cases = [
            (["candidate_commit"], "c" * 40),
            (["source_sha256"], "c" * 64),
            (["application_deployment_authorized"], True),
            (["backend_deployment_authorized"], True),
            (["target"], "production"),
            (["scopes", "public", "status"], "FAIL"),
            (["scopes", "public", "preview", "projectId"], "prj_app"),
            (["scopes", "public", "preview", "target"], "production"),
            (["scopes", "public", "preview", "sourceRevision"], "c" * 40),
            (
                ["scopes", "public", "hosted_acceptance", "provenance"],
                {"revision": SHA, "classification": "internal"},
            ),
            (
                ["scopes", "public", "production_acceptance", "environment_context"],
                "staging",
            ),
            (["scopes", "public", "production_acceptance", "navigation"], []),
            (["scopes", "public", "checks", "dependency_security"], "BLOCKED"),
        ]
        for keys, value in cases:
            saved = copy.deepcopy(self.github.docs)
            current = self.github.docs
            for key in keys[:-1]:
                current = current[key]
            current[keys[-1]] = value
            with self.subTest(keys=keys), self.assertRaises(e.Rejected):
                f.docs_qualification(self.github, SHA, 20, "docs-public")
            self.github.docs = saved
        for field, value in [
            ("actor", {"login": "attacker"}),
            ("conclusion", "failure"),
            ("head_sha", "c" * 40),
            ("head_branch", "dev"),
        ]:
            old = self.github.runs_by_id[20][field]
            self.github.runs_by_id[20][field] = value
            with self.subTest(field=field), self.assertRaises(e.Rejected):
                f.docs_qualification(self.github, SHA, 20, "docs-public")
            self.github.runs_by_id[20][field] = old
        del self.github.docs["scopes"]["public"]["preview"]["target"]
        with self.assertRaises(e.Rejected):
            f.docs_qualification(self.github, SHA, 20, "docs-public")

    def test_archive_origin_bytes_and_qualified_build_are_all_bound(self):
        proof = self.github.docs["scopes"]["public"]
        for key, value in [
            ("expired", True),
            ("digest", "sha256:" + "0" * 64),
            ("workflow_run", {"id": 20, "head_sha": "c" * 40, "head_repository_id": 7}),
        ]:
            saved = copy.deepcopy(self.github.metadata)
            self.github.metadata[key] = value
            with self.subTest(key=key), self.assertRaises(e.Rejected):
                f.public_docs_artifact(self.github, self.github.run(20), proof)
            self.github.metadata = saved
        self.github.site += b"tampered"
        with self.assertRaises(e.Rejected):
            f.public_docs_artifact(self.github, self.github.run(20), proof)

    def test_malformed_duplicate_and_failing_per_view_acceptance_is_rejected(self):
        baseline = acceptance("production")
        for field, value in [
            ("accessibility", [1] * 124),
            ("widths", [1] * 20),
            ("navigation", [1, 2]),
            ("icons", [1, 2, 3]),
            ("accessibility", [baseline["accessibility"][0]] * 124),
            ("widths", [baseline["widths"][0]] * 20),
        ]:
            candidate = copy.deepcopy(baseline)
            candidate[field] = value
            with self.subTest(field=field), self.assertRaises(e.Rejected):
                f.docs_acceptance_schema(candidate)
        for mutation in ["violation", "overflow", "icon", "navigation"]:
            candidate = copy.deepcopy(baseline)
            if mutation == "violation":
                candidate["accessibility"][0]["violations"] = [
                    {"id": "contrast", "impact": "serious", "nodes": []}
                ]
            elif mutation == "overflow":
                candidate["widths"][0]["overflow"] = True
            elif mutation == "icon":
                candidate["icons"][0]["sha256"] = "d" * 64
            else:
                candidate["navigation"][0]["links"][0]["href"] = "http://localhost"
            with self.subTest(mutation=mutation), self.assertRaises(e.Rejected):
                f.docs_acceptance_schema(candidate)

    def test_unsafe_zip_paths_aliases_and_different_production_bytes_are_rejected(self):
        for entries in [
            [("../outside/", b"", stat.S_IFDIR | 0o755)],
            [("alias/", b"", stat.S_IFLNK | 0o777)],
            [("../outside", b"x", 0)],
            [("/absolute", b"x", 0)],
            [("./index.html", b"x", 0)],
            [("a//b", b"x", 0)],
            [("alias", b"outside", stat.S_IFLNK | 0o777)],
            [("index.html", b"different ignored production build", 0)],
        ]:
            self.github.site = archive(entries)
            proof = copy.deepcopy(self.github.docs["scopes"]["public"])
            proof["artifact_sha256"] = hashlib.sha256(self.github.site).hexdigest()
            self.github.metadata["digest"] = "sha256:" + proof["artifact_sha256"]
            with self.subTest(entries=entries), self.assertRaises(e.Rejected):
                f.public_docs_artifact(self.github, self.github.run(20), proof)

    def test_latest_revocation_and_malformed_grants_block_older_approval(self):
        self.prepare()
        self.github.approval["application_deployment_authorized"] = True
        with self.assertRaises(e.Rejected):
            f.verify(self.github, SHA, 40, "docs-public")
        self.prepare()
        self.github.approval["decision"] = "revoke"
        with self.assertRaises(e.Rejected):
            f.verify(self.github, SHA, 40, "docs-public")
        self.prepare()
        self.github.latest = 41
        self.github.runs_by_id[41] = run(41, f.WORKFLOW)
        with self.assertRaises(e.Rejected):
            f.verify(self.github, SHA, 40, "docs-public")

    def test_ambient_docs_scope_cannot_change_default_cli_consumer(self):
        seen = []

        def capture(*args):
            seen.append(args[-1])
            raise e.Rejected("synthetic stop before output")

        with (
            patch.dict(os.environ, {"DELIVERY_SCOPE": "docs-public"}, clear=True),
            patch.object(
                sys,
                "argv",
                [
                    "free_gate.py",
                    "verify",
                    "--sha",
                    SHA,
                    "--authorization-run",
                    "40",
                    "--output",
                    "/not-written/record.json",
                ],
            ),
            patch.object(
                f.subprocess,
                "check_output",
                side_effect=[SHA, "", json.dumps({"login": e.OWNER})],
            ),
            patch.object(f, "verify", side_effect=capture),
            self.assertRaises(e.Rejected),
        ):
            f.main()
        self.assertEqual(seen, ["full"])


if __name__ == "__main__":
    unittest.main()
