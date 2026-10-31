"""Synthetic private artifacts only; no credential, hosted or release authority."""

import copy
import hashlib
import io
import stat
import unittest
import warnings
import zipfile

import oracle_docs_internal_build as build
import oracle_owner as owner


class PrivateBuildTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "repository": "DruHustle/onesa-ai-platform",
            "candidate_commit": "a" * 40,
            "source_tree": "b" * 40,
            "source_sha256": "c" * 64,
        }
        self.approved = {
            "docs/engineering/DEPLOYMENT.md": {
                "repository": "onesa-ai-platform",
                "source_revision": "d" * 40,
                "source_path": "docs/engineering/DEPLOYMENT.md",
                "sha256": "e" * 64,
            }
        }
        worker = b"// synthetic reviewed worker fixture, never deployed\n"
        self.source_files = {
            "infra/cloudflare-docs/worker.mjs": hashlib.sha256(worker).hexdigest(),
            "docs/public/introduction.md": "f" * 64,
        }
        self.provenance = {
            "classification": "internal",
            "revision": self.source["candidate_commit"],
            "policy_schema_version": 1,
            "code_sha256": "1" * 64,
            "protected_document_sources": {
                "schema_version": 1,
                "classification": "internal",
                "documents": copy.deepcopy(self.approved),
                "bundle_sha256": owner.digest(self.approved),
                "historical_public_copies_removed": False,
            },
            "sources": {
                "docs/public/introduction.md": "f" * 64,
                "docs/engineering/DEPLOYMENT.md": "e" * 64,
            },
        }
        self.files = {
            "index.html": (
                '<html><div class="docs-audience">'
                + build.CONTEXTS["staging"]
                + "</div><main>Synthetic private guide</main></html>"
            ).encode(),
            "_worker.js": worker,
            "_routes.json": owner.canonical(
                {"version": 1, "include": ["/*"], "exclude": []}
            ),
            "robots.txt": b"User-agent: *\nDisallow: /\n",
        }
        self.files.update(
            {f"assets/synthetic-{i}.txt": b"synthetic" for i in range(100)}
        )

    def archive(self, *, extra=None):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in {
                **self.files,
                "generated/provenance.json": owner.canonical(self.provenance),
            }.items():
                archive.writestr(name, raw)
            if extra:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    archive.writestr(*extra)
        return stream.getvalue()

    def inspect(self, raw=None, environment="staging"):
        return build.identity(
            self.archive() if raw is None else raw,
            source=self.source,
            environment=environment,
            approved_documents=self.approved,
            source_files=self.source_files,
            backend_code_sha256="1" * 64,
        )

    def test_genuine_private_identity_preserves_original_provenance_without_authority(
        self,
    ):
        raw = self.archive()
        value = self.inspect(raw)
        self.assertEqual(value["archive_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(
            value["protected_source_bundle_sha256"], owner.digest(self.approved)
        )
        self.assertEqual(value["custody"], "private-owner-build-not-actions")
        self.assertFalse(value["qualification_or_publication_authorized"])
        self.assertNotIn("_worker.js", value["served_asset_paths"])
        self.assertIn("index.html", value["served_asset_paths"])
        self.assertEqual(
            self.approved["docs/engineering/DEPLOYMENT.md"]["source_revision"], "d" * 40
        )

    def test_served_bytes_and_routes_match_signed_descriptor(self):
        raw = self.archive()
        identity = self.inspect(raw)
        assets = build.served_assets(raw, identity)
        self.assertEqual(len(assets), len(identity["served_asset_paths"]))
        self.assertIn("/", [item["route"] for item in assets])
        self.assertFalse(any(item["route"].startswith("/_worker") for item in assets))
        for key, changed in [
            ("custody", "actions"),
            ("archive_sha256", "0" * 64),
            ("archive_bytes", len(raw) + 1),
            ("file_manifest_sha256", "0" * 64),
            ("served_asset_paths", identity["served_asset_paths"][:-1]),
            ("files", {**identity["files"], "index.html": "0" * 64}),
        ]:
            altered = {**identity, key: changed}
            with self.subTest(key=key), self.assertRaises(owner.Rejected):
                build.served_assets(raw, altered)

    def test_ambiguous_served_html_routes_fail_closed(self):
        self.files["guide/index.html"] = b"synthetic collision"
        self.files["guide.html"] = b"synthetic collision"
        raw = self.archive()
        with self.assertRaises(owner.Rejected):
            build.served_assets(raw, self.inspect(raw))

    def test_native_http_paths_preserve_space_unicode_and_reserved_name_bytes(self):
        filenames = {
            "manuals/Private guide.pdf": "/manuals/Private%20guide.pdf",
            "assets/Übersicht: original.svg": "/assets/%C3%9Cbersicht%3A%20original.svg",
            "guide with spaces/index.html": "/guide%20with%20spaces/",
        }
        for name in filenames:
            self.files[name] = ("synthetic original bytes: " + name).encode()
        raw = self.archive()
        identity = self.inspect(raw)
        assets = {item["route"]: item for item in build.served_assets(raw, identity)}
        for name, route in filenames.items():
            with self.subTest(name=name):
                self.assertIn(name, identity["files"])
                self.assertEqual(assets[route]["sha256"], identity["files"][name])
                self.assertEqual(assets[route]["bytes"], len(self.files[name]))
                self.assertNotIn(" ", route)

    def test_preescaped_and_traversal_names_remain_refused(self):
        for name in [
            "manuals/Private%20guide.pdf",
            "manuals/../guide.pdf",
            "manuals/guide?.pdf",
            "manuals/guide#.pdf",
        ]:
            with self.subTest(name=name), self.assertRaises(owner.Rejected):
                build.served_assets(self.archive(extra=(name, b"synthetic")), {})

    def test_source_repository_revision_classification_and_policy_mismatch_refused(
        self,
    ):
        for key, value in [
            ("revision", "0" * 40),
            ("classification", "public"),
            ("policy_schema_version", True),
            ("code_sha256", "0" * 64),
        ]:
            saved = copy.deepcopy(self.provenance)
            self.provenance[key] = value
            with self.subTest(key=key), self.assertRaises(owner.Rejected):
                self.inspect()
            self.provenance = saved
        self.source["repository"] = "foreign/repository"
        with self.assertRaises(owner.Rejected):
            self.inspect()

    def test_partial_or_changed_private_provenance_and_false_history_claim_refused(
        self,
    ):
        for change in [
            lambda p: p.update(documents={}),
            lambda p: p.update(bundle_sha256="0" * 64),
            lambda p: p.update(historical_public_copies_removed=True),
            lambda p: p["documents"]["docs/engineering/DEPLOYMENT.md"].update(
                source_revision="0" * 40
            ),
        ]:
            saved = copy.deepcopy(self.provenance)
            change(self.provenance["protected_document_sources"])
            with self.assertRaises(owner.Rejected):
                self.inspect()
            self.provenance = saved

    def test_forged_source_input_or_reference_stub_hash_refused(self):
        for path in ["docs/public/introduction.md", "docs/engineering/DEPLOYMENT.md"]:
            saved = self.provenance["sources"][path]
            self.provenance["sources"][path] = "0" * 64
            with self.assertRaises(owner.Rejected):
                self.inspect()
            self.provenance["sources"][path] = saved
        del self.provenance["sources"]["docs/engineering/DEPLOYMENT.md"]
        with self.assertRaises(owner.Rejected):
            self.inspect()

    def test_context_is_derived_from_actual_html_and_cannot_be_relabelled(self):
        with self.assertRaises(owner.Rejected):
            self.inspect(environment="production")
        self.files["index.html"] = self.files["index.html"].replace(
            b"STAGING", b"DEVELOPMENT"
        )
        with self.assertRaises(owner.Rejected):
            self.inspect()
        self.files["index.html"] = (
            '<div class="docs-audience">' + build.CONTEXTS["production"] + "</div>"
        ).encode()
        self.assertEqual(
            self.inspect(environment="production")["environment"], "production"
        )

    def test_worker_modified_unwrapped_or_routes_excluded_refused(self):
        for name, raw in [
            (
                "_worker.js",
                b"export default {fetch(){return new Response('unguarded')}}",
            ),
            ("_routes.json", b'{"version":1,"include":["/*"],"exclude":["/assets/*"]}'),
            ("robots.txt", b"User-agent: *\nAllow: /\n"),
        ]:
            saved = self.files[name]
            self.files[name] = raw
            with self.subTest(name=name), self.assertRaises(owner.Rejected):
                self.inspect()
            del self.files[name]
            with self.assertRaises(owner.Rejected):
                self.inspect()
            self.files[name] = saved

    def test_provider_redirect_and_header_overrides_refused(self):
        for path in ["_redirects", "_headers"]:
            with self.subTest(path=path), self.assertRaises(owner.Rejected):
                self.inspect(self.archive(extra=(path, b"synthetic unsafe override")))

    def test_traversal_encoded_control_alias_and_duplicate_members_refused(self):
        for path in [
            "../escape",
            "/absolute",
            "a/./b",
            "a//b",
            "a\\b",
            "a%2fb",
            "a?b",
            "a#b",
            "a\nb",
            "index.html",
        ]:
            with self.subTest(path=path), self.assertRaises(owner.Rejected):
                self.inspect(self.archive(extra=(path, b"synthetic")))

    def test_symlink_directory_type_and_oversized_member_refused(self):
        for mode, name in [(stat.S_IFLNK, "link"), (stat.S_IFDIR, "not-a-directory")]:
            info = zipfile.ZipInfo(name)
            info.external_attr = (mode | 0o600) << 16
            with self.assertRaises(owner.Rejected):
                self.inspect(self.archive(extra=(info, b"target")))
        with self.assertRaises(owner.Rejected):
            self.inspect(
                self.archive(extra=("assets/too-large", b"x" * (build.MAX_FILE + 1)))
            )

    def test_duplicate_json_and_incomplete_artifact_refused(self):
        self.files["_routes.json"] = (
            b'{"version":1,"include":["/*"],"exclude":[],"exclude":[]}'
        )
        with self.assertRaises(owner.Rejected):
            self.inspect()
        with self.assertRaises(owner.Rejected):
            self.inspect(b"not a ZIP")
        self.files = {"index.html": self.files["index.html"]}
        with self.assertRaises(owner.Rejected):
            self.inspect()


if __name__ == "__main__":
    unittest.main()
