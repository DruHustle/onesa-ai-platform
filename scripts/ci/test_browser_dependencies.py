"""Synthetic APT fixtures; never modify a workstation or production host."""

import base64
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import browser_dependencies as browser

# Public verification bytes from the checksum-bound official Noble package.
# Provenance and reviewed rotation policy: docs/engineering/BUILD_AND_TEST.md.
PUBLIC_KEY = base64.b64decode(
    "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"
    "XC0JTOWtJo+wBgADZ3BnAA=="
)


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
        keyring.write_bytes(PUBLIC_KEY)
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
            result = {}
            for path in root.rglob("*"):
                value = path.lstat()
                content = None
                if stat.S_ISREG(value.st_mode):
                    content = path.read_bytes()
                elif stat.S_ISLNK(value.st_mode):
                    content = os.readlink(path)
                result[path.relative_to(root)] = (
                    value.st_mode,
                    value.st_uid,
                    value.st_gid,
                    content,
                )
            return result

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
            self.assertEqual(result["signed_by_paths_rebound"], 2)
            self.assertTrue(result["protected_keyring_created"])
            self.assertFalse(result["signer_bytes_changed"])
            self.assertFalse(result["suites_or_components_changed"])
            self.assertEqual(
                source.read_bytes(),
                before.replace(
                    f"URIs: {browser.ARCHIVE_LIST}".encode(),
                    b"URIs: https://archive.ubuntu.com/ubuntu/",
                    1,
                )
                .replace(
                    f"URIs: {browser.ARCHIVE_LIST}".encode(),
                    b"URIs: https://security.ubuntu.com/ubuntu/",
                    1,
                )
                .replace(
                    f"Signed-By: {browser.UBUNTU_KEYRING}".encode(),
                    f"Signed-By: {browser.PROTECTED_KEYRING}".encode(),
                ),
            )
            self.assertEqual(mirror.read_bytes(), unknown)
            second = browser.prepare(root)
            self.assertEqual(second["mirror_URIs_updated"], 0)
            self.assertEqual(second["signed_by_paths_rebound"], 0)
            self.assertFalse(second["protected_keyring_created"])

    def test_prepare_preserves_bytes_outside_exact_uri_and_key_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            _apt, source, _keyring, _mirror = self.canonical_fixture(root)
            original = (
                self.stanza()
                .replace("Types: deb deb-src", "Types: deb\n deb-src")
                .replace("URIs: ", "URIs:\n\t")
                .replace("Suites: noble ", "Suites: noble\n ")
                .replace("Signed-By: ", "Signed-By:\n\t")
                + "Architectures: amd64 i386\nEnabled: yes \t\n"
            )
            source.write_text(original)
            browser.prepare(root)
            self.assertEqual(
                source.read_text(),
                original.replace(
                    browser.ARCHIVE_LIST, "https://archive.ubuntu.com/ubuntu/"
                ).replace(browser.UBUNTU_KEYRING, browser.PROTECTED_KEYRING),
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

    def test_public_key_fixture_matches_the_reviewed_package_pin(self):
        self.assertEqual(len(PUBLIC_KEY), 3607)
        self.assertEqual(browser.KEYRING_SIZE, 3607)
        self.assertEqual(
            hashlib.sha256(PUBLIC_KEY).hexdigest(),
            "80a36b0a6de2f69f49d2df75ef473ccde121e9e190b9ea01d20a4f63778d5c31",
        )
        self.assertEqual(browser.KEYRING_SHA256, hashlib.sha256(PUBLIC_KEY).hexdigest())

    def test_observed_writable_key_is_copied_without_changing_original_custody(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            _apt, source, original, mirror = self.canonical_fixture(root)
            original.chmod(0o777)
            original.parent.chmod(0o777)
            original.parent.parent.chmod(0o777)
            mirror.chmod(0o666)
            observed = {
                path: (path.read_bytes(), path.stat().st_mode)
                for path in (original, mirror)
            }
            result = browser.prepare(root)
            copy = root / browser.PROTECTED_KEYRING.lstrip("/")
            self.assertTrue(result["protected_keyring_created"])
            self.assertEqual(copy.read_bytes(), PUBLIC_KEY)
            self.assertEqual(stat.S_IMODE(copy.stat().st_mode), 0o644)
            self.assertEqual(stat.S_IMODE(copy.parent.stat().st_mode), 0o755)
            self.assertEqual(copy.stat().st_uid, os.geteuid())
            self.assertEqual(copy.stat().st_gid, os.getegid())
            self.assertEqual(copy.stat().st_nlink, 1)
            self.assertIn(f"Signed-By: {browser.PROTECTED_KEYRING}", source.read_text())
            for path, (content, mode) in observed.items():
                self.assertEqual(path.read_bytes(), content)
                self.assertEqual(path.stat().st_mode, mode)
            self.assertEqual(stat.S_IMODE(original.parent.stat().st_mode), 0o777)
            self.assertEqual(stat.S_IMODE(original.parent.parent.stat().st_mode), 0o777)
            self.assertFalse(browser.prepare(root)["protected_keyring_created"])

    def test_one_bounded_capture_feeds_all_bindings_and_the_copy_without_reopening(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            _apt, source, original, _mirror = self.canonical_fixture(root)
            source.write_text(self.stanza() + "\n" + self.stanza("noble-security"))
            inode = original.stat().st_ino
            original_read = os.read
            original_install = browser.install_key_copy
            reads = []

            def read(fd, length):
                if os.fstat(fd).st_ino == inode:
                    reads.append(length)
                return original_read(fd, length)

            def install(captured, destination, stack):
                self.assertEqual(captured, PUBLIC_KEY)
                # Model a source-path replacement after capture. Publication must
                # still use the held, reviewed buffer, never this replacement.
                original.write_bytes(b"x" * browser.KEYRING_SIZE)
                return original_install(captured, destination, stack)

            with (
                patch.object(browser.os, "read", side_effect=read),
                patch.object(browser, "install_key_copy", side_effect=install),
            ):
                result = browser.prepare(root)
            self.assertEqual(reads, [browser.KEYRING_SIZE + 1])
            self.assertEqual(result["signed_by_paths_rebound"], 2)
            self.assertEqual(
                (root / browser.PROTECTED_KEYRING.lstrip("/")).read_bytes(), PUBLIC_KEY
            )

    def test_unknown_key_bytes_or_unsupported_original_metadata_refuse_without_writes(
        self,
    ):
        for case in (
            "digest",
            "oversize",
            "mode",
            "special mode",
            "hardlink",
            "directory",
            "parent alias",
            "owner",
            "group",
        ):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                _apt, _source, original, _mirror = self.canonical_fixture(root)
                if case == "digest":
                    original.write_bytes(b"x" + PUBLIC_KEY[1:])
                elif case == "oversize":
                    original.write_bytes(PUBLIC_KEY + b"x")
                elif case == "mode":
                    original.chmod(0o640)
                elif case == "special mode":
                    original.chmod(0o4644)
                elif case == "hardlink":
                    os.link(original, original.with_suffix(".alias"))
                elif case == "directory":
                    original.unlink()
                    original.mkdir()
                elif case == "parent alias":
                    target = original.parent.with_name("aliased-keyrings")
                    original.parent.rename(target)
                    original.parent.symlink_to(target, target_is_directory=True)
                if case in {"owner", "group"}:
                    snapshot = original.stat()
                    values = list(snapshot)
                    values[4 if case == "owner" else 5] += 1
                    fake = os.stat_result(values)
                    real_fstat = os.fstat

                    def metadata(
                        fd, _inode=snapshot.st_ino, _fake=fake, _fstat=real_fstat
                    ):
                        current = _fstat(fd)
                        return _fake if current.st_ino == _inode else current

                    with patch.object(browser.os, "fstat", side_effect=metadata):
                        self.refuse_without_writes(root)
                else:
                    self.refuse_without_writes(root)

    def test_fifo_original_refuses_promptly_without_open_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            apt, source, original, _mirror = self.canonical_fixture(root)
            before = source.read_bytes()
            original.unlink()
            os.mkfifo(original, 0o644)
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path; import sys; import browser_dependencies as b; "
                        "b.prepare(Path(sys.argv[1]))"
                    ),
                    str(root),
                ],
                cwd=Path(browser.__file__).parent,
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unsupported pinned Ubuntu keyring metadata", result.stderr)
            self.assertEqual(source.read_bytes(), before)
            self.assertFalse((root / browser.PROTECTED_KEYRING.lstrip("/")).exists())
            self.assertFalse((apt / "apt.conf.d/99-onesa-ci-network").exists())

    def test_unsafe_or_conflicting_copy_destinations_refuse_before_any_write(self):
        cases = (
            "etc writable",
            "apt writable",
            "etc not traversable",
            "apt not traversable",
            "directory writable",
            "directory private",
            "directory alias",
            "key alias",
            "key hardlink",
            "key digest",
            "key mode",
        )
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                apt, _source, original, _mirror = self.canonical_fixture(root)
                copy = root / browser.PROTECTED_KEYRING.lstrip("/")
                if case == "etc writable":
                    (root / "etc").chmod(0o777)
                elif case == "apt writable":
                    apt.chmod(0o777)
                elif case == "etc not traversable":
                    (root / "etc").chmod(0o750)
                elif case == "apt not traversable":
                    apt.chmod(0o750)
                elif case == "directory alias":
                    copy.parent.symlink_to(original.parent, target_is_directory=True)
                else:
                    copy.parent.mkdir(mode=0o755)
                    if case == "directory writable":
                        copy.parent.chmod(0o777)
                    elif case == "directory private":
                        copy.parent.chmod(0o700)
                    elif case == "key alias":
                        copy.symlink_to(original)
                    elif case == "key hardlink":
                        os.link(original, copy)
                    else:
                        copy.write_bytes(PUBLIC_KEY)
                        copy.chmod(0o644)
                        if case == "key digest":
                            copy.write_bytes(b"x" + PUBLIC_KEY[1:])
                        elif case == "key mode":
                            copy.chmod(0o666)
                self.refuse_without_writes(root)

    def test_publication_is_complete_and_no_clobber_if_final_appears_during_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            apt, source, _original, _mirror = self.canonical_fixture(root)
            before = source.read_bytes()
            copy = root / browser.PROTECTED_KEYRING.lstrip("/")
            original_link = os.link
            original_write = os.write
            writes = []

            def write(fd, value):
                self.assertFalse(copy.exists())
                writes.append(len(value))
                return original_write(fd, value)

            def publish(src, dst, **options):
                pending = copy.parent / src
                self.assertEqual(pending.read_bytes(), PUBLIC_KEY)
                self.assertEqual(stat.S_IMODE(pending.stat().st_mode), 0o644)
                copy.write_bytes(b"CONCURRENT_OWNER_FILE")
                return original_link(src, dst, **options)

            with (
                patch.object(browser.os, "write", side_effect=write),
                patch.object(browser.os, "link", side_effect=publish),
                self.assertRaises(FileExistsError),
            ):
                browser.prepare(root)
            self.assertEqual(writes, [browser.KEYRING_SIZE])
            self.assertEqual(copy.read_bytes(), b"CONCURRENT_OWNER_FILE")
            self.assertEqual(list(copy.parent.iterdir()), [copy])
            self.assertEqual(source.read_bytes(), before)
            self.assertFalse((apt / "apt.conf.d/99-onesa-ci-network").exists())

    def test_failed_copy_write_exposes_no_final_key_or_rebound_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            apt, source, _original, _mirror = self.canonical_fixture(root)
            before = source.read_bytes()
            copy = root / browser.PROTECTED_KEYRING.lstrip("/")
            with (
                patch.object(
                    browser.os, "write", side_effect=OSError("fixture disk full")
                ),
                self.assertRaises(OSError),
            ):
                browser.prepare(root)
            self.assertFalse(copy.exists())
            self.assertEqual(list(copy.parent.iterdir()), [])
            self.assertEqual(source.read_bytes(), before)
            self.assertFalse((apt / "apt.conf.d/99-onesa-ci-network").exists())

    def test_idempotent_run_revalidates_both_reviewed_original_and_protected_copy(self):
        for case in ("copy digest", "copy mode", "original digest", "binding"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                _apt, source, original, _mirror = self.canonical_fixture(root)
                browser.prepare(root)
                copy = root / browser.PROTECTED_KEYRING.lstrip("/")
                if case == "copy digest":
                    copy.write_bytes(b"x" + PUBLIC_KEY[1:])
                elif case == "copy mode":
                    copy.chmod(0o777)
                elif case == "original digest":
                    original.write_bytes(b"x" + PUBLIC_KEY[1:])
                else:
                    source.write_text(
                        source.read_text().replace(
                            "https://archive.ubuntu.com/ubuntu/",
                            "https://unknown.invalid/",
                        )
                    )
                self.refuse_without_writes(root)

    def test_disabled_stanza_needs_no_key_copy_and_preserves_all_its_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            _apt, source, original, _mirror = self.canonical_fixture(root)
            original.unlink()
            disabled = self.stanza() + "Enabled: no\n"
            source.write_text(disabled)
            result = browser.prepare(root)
            self.assertEqual(source.read_text(), disabled)
            self.assertEqual(result["signed_by_paths_rebound"], 0)
            self.assertFalse((root / browser.PROTECTED_KEYRING.lstrip("/")).exists())

    def test_protected_key_in_an_unvalidated_legacy_source_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            apt, _source, _original, _mirror = self.canonical_fixture(root)
            (apt / "sources.list.d/zz-legacy.list").write_text(
                f"deb [signed-by={browser.PROTECTED_KEYRING}] "
                "https://archive.ubuntu.com/ubuntu/ noble main\n"
            )
            self.refuse_without_writes(root)

    def test_keyring_refusal_reports_only_fixed_role_metadata_and_preserves_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            apt, source, _original, mirror = self.canonical_fixture(root)
            keyring = root / browser.PROTECTED_KEYRING.lstrip("/")
            keyring.parent.mkdir(mode=0o755)
            secret = b"private-keyring-content-must-not-enter-diagnostics"
            keyring.write_bytes(secret)
            keyring.chmod(0o666)
            observed = keyring.stat()
            source_before = source.read_bytes()
            mirror_before = mirror.read_bytes()
            with self.assertRaises(ValueError) as error:
                browser.prepare(root)
            message = str(error.exception)
            prefix = "Unexpected APT keyring custody: "
            self.assertTrue(message.startswith(prefix))
            self.assertEqual(
                json.loads(message.removeprefix(prefix)),
                {
                    "role": "ubuntu_archive_keyring",
                    "type": "regular",
                    "uid": observed.st_uid,
                    "gid": observed.st_gid,
                    "mode": "0666",
                    "size": observed.st_size,
                    "size_bound": 256 * 1024,
                    "failed_conditions": ["group_or_other_writable"],
                },
            )
            self.assertLess(len(message), 512)
            for forbidden in (
                secret.decode(),
                str(keyring),
                str(root),
                browser.ARCHIVE_LIST,
                browser.UBUNTU_KEYRING,
                "unknown.invalid",
                "GITHUB_ACTIONS",
            ):
                self.assertNotIn(forbidden, message)
            self.assertEqual(source.read_bytes(), source_before)
            self.assertEqual(mirror.read_bytes(), mirror_before)
            self.assertEqual(keyring.read_bytes(), secret)
            self.assertEqual(stat.S_IMODE(keyring.stat().st_mode), 0o666)
            self.assertFalse((apt / "apt.conf.d/99-onesa-ci-network").exists())

    def test_each_custody_refusal_reports_the_single_held_stat_snapshot(self):
        cases = {
            "not_regular": (0, stat.S_IFDIR | 0o644),
            "owner_uid": (4, os.geteuid() + 1),
            "group_or_other_writable": (0, stat.S_IFREG | 0o666),
            "size_bound": (6, 256 * 1024 + 1),
        }
        for condition, (field, value) in cases.items():
            with (
                self.subTest(condition=condition),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory).resolve()
                _apt, _source, keyring, _mirror = self.canonical_fixture(root)
                values = list(keyring.stat())
                values[field] = value
                held = os.stat_result(values)
                original_stat = Path.stat
                reads = []

                def snapshot(
                    path,
                    *args,
                    _keyring=keyring,
                    _reads=reads,
                    _held=held,
                    _original_stat=original_stat,
                    **kwargs,
                ):
                    if path == _keyring and kwargs.get("follow_symlinks", True):
                        _reads.append(path)
                        if len(_reads) != 1:
                            raise AssertionError(
                                "Refusal must not rediscover keyring metadata"
                            )
                        return _held
                    return _original_stat(path, *args, **kwargs)

                with (
                    patch.object(Path, "stat", snapshot),
                    self.assertRaises(ValueError) as error,
                ):
                    browser.regular(keyring, ubuntu_keyring=True)
                diagnostic = json.loads(str(error.exception).split(": ", 1)[1])
                self.assertEqual(reads, [keyring])
                self.assertEqual(diagnostic["failed_conditions"], [condition])
                self.assertEqual(diagnostic["uid"], held.st_uid)
                self.assertEqual(diagnostic["gid"], held.st_gid)
                self.assertEqual(diagnostic["size"], held.st_size)
                self.assertEqual(
                    diagnostic["mode"], f"{stat.S_IMODE(held.st_mode):04o}"
                )
                self.assertEqual(
                    diagnostic["type"],
                    "directory" if condition == "not_regular" else "regular",
                )

    def test_unrelated_source_refusal_keeps_generic_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            _apt, source = self.fixture(root)
            source.chmod(0o666)
            with self.assertRaisesRegex(ValueError, "^Unexpected APT source custody$"):
                browser.prepare(root)

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

    def test_invalid_configuration_parent_is_refused_before_copy_or_source_writes(self):
        for case in ("missing", "non-directory", "writable", "nontraversable"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                apt, _source, _original, _mirror = self.canonical_fixture(root)
                parent = apt / "apt.conf.d"
                if case in {"missing", "non-directory"}:
                    parent.rmdir()
                    if case == "non-directory":
                        parent.write_bytes(b"OWNER_FILE")
                elif case == "writable":
                    parent.chmod(0o777)
                else:
                    parent.chmod(0o750)
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
