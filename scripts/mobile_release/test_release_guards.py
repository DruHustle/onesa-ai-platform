import copy
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import ci_gate
import release
import source_guard
import upload


class SourceGuardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name) / "repo"
        self.root.mkdir()
        self.work = Path(self.directory.name) / "release"
        self.work.mkdir()
        self.config = {"repository": "DruHustle/fixture", "framework": "capacitor", "mobilePath": "mobile",
                       "scheme": "App", "appId": "eu.onesa.fixture", "generatedNative": False}
        self.record = {"version": "1.2.3", "buildNumber": "17"}
        files = {"mobile/App.ts": "export const value = 1;\n", "backend/policy.ts": "export const allow = false;\n",
                 "package-lock.json": '{"lockfileVersion":3}\n', ".github/workflows/verify.yml": "name: Verify\n",
                 "mobile/android/app/build.gradle": 'versionCode 1\nversionName "1.2.3"\n',
                 "mobile/ios/App/App.xcodeproj/project.pbxproj": "synthetic project\n"}
        for name, text in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        plist = self.root / "mobile/ios/App/App/Info.plist"
        plist.parent.mkdir(parents=True)
        plist.write_bytes(plistlib.dumps({"CFBundleVersion": "1", "CFBundleShortVersionString": "1.2.3"}))
        self.git("init", "-b", "main")
        self.git("config", "user.name", "DruHustle")
        self.git("config", "user.email", "51920419+DruHustle@users.noreply.github.com")
        self.git("add", ".")
        self.git("commit", "-m", "Synthetic source fixture")
        self.sha = self.git("rev-parse", "HEAD").decode().strip()
        source_guard.initialize(self.config, self.work, self.root)

    def tearDown(self):
        self.directory.cleanup()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def test_permitted_counter_stamp_is_bound_and_later_edits_fail(self):
        for platform in ("android", "ios"):
            release.stamp_native(self.config, self.record, platform, self.root, work=self.work)
            self.assertRegex(source_guard.verify(self.config, self.work, self.root), r"^[a-f0-9]{64}$")
        (self.root / "mobile/android/app/build.gradle").write_text('versionCode 18\nversionName "1.2.3"\n')
        with self.assertRaisesRegex(ValueError, "outside the authorized"):
            source_guard.verify(self.config, self.work, self.root)

    def test_app_nonapp_lockfile_and_workflow_edits_are_rejected(self):
        for name in ("mobile/App.ts", "backend/policy.ts", "package-lock.json", ".github/workflows/verify.yml"):
            with self.subTest(path=name):
                path = self.root / name
                original = path.read_bytes()
                path.write_bytes(original + b"unexpected change\n")
                with self.assertRaisesRegex(ValueError, "outside the authorized"):
                    source_guard.verify(self.config, self.work, self.root)
                path.write_bytes(original)

    def test_untracked_source_staged_source_deletion_and_mode_change_are_rejected(self):
        path = self.root / "backend/new.ts"
        path.write_text("new source")
        with self.assertRaisesRegex(ValueError, "untracked source"):
            source_guard.verify(self.config, self.work, self.root)
        self.git("add", "backend/new.ts")
        with self.assertRaisesRegex(ValueError, "index changed"):
            source_guard.verify(self.config, self.work, self.root)
        self.git("reset", "--", "backend/new.ts")
        path.unlink()
        path = self.root / "mobile/App.ts"
        original = path.read_bytes()
        path.unlink()
        with self.assertRaises(ValueError):
            source_guard.verify(self.config, self.work, self.root)
        path.write_bytes(original)
        path.chmod(0o755)
        with self.assertRaises(ValueError):
            source_guard.verify(self.config, self.work, self.root)

    def test_signing_project_scope_cannot_accept_simultaneous_application_edit(self):
        project = self.root / source_guard.project_path(self.config)
        project.write_text("synthetic manual signing settings\n")
        source_guard.verify(self.config, self.work, self.root, stage="app-target-signing", allowed=[source_guard.project_path(self.config)])
        (self.root / "backend/policy.ts").write_text("changed backend source\n")
        with self.assertRaisesRegex(ValueError, "backend/policy.ts"):
            source_guard.verify(self.config, self.work, self.root, stage="app-target-signing", allowed=[source_guard.project_path(self.config)])

    def test_preupload_checks_actual_source_and_never_reaches_ci_after_corruption(self):
        origin = Path(self.directory.name) / "origin.git"
        subprocess.run(["git", "init", "--bare", str(origin)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "origin", "main")
        env = {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
               "GITHUB_REPOSITORY": self.config["repository"], "GITHUB_SHA": self.sha}
        with patch("release.ci_gate.verify") as checks:
            release.check_source(self.config, self.sha, root=self.root, env=env, work=self.work)
        checks.assert_called_once()
        (self.root / "backend/policy.ts").write_text("changed source\n")
        with patch("release.ci_gate.verify") as checks, self.assertRaises(ValueError):
            release.check_source(self.config, self.sha, root=self.root, env=env, work=self.work)
        checks.assert_not_called()


class PackagedPayloadTests(unittest.TestCase):
    def setUp(self):
        self.config = {"framework": "capacitor", "appId": "com.onesa.pasofi"}
        self.embedded = {"appId": "com.onesa.pasofi", "plugins": {"PasoFiCustomerApi": {"origin": "https://pasofi.mobile.onesa.eu"}}}
        self.payload = {"capacitor.config.json": json.dumps(self.embedded).encode(),
                        "public/index.html": b'<script type="module" src="/assets/app.js"></script>',
                        "public/assets/app.js": b"console.log('synthetic application');"}

    def validate_both(self, payload):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ipa = root / "fixture.ipa"
            with zipfile.ZipFile(ipa, "w") as archive:
                for name, data in payload.items():
                    archive.writestr("Payload/App.app/" + name, data)
            with zipfile.ZipFile(ipa) as archive:
                archive.extractall(root / "unpacked")
            release.inspect_ios_payload(root / "unpacked/Payload/App.app", self.config)
            aab = root / "fixture.aab"
            with zipfile.ZipFile(aab, "w") as archive:
                for name, data in payload.items():
                    archive.writestr("base/assets/" + name, data)
            with zipfile.ZipFile(aab) as archive:
                release.validate_capacitor_payload(self.config, set(archive.namelist()), archive.read, prefix="base/assets/")

    def test_both_packaged_formats_require_config_and_actual_referenced_javascript(self):
        self.validate_both(self.payload)
        for name in self.payload:
            for replacement in (None, b""):
                with self.subTest(path=name, replacement=replacement):
                    payload = dict(self.payload)
                    if replacement is None:
                        del payload[name]
                    else:
                        payload[name] = replacement
                    with self.assertRaises(ValueError):
                        self.validate_both(payload)

    def test_wrong_origin_wrong_app_remote_webview_and_stale_entry_are_rejected(self):
        for mutate in (lambda value: value.update(appId="com.onesa.other"),
                       lambda value: value["plugins"]["PasoFiCustomerApi"].update(origin="https://stale.example"),
                       lambda value: value.update(server={"url": "https://remote.example"})):
            embedded = copy.deepcopy(self.embedded)
            mutate(embedded)
            with self.assertRaises(ValueError):
                self.validate_both({**self.payload, "capacitor.config.json": json.dumps(embedded).encode()})
        for source in ("/assets/missing.js", "https://remote.example/app.js", "../assets/app.js"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.validate_both({**self.payload, "public/index.html": ('<script src="' + source + '"></script>').encode()})

    def test_expo_ipa_requires_nonempty_embedded_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "Fixture.app"
            app.mkdir()
            with self.assertRaises(ValueError):
                release.inspect_ios_payload(app, {"framework": "expo"})
            (app / "main.jsbundle").write_bytes(b"")
            with self.assertRaises(ValueError):
                release.inspect_ios_payload(app, {"framework": "expo"})
            (app / "main.jsbundle").write_bytes(b"synthetic hermes payload")
            release.inspect_ios_payload(app, {"framework": "expo"})


class ExactProductCITests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.config = {"repository": "DruHustle/fixture", "requiredChecks": ["verify", "native"]}
        self.env = {"GITHUB_TOKEN": "synthetic-read-only-token", "GITHUB_RUN_ID": "99"}
        self.checks = [self.check("verify", 1), self.check("native", 2)]

    def check(self, name, identifier):
        return {"name": name, "id": identifier, "head_sha": self.sha, "app": {"id": 15368, "slug": "github-actions"},
                "status": "completed", "conclusion": "success",
                "details_url": f"https://github.com/DruHustle/fixture/actions/runs/10/job/{identifier}"}

    def call(self, *args):
        return {"total_count": len(self.checks), "check_runs": self.checks}

    def test_only_successful_exact_source_independent_product_checks_pass(self):
        ci_gate.verify(self.config, self.sha, self.env, call=self.call)
        for status, conclusion in [("queued", None), ("in_progress", None), ("completed", "skipped"),
                                   ("completed", "neutral"), ("completed", "cancelled"), ("completed", "failure")]:
            with self.subTest(status=status, conclusion=conclusion):
                self.checks[1].update(status=status, conclusion=conclusion)
                with self.assertRaisesRegex(ValueError, "native"):
                    ci_gate.verify(self.config, self.sha, self.env, call=self.call)

    def test_missing_forged_wrong_source_and_current_dispatch_checks_cannot_pass(self):
        for mutate in (lambda checks: checks.pop(),
                       lambda checks: checks[1].update(app={"id": 1, "slug": "other"}),
                       lambda checks: checks[1].update(head_sha="b" * 40),
                       lambda checks: checks[1].update(details_url="https://github.com/DruHustle/fixture/actions/runs/99/job/2")):
            self.checks = [self.check("verify", 1), self.check("native", 2)]
            mutate(self.checks)
            with self.assertRaises(ValueError):
                ci_gate.verify(self.config, self.sha, self.env, call=self.call)

    def test_newer_pending_result_blocks_older_success_and_pagination_is_read(self):
        latest = self.check("native", 3)
        latest.update(status="queued", conclusion=None)
        self.checks.append(latest)
        with self.assertRaises(ValueError):
            ci_gate.verify(self.config, self.sha, self.env, call=self.call)
        self.checks.pop()
        pages = []
        def page_call(repository, sha, page, token):
            pages.append(page)
            return {"total_count": 2, "check_runs": [self.checks[page - 1]]}
        ci_gate.verify(self.config, self.sha, self.env, call=page_call)
        self.assertEqual(pages, [1, 2])

    def test_release_jobs_cannot_be_used_as_their_own_product_gate(self):
        with self.assertRaises(ValueError):
            ci_gate.required_checks({"requiredChecks": ["Native source and release contract"]})


class UnknownAppleOutcomeTests(unittest.TestCase):
    def test_cli_failure_is_neutral_and_never_exposes_command_arguments(self):
        with self.assertRaises(ValueError) as caught:
            release.command("python3", "-c", "import sys; sys.exit(7)", "synthetic-secret")
        self.assertNotIn("synthetic-secret", str(caught.exception))
        self.assertNotIn("no upload completed", str(caught.exception))

    def test_altool_nonzero_timeout_and_interrupt_are_unknown_without_retry(self):
        record = {"appId": "com.onesa.pasofi", "version": "1.2.3", "buildNumber": "17"}
        env = {"APP_STORE_CONNECT_KEY_ID": "SYNTHETIC1", "APP_STORE_CONNECT_ISSUER_ID": "synthetic",
               "APP_STORE_CONNECT_APP_ID": "123"}
        for error in (ValueError("xcrun failed (exit 1)"), subprocess.TimeoutExpired("synthetic-secret", 1), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as directory:
                private = Path(directory)
                with patch.dict(os.environ, env), patch("upload.apple_token", return_value=("synthetic", private / "key.p8")), \
                     patch("upload.verify_apple_destination"), patch("upload.request", return_value={"data": []}), \
                     patch("upload.command", side_effect=[b"--p8-file-path", b"", error]) as command, \
                     self.assertRaisesRegex(ValueError, "Apple upload response unknown") as caught:
                    upload.upload_apple(record, private / "fixture.ipa", private)
                self.assertNotIn("synthetic-secret", str(caught.exception))
                self.assertEqual(sum("--upload-app" in call.args for call in command.call_args_list), 1)

    def test_unknown_receipt_is_preserved_credential_files_removed_and_second_attempt_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            artifacts = work / "artifacts"
            artifacts.mkdir()
            artifact = artifacts / "upload.ipa"
            artifact.write_bytes(b"synthetic signed IPA")
            record = {"schema": 1, "repository": "DruHustle/fixture", "appId": "eu.onesa.fixture", "sourceSha": "a" * 40,
                      "version": "1.2.3", "buildNumber": "17"}
            receipt = {**record, "platform": "ios", "artifactSha256": release.sha256(artifact),
                       "preparedSourceSha256": "b" * 64, "distribution": "signed-not-uploaded"}
            path = artifacts / "receipt.json"
            path.write_text(json.dumps(receipt))
            def unknown(record, artifact, private):
                (private / "synthetic.p8").write_text("synthetic credential")
                raise ValueError("Apple upload response unknown")
            with patch("upload.upload_apple", side_effect=unknown) as provider, self.assertRaises(ValueError):
                upload.upload({}, record, "ios", work, source_digest="b" * 64)
            provider.assert_called_once()
            self.assertEqual(json.loads(path.read_text())["distribution"], "upload-started-outcome-unknown")
            self.assertEqual(list(work.glob("provider-credential-*")), [])
            with patch("upload.upload_apple") as provider, self.assertRaises(ValueError):
                upload.upload({}, record, "ios", work, source_digest="b" * 64)
            provider.assert_not_called()
            path.write_text(json.dumps(receipt))
            with patch("upload.upload_apple") as provider, self.assertRaises(ValueError):
                upload.upload({}, record, "ios", work, source_digest="c" * 64)
            provider.assert_not_called()


if __name__ == "__main__":
    unittest.main()
