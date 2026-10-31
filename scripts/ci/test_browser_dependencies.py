"""Synthetic APT fixtures; never modify a workstation or production host."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import browser_dependencies as browser


class BrowserDependenciesTests(unittest.TestCase):
    def test_legacy_preserves_suites_components_keys_and_other_hosts(self):
        text = (
            "# http://azure.archive.ubuntu.com/ubuntu/ remains a comment\n"
            "deb [arch=amd64 signed-by=/keys/ubuntu.gpg] "
            "http://azure.archive.ubuntu.com/ubuntu/ noble-updates main universe\n"
            "deb https://packages.microsoft.com/ubuntu noble main\n"
        )
        result, count = browser.rewrite_sources(text)
        self.assertEqual(count, 1)
        self.assertEqual(
            result,
            text.replace(
                "http://azure.archive.ubuntu.com/ubuntu/ noble-updates",
                "https://archive.ubuntu.com/ubuntu/ noble-updates",
            ),
        )

    def test_deb822_preserves_all_non_uri_fields_and_continuations(self):
        text = (
            "Types: deb deb-src\nURIs: http://azure.archive.ubuntu.com/ubuntu/\n"
            " https://archive.ubuntu.com/ubuntu/\n"
            "Suites: noble noble-updates noble-security\n"
            "Components: main restricted universe multiverse\n"
            "Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n"
        )
        result, count = browser.rewrite_sources(text, True)
        self.assertEqual(count, 1)
        self.assertEqual(
            result,
            text.replace(
                "http://azure.archive.ubuntu.com/ubuntu/",
                "https://archive.ubuntu.com/ubuntu/",
            ),
        )

    def test_lookalike_host_is_unchanged(self):
        text = "deb https://azure.archive.ubuntu.com.example/ubuntu noble main\n"
        self.assertEqual(browser.rewrite_sources(text), (text, 0))

    def test_credentialed_or_unexpected_mirror_is_rejected(self):
        for uri in [
            "https://user:password@azure.archive.ubuntu.com/ubuntu",
            "https://azure.archive.ubuntu.com:444/ubuntu",
            "https://azure.archive.ubuntu.com/other",
            "https://azure.archive.ubuntu.com/ubuntu?override=1",
        ]:
            with self.subTest(uri=uri), self.assertRaises(ValueError):
                browser.rewrite_sources("deb " + uri + " noble main\n")

    def test_refuses_local_persistent_and_unrelated_runner(self):
        for values in [
            {},
            {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "self-hosted"},
            {
                "GITHUB_ACTIONS": "true",
                "RUNNER_ENVIRONMENT": "github-hosted",
                "RUNNER_OS": "Linux",
                "GITHUB_REPOSITORY": "someone/else",
            },
        ]:
            with (
                patch.dict(os.environ, values, clear=True),
                self.assertRaises(ValueError),
            ):
                browser.require_runner()

    def test_accepts_only_the_expected_disposable_root_runner(self):
        values = {
            "GITHUB_ACTIONS": "true",
            "RUNNER_ENVIRONMENT": "github-hosted",
            "RUNNER_OS": "Linux",
            "GITHUB_REPOSITORY": "DruHustle/onesa-ai-platform",
        }
        with (
            patch.dict(os.environ, values, clear=True),
            patch.object(browser.platform, "system", return_value="Linux"),
            patch.object(browser.os, "geteuid", return_value=0),
        ):
            browser.require_runner()

    def fixture(self, root):
        apt = root / "etc/apt"
        (apt / "sources.list.d").mkdir(parents=True)
        (apt / "apt.conf.d").mkdir()
        source = apt / "sources.list.d/ubuntu.sources"
        source.write_text(
            "URIs: http://azure.archive.ubuntu.com/ubuntu/\n"
            "Suites: noble noble-security\nSigned-By: /keys/ubuntu.gpg\n"
        )
        source.chmod(0o644)
        return apt, source

    def stanza(self, suites="noble noble-updates noble-backports"):
        return (
            "Types: deb deb-src\n"
            f"URIs: {browser.ARCHIVE_LIST}\n"
            f"Suites: {suites}\n"
            "Components: main restricted universe multiverse\n"
            f"Signed-By: {browser.UBUNTU_KEYRING}\n"
        )

    def canonical_fixture(self, root):
        apt, source = self.fixture(root)
        keyring = root / browser.UBUNTU_KEYRING.lstrip("/")
        keyring.parent.mkdir(parents=True)
        keyring.write_bytes(b"synthetic-keyring-for-offline-parser-tests-only")
        keyring.chmod(0o644)
        source.write_text(self.stanza())
        mirror = apt / "apt-mirrors.txt"
        # This untrusted and deliberately undecodable file must never be read.
        mirror.write_bytes(
            b"\xffunreviewed mirror metadata\nhttps://unknown.invalid/ubuntu/\n"
        )
        return apt, source, keyring, mirror

    def refuse_without_writes(self, root):
        def snapshot():
            return {
                path.relative_to(root): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }

        before = snapshot()
        with self.assertRaises((ValueError, OSError)):
            browser.prepare(root)
        self.assertEqual(snapshot(), before)

    def test_fixture_rewrite_is_idempotent_and_config_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            apt, source = self.fixture(root)
            first = browser.prepare(root)
            second = browser.prepare(root)
            self.assertEqual(first["mirror_URIs_updated"], 1)
            self.assertEqual(second["mirror_URIs_updated"], 0)
            self.assertIn("Signed-By: /keys/ubuntu.gpg", source.read_text())
            self.assertEqual(
                (apt / "apt.conf.d/99-onesa-ci-network").read_text(), browser.NETWORK
            )
            self.assertIn('APT::Update::Error-Mode "any";', browser.NETWORK)
            self.assertNotIn("AllowUnauthenticated", browser.NETWORK)
            self.assertNotIn("AllowInsecure", browser.NETWORK)

    def test_conflicting_config_preserves_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            apt, source = self.fixture(root)
            config = apt / "apt.conf.d/99-onesa-ci-network"
            config.write_text("OWNER_CONFIG\n")
            config.chmod(0o644)
            before = source.read_bytes()
            with self.assertRaises(ValueError):
                browser.prepare(root)
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(config.read_text(), "OWNER_CONFIG\n")

    def test_prepare_selects_archive_and_security_without_reading_unknown_list(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            _apt, source, _keyring, mirror = self.canonical_fixture(root)
            text = (
                f"# Original transport: {browser.ARCHIVE_LIST}\n"
                + self.stanza()
                + "\n"
                + self.stanza("noble-security")
            ).replace("\n", "\r\n")
            before = text.encode()
            source.write_bytes(before)
            unknown = mirror.read_bytes()
            result = browser.prepare(root)
            self.assertEqual(result["source_files_updated"], 1)
            self.assertEqual(result["mirror_list_files_updated"], 0)
            self.assertEqual(result["archive_indirections_replaced"], 2)
            self.assertEqual(result["mirror_URIs_updated"], 2)
            self.assertEqual(
                source.read_bytes(),
                before.replace(
                    f"URIs: {browser.ARCHIVE_LIST}".encode(),
                    b"URIs: https://archive.ubuntu.com/ubuntu/",
                    1,
                ).replace(
                    f"URIs: {browser.ARCHIVE_LIST}".encode(),
                    b"URIs: https://security.ubuntu.com/ubuntu/",
                    1,
                ),
            )
            self.assertEqual(mirror.read_bytes(), unknown)
            self.assertEqual(browser.prepare(root)["mirror_URIs_updated"], 0)

    def test_prepare_preserves_valid_continuations_and_non_uri_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            _apt, source, _keyring, _mirror = self.canonical_fixture(root)
            original = (
                self.stanza()
                .replace("Types: deb deb-src", "Types: deb\n deb-src")
                .replace("URIs: ", "URIs:\n\t")
                .replace("Suites: noble ", "Suites: noble\n ")
                + "Architectures: amd64 i386\nEnabled: yes \t\n"
            )
            source.write_text(original)
            browser.prepare(root)
            self.assertEqual(
                source.read_text(),
                original.replace(
                    browser.ARCHIVE_LIST, "https://archive.ubuntu.com/ubuntu/"
                ),
            )

    def test_prepare_rejects_ambiguous_or_unauthenticated_stanzas_before_writes(self):
        valid = self.stanza()
        invalid = {
            "missing types": valid.replace("Types: deb deb-src\n", ""),
            "missing components": valid.replace(
                "Components: main restricted universe multiverse\n", ""
            ),
            "missing key": valid.replace(f"Signed-By: {browser.UBUNTU_KEYRING}\n", ""),
            "duplicate URI": valid + f"uRiS: {browser.ARCHIVE_LIST}\n",
            "duplicate key": valid + f"SIGNED-BY: {browser.UBUNTU_KEYRING}\n",
            "mixed targets": valid.replace(
                browser.ARCHIVE_LIST,
                browser.ARCHIVE_LIST + " https://archive.ubuntu.com/ubuntu/",
            ),
            "duplicate target": valid.replace(
                browser.ARCHIVE_LIST, browser.ARCHIVE_LIST + " " + browser.ARCHIVE_LIST
            ),
            "alternate list": valid.replace(
                browser.ARCHIVE_LIST, "mirror+file:/etc/apt/other.txt"
            ),
            "alternate path": valid.replace(
                browser.ARCHIVE_LIST, "mirror+file:///etc/apt/apt-mirrors.txt"
            ),
            "query": valid.replace(
                browser.ARCHIVE_LIST, browser.ARCHIVE_LIST + "?override=1"
            ),
            "fragment": valid.replace(
                browser.ARCHIVE_LIST, browser.ARCHIVE_LIST + "#override"
            ),
            "remote mirror": valid.replace(
                browser.ARCHIVE_LIST, "mirror+https://unknown.invalid/list"
            ),
            "wrong key": valid.replace(browser.UBUNTU_KEYRING, "/keys/other.gpg"),
            "multiple keys": valid.replace(
                browser.UBUNTU_KEYRING, browser.UBUNTU_KEYRING + " /keys/other.gpg"
            ),
            "trusted override": valid + "Trusted: yes\n",
            "insecure override": valid + "Allow-Insecure: yes\n",
            "unknown field": valid + "Unknown: value\n",
            "wrong suite": valid.replace("noble-updates", "jammy-updates"),
            "mixed security": valid.replace("noble-backports", "noble-security"),
            "duplicate suite": valid.replace("noble-backports", "noble"),
            "suite options": valid.replace("noble-backports", "[trusted=yes]"),
            "wrong component": valid.replace("multiverse", "custom"),
            "duplicate component": valid.replace("multiverse", "main"),
            "wrong type": valid.replace("deb-src", "rpm"),
            "duplicate type": valid.replace("deb-src", "deb"),
            "unsupported architecture": valid + "Architectures: arm64\n",
            "missing native architecture": valid + "Architectures: i386\n",
            "duplicate architecture": valid + "Architectures: amd64 amd64\n",
            "ambiguous activation": valid + "Enabled: maybe\n",
            "duplicate activation": valid + "Enabled: no\nEnabled: yes\n",
            "inline URI comment": valid.replace(
                browser.ARCHIVE_LIST, browser.ARCHIVE_LIST + " # comment"
            ),
            "inline suite comment": valid.replace(
                "noble-backports", "noble-backports # comment"
            ),
            "indented comment": valid.replace(
                "URIs: ", " # ambiguous continuation\nURIs: "
            ),
            "orphan continuation": " continuation\n" + valid,
            "malformed line": valid + "not a field\n",
            "control character": valid.replace(
                "Components: main", "Components: main\x00"
            ),
        }
        for case, text in invalid.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                apt, _source, _keyring, _mirror = self.canonical_fixture(root)
                # A valid earlier source is planned first, but nothing may be written.
                (apt / "sources.list.d/zz-ambiguous.sources").write_text(text)
                self.refuse_without_writes(root)

    def test_prepare_rejects_legacy_active_archive_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            apt, _source, _keyring, _mirror = self.canonical_fixture(root)
            (apt / "sources.list.d/zz-legacy.list").write_text(
                f"deb {browser.ARCHIVE_LIST} noble main\n"
            )
            self.refuse_without_writes(root)

    def test_prepare_validates_keyring_custody_before_writing_sources(self):
        for case in ("empty", "writable", "symlink", "missing"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                _apt, _source, keyring, _mirror = self.canonical_fixture(root)
                if case == "empty":
                    keyring.write_bytes(b"")
                elif case == "writable":
                    keyring.chmod(0o666)
                elif case == "symlink":
                    target = keyring.with_suffix(".original")
                    keyring.rename(target)
                    keyring.symlink_to(target)
                else:
                    keyring.unlink()
                self.refuse_without_writes(root)

    def test_prepare_preserves_disabled_stanza_and_unused_mirror_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            _apt, source, keyring, mirror = self.canonical_fixture(root)
            disabled = self.stanza("noble-security") + "Enabled: no \t\n"
            source.write_text(self.stanza() + "\n" + disabled)
            mirror.unlink()
            mirror.symlink_to(keyring)
            before = keyring.read_bytes()
            result = browser.prepare(root)
            self.assertEqual(result["archive_indirections_replaced"], 1)
            self.assertTrue(source.read_text().endswith(disabled))
            self.assertTrue(mirror.is_symlink())
            self.assertEqual(keyring.read_bytes(), before)

    def test_canonical_selection_preserves_conflicting_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            apt, _source, _keyring, _mirror = self.canonical_fixture(root)
            config = apt / "apt.conf.d/99-onesa-ci-network"
            config.write_text("OWNER_CONFIG\n")
            config.chmod(0o644)
            self.refuse_without_writes(root)

    @unittest.skipUnless(
        Path("/usr/bin/apt-get").is_file(), "Native APT parser unavailable"
    )
    def test_native_apt_prints_only_expected_canonical_targets_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            apt, source, _keyring, mirror = self.canonical_fixture(root)
            source.write_text(self.stanza() + "\n" + self.stanza("noble-security"))
            before = mirror.read_bytes()
            browser.prepare(root)
            for relative in (
                "var/lib/apt/lists/partial",
                "var/cache/apt",
                "var/log/apt",
            ):
                (root / relative).mkdir(parents=True, exist_ok=True)
            (apt / "sources.list").write_text("")
            result = subprocess.run(
                [
                    "/usr/bin/apt-get",
                    "--print-uris",
                    "-o",
                    f"Dir={root}",
                    "-o",
                    "Dir::Etc::main=/dev/null",
                    "-o",
                    f"Dir::Etc::parts={apt / 'apt.conf.d'}",
                    "-o",
                    f"Dir::Etc::sourcelist={apt / 'sources.list'}",
                    "-o",
                    f"Dir::Etc::sourceparts={apt / 'sources.list.d'}",
                    "-o",
                    f"Dir::State::lists={root / 'var/lib/apt/lists'}",
                    "-o",
                    f"Dir::Cache={root / 'var/cache/apt'}",
                    "-o",
                    f"Dir::Log={root / 'var/log/apt'}",
                    "-o",
                    "APT::Architecture=amd64",
                    "-o",
                    "Debug::NoLocking=true",
                    "update",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
                env={
                    key: value
                    for key, value in os.environ.items()
                    if key != "APT_CONFIG"
                },
            )
            self.assertIn(
                "https://archive.ubuntu.com/ubuntu/dists/noble/InRelease", result.stdout
            )
            self.assertIn(
                "https://archive.ubuntu.com/ubuntu/dists/noble-updates/InRelease",
                result.stdout,
            )
            self.assertIn(
                "https://archive.ubuntu.com/ubuntu/dists/noble-backports/InRelease",
                result.stdout,
            )
            self.assertIn(
                "https://security.ubuntu.com/ubuntu/dists/noble-security/InRelease",
                result.stdout,
            )
            self.assertNotIn("mirror+", result.stdout)
            self.assertNotIn("unknown.invalid", result.stdout)
            self.assertEqual(mirror.read_bytes(), before)
            self.assertEqual(
                list((root / "var/lib/apt/lists").iterdir()),
                [root / "var/lib/apt/lists/partial"],
            )

    def test_unreferenced_mirror_file_is_never_modified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            apt, _source = self.fixture(root)
            mirror = apt / "apt-mirrors.txt"
            mirror.write_text("UNRELATED OWNER CONFIGURATION\n")
            before = mirror.read_bytes()
            browser.prepare(root)
            self.assertEqual(mirror.read_bytes(), before)

    def test_source_alias_is_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            apt, source = self.fixture(root)
            (apt / "sources.list.d/alias.sources").symlink_to(source)
            before = source.read_bytes()
            with self.assertRaises(ValueError):
                browser.prepare(root)
            self.assertEqual(source.read_bytes(), before)
            self.assertFalse((apt / "apt.conf.d/99-onesa-ci-network").exists())


if __name__ == "__main__":
    unittest.main()
