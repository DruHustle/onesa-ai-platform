import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import release
import upload


class ReleaseContractTests(unittest.TestCase):
    def setUp(self):
        self.config = {"appId": "eu.onesa.fixture", "framework": "expo", "mobilePath": "mobile", "scheme": "Fixture"}
        self.record = {"appId": "eu.onesa.fixture", "version": "1.2.3", "buildNumber": "17"}

    def test_missing_inputs_report_names_without_values(self):
        with self.assertRaises(ValueError) as caught:
            release.preflight("android", {"ANDROID_PLAY_UPLOAD_STORE_PASSWORD": "synthetic-secret-value"})
        self.assertIn("ANDROID_PLAY_UPLOAD_KEYSTORE_BASE64", str(caught.exception))
        self.assertNotIn("synthetic-secret-value", str(caught.exception))

    def test_all_credential_names_are_removed_from_build_children(self):
        values = {name: "synthetic" for names in release.SECRET_NAMES.values() for name in names}
        with patch.dict(os.environ, {**values, "GITHUB_TOKEN": "synthetic", "CI": "1"}):
            env = release.public_environment()
        self.assertEqual(env["CI"], "1")
        self.assertFalse(set(values) & set(env))
        self.assertNotIn("GITHUB_TOKEN", env)

    def test_build_counter_rejects_shell_text_zero_and_overflow(self):
        for value in ("", "0", "01", "-1", "1.2", "1\n", "$(id)", "2100000001", "99999999999"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                release.build_number(value)
        self.assertEqual(release.build_number("2100000000"), "2100000000")

    def test_signer_pin_is_a_complete_sha256(self):
        self.assertEqual(release.fingerprint(":".join(["AB"] * 32)), "ab" * 32)
        for value in ("", "ab" * 20, "g" * 64):
            with self.assertRaises(ValueError):
                release.fingerprint(value)

    def test_source_must_be_canonical_main_and_still_current_before_upload(self):
        sha = "a" * 40
        config = {"repository": "DruHustle/fixture"}
        env = {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
               "GITHUB_REPOSITORY": config["repository"], "GITHUB_SHA": sha}
        with patch("release.command", side_effect=[sha.encode(), b"", (sha + "\trefs/heads/main").encode()]), patch("release.ci_gate.verify") as checks:
            release.check_source(config, sha, env=env)
        checks.assert_called_once_with(config, sha, env)
        with patch("release.command") as run, self.assertRaises(ValueError):
            release.check_source(config, sha, env={**env, "GITHUB_REF": "refs/heads/topic"})
        run.assert_not_called()
        with patch("release.command", side_effect=[sha.encode(), b"", ("b" * 40 + "\trefs/heads/main").encode()]), self.assertRaises(ValueError):
            release.check_source(config, sha, env=env)

    def profile(self):
        cert = b"public-test-certificate"
        return {"UUID": "00000000-0000-4000-8000-000000000000", "TeamIdentifier": ["ABCDEFGHIJ"],
                "ExpirationDate": dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1),
                "DeveloperCertificates": [cert], "Entitlements": {"application-identifier": "OLDPREFIX.eu.onesa.fixture",
                "com.apple.developer.team-identifier": "ABCDEFGHIJ", "get-task-allow": False}}, hashlib.sha256(cert).hexdigest()

    def test_profile_preserves_legacy_prefix_separate_from_team(self):
        profile, pin = self.profile()
        self.assertEqual(release.validate_profile(profile, self.config, "ABCDEFGHIJ", pin), "OLDPREFIX.eu.onesa.fixture")

    def test_profile_rejects_expiry_wrong_team_wildcard_debug_and_wrong_cert(self):
        mutations = [lambda p: p.update(ExpirationDate=dt.datetime(2000, 1, 1)),
                     lambda p: p.update(TeamIdentifier=["OTHERTEAM1"]),
                     lambda p: p.update(ProvisionedDevices=["device"]),
                     lambda p: p.update(ProvisionsAllDevices=True),
                     lambda p: p.update(DeveloperCertificates=[b"other"]),
                     lambda p: p["Entitlements"].update({"application-identifier": "OLDPREFIX.*"}),
                     lambda p: p["Entitlements"].update({"get-task-allow": True})]
        for mutate in mutations:
            profile, pin = self.profile()
            mutate(profile)
            with self.assertRaises(ValueError):
                release.validate_profile(profile, self.config, "ABCDEFGHIJ", pin)

    def test_native_counter_stamp_preserves_marketing_version_and_app_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mobile = root / "mobile"
            (mobile / "android/app").mkdir(parents=True)
            (mobile / "android/app/build.gradle").write_text('defaultConfig {\n applicationId "eu.onesa.fixture"\n versionCode 1\n versionName "1.2.3"\n}\n')
            config = {"expo": {"version": "1.2.3", "android": {"package": "eu.onesa.fixture"}, "ios": {"bundleIdentifier": "eu.onesa.fixture"}}}
            (mobile / "app.json").write_text(json.dumps(config))
            release.stamp_native(self.config, self.record, "android", root)
            self.assertIn('versionCode 17', (mobile / "android/app/build.gradle").read_text())
            updated = json.loads((mobile / "app.json").read_text())["expo"]
            self.assertEqual(updated["version"], "1.2.3")
            self.assertEqual(updated["android"]["package"], "eu.onesa.fixture")
            self.assertEqual(updated["ios"]["buildNumber"], "17")

    def test_ios_info_rejects_simulator_wrong_version_and_old_sdk(self):
        info = {"CFBundleIdentifier": self.record["appId"], "CFBundleVersion": "17",
                "CFBundleShortVersionString": "1.2.3", "CFBundleSupportedPlatforms": ["iPhoneOS"],
                "DTPlatformName": "iphoneos", "DTXcode": "2600"}
        release.validate_ios_info(info, self.config, self.record)
        for key, value in [("CFBundleVersion", "18"), ("CFBundleIdentifier", "eu.onesa.other"),
                           ("CFBundleSupportedPlatforms", ["iPhoneSimulator"]), ("DTXcode", "1600")]:
            with self.assertRaises(ValueError):
                release.validate_ios_info({**info, key: value}, self.config, self.record)

    def test_provider_redirect_and_nonallowlisted_host_are_refused(self):
        for url in ("http://androidpublisher.googleapis.com/", "https://example.com/", "https://androidpublisher.googleapis.com@evil.test/"):
            with self.assertRaises(ValueError):
                upload.request("GET", url, "synthetic")
        self.assertIsNone(upload.NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.test"))

    def test_jwt_es256_uses_valid_raw_signature_from_real_openssl(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory)
            key = private / "key.pem"
            subprocess.run(["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(key)], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            token = upload.jwt({"alg": "ES256", "typ": "JWT"}, {"iss": "synthetic", "exp": 123}, key, ec=True)
            signature = base64.urlsafe_b64decode(token.split(".")[2] + "==")
            self.assertEqual(len(signature), 64)
            # Convert JWT raw signature back to DER and verify the actual signed bytes.
            encoded = []
            for part in (signature[:32], signature[32:]):
                value = part.lstrip(b"\0") or b"\0"
                if value[0] & 0x80:
                    value = b"\0" + value
                encoded.append(b"\x02" + bytes([len(value)]) + value)
            content = b"".join(encoded)
            (private / "signature").write_bytes(b"\x30" + bytes([len(content)]) + content)
            public = release.command("openssl", "pkey", "-in", key, "-pubout")
            (private / "public.pem").write_bytes(public)
            result = release.command("openssl", "dgst", "-sha256", "-verify", private / "public.pem",
                                     "-signature", private / "signature", data=".".join(token.split(".")[:2]).encode())
            self.assertIn(b"Verified OK", result)

    def test_external_or_other_app_testflight_group_is_refused(self):
        env = {"APP_STORE_CONNECT_APP_ID": "123", "APP_STORE_CONNECT_INTERNAL_GROUP_ID": "group"}
        def call(method, url, token):
            if "/apps/" in url:
                return {"data": {"id": "123", "attributes": {"bundleId": self.record["appId"]}}}
            return {"data": {"id": "group", "attributes": {"isInternalGroup": False},
                             "relationships": {"app": {"data": {"id": "123"}}}}}
        with patch.dict(os.environ, env), self.assertRaises(ValueError):
            upload.verify_apple_destination(self.record, "synthetic", call=call)

    def test_apple_build_requires_both_marketing_and_build_version(self):
        result = {"data": [{"id": "b", "attributes": {"version": "17"}, "relationships": {"preReleaseVersion": {"data": {"id": "v"}}}}],
                  "included": [{"type": "preReleaseVersions", "id": "v", "attributes": {"version": "1.2.3", "platform": "IOS"}}]}
        self.assertEqual(upload.matching_apple_build(result, self.record)["id"], "b")
        result["included"][0]["attributes"]["version"] = "1.2.2"
        self.assertIsNone(upload.matching_apple_build(result, self.record))


class PlayTransactionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.artifact = Path(self.directory.name) / "fixture.aab"
        self.artifact.write_bytes(b"synthetic-bundle")
        self.record = {"appId": "eu.onesa.fixture", "version": "1.2.3", "buildNumber": "17"}
        self.calls = []
        self.fail = None
        self.existing = "16"
        self.wrong_hash = False

    def tearDown(self):
        self.directory.cleanup()

    def call(self, method, url, token, body=None, content_type=None):
        self.calls.append((method, url, body))
        if self.fail and self.fail in url:
            raise ValueError("synthetic provider outcome")
        if method == "DELETE":
            return {}
        if url.endswith("/edits"):
            return {"id": "owned-edit"}
        if url.endswith("/tracks"):
            return {"tracks": [{"track": "internal", "releases": [{"versionCodes": [self.existing]}]},
                               {"track": "production", "releases": [{"versionCodes": ["15"]}]}]}
        if "/bundles?" in url:
            return {"versionCode": 17, "sha256": "0" * 64 if self.wrong_hash else release.sha256(self.artifact)}
        if url.endswith("/tracks/internal"):
            return body
        if ":commit?" in url:
            return {"id": "owned-edit"}
        return {}

    def test_internal_only_hash_bound_validate_then_commit(self):
        result = upload.upload_google(self.record, self.artifact, "synthetic", call=self.call)
        self.assertEqual(result["distribution"], "internal-track-committed")
        writes = [(method, url, body) for method, url, body in self.calls if method == "PUT"]
        self.assertEqual(len(writes), 1)
        self.assertTrue(writes[0][1].endswith("/tracks/internal"))
        self.assertEqual(writes[0][2]["releases"][0]["versionCodes"], ["17"])
        self.assertTrue(self.calls[-2][1].endswith(":validate"))
        self.assertTrue(self.calls[-1][1].endswith(":commit?changesInReviewBehavior=ERROR_IF_IN_REVIEW"))

    def test_duplicate_build_is_rejected_before_upload_and_owned_edit_deleted(self):
        self.existing = "17"
        with self.assertRaises(ValueError):
            upload.upload_google(self.record, self.artifact, "synthetic", call=self.call)
        self.assertFalse(any("/bundles?" in url for _, url, _ in self.calls))
        self.assertEqual(self.calls[-1][0], "DELETE")

    def test_wrong_uploaded_hash_never_updates_track(self):
        self.wrong_hash = True
        with self.assertRaises(ValueError):
            upload.upload_google(self.record, self.artifact, "synthetic", call=self.call)
        self.assertFalse(any(method == "PUT" for method, _, _ in self.calls))
        self.assertEqual(self.calls[-1][0], "DELETE")

    def test_validation_failure_never_commits(self):
        self.fail = ":validate"
        with self.assertRaises(ValueError):
            upload.upload_google(self.record, self.artifact, "synthetic", call=self.call)
        self.assertFalse(any(":commit" in url for _, url, _ in self.calls))
        self.assertEqual(self.calls[-1][0], "DELETE")

    def test_unknown_commit_is_not_retried_or_deleted(self):
        self.fail = ":commit"
        with self.assertRaises(ValueError):
            upload.upload_google(self.record, self.artifact, "synthetic", call=self.call)
        self.assertEqual(sum(":commit" in url for _, url, _ in self.calls), 1)
        self.assertFalse(any(method == "DELETE" for method, _, _ in self.calls))


if __name__ == "__main__":
    unittest.main()
