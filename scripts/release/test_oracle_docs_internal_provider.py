"""Private disposable custody and fake HTTPS replies; never provider access."""

import io
import os
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import oracle_docs_internal_provider as provider
import oracle_owner as owner


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            dir=Path.home() if os.getuid() == 0 else None
        )
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.root.chmod(0o700)
        self.path = self.root / "publisher.json"
        self.enterContext(patch.object(provider, "PUBLISHER", self.path))
        self.now = datetime.now(timezone.utc)
        self.configuration = {
            "account_id": "a" * 32,
            "applications": {"canonical": "b" * 36, "wildcard": "c" * 36},
        }
        self.value = {
            "schema_version": 1,
            "purpose": "existing-cloudflare-pages-publisher",
            "account_id": "a" * 32,
            "token": "synthetic-provider-fixture-not-a-working-token",
            "expires_at": (self.now + timedelta(hours=1)).isoformat(),
            "release_authority": False,
        }
        self.write()

    def write(self):
        self.path.write_bytes(owner.canonical(self.value))
        self.path.chmod(0o600)

    def test_current_private_custody_is_only_a_provider_credential(self):
        self.assertEqual(
            provider.custody(self.path, "a" * 32, uid=os.getuid(), now=self.now),
            self.value["token"],
        )

    def test_wrong_account_purpose_expiry_authority_or_schema_refused(self):
        for key, value in [
            ("account_id", "b" * 32),
            ("purpose", "owner-authorization"),
            ("expires_at", (self.now - timedelta(seconds=1)).isoformat()),
            ("expires_at", (self.now + timedelta(days=3)).isoformat()),
            ("release_authority", True),
            ("schema_version", True),
            ("token", "synthetic token with spaces"),
            ("token", "x" * 25 + "\x00"),
            ("token", "x" * 25 + "é"),
        ]:
            original = self.value[key]
            self.value[key] = value
            self.write()
            with self.subTest(key=key), self.assertRaises(owner.Rejected):
                provider.custody(self.path, "a" * 32, uid=os.getuid(), now=self.now)
            self.value[key] = original

    def test_symlink_and_permissive_custody_refused(self):
        self.path.chmod(0o644)
        with self.assertRaises(owner.Rejected):
            provider.custody(self.path, "a" * 32, uid=os.getuid(), now=self.now)
        self.path.chmod(0o600)
        alias = self.root / "alias.json"
        alias.symlink_to(self.path)
        with self.assertRaises(owner.Rejected):
            provider.custody(alias, "a" * 32, uid=os.getuid(), now=self.now)

    def test_unknown_account_project_url_token_endpoint_and_paths_refused_before_custody(
        self,
    ):
        for path in [
            "https://foreign.example.invalid",
            "/pages/projects/other",
            "/access/apps/" + "d" * 36,
            "/tokens",
            "/pages/projects/onesa-engineering-docs/../other",
            "/pages/projects/onesa-engineering-docs/deployments?per_page=25&page=42",
            "/pages/projects/onesa-engineering-docs#fragment",
        ]:
            with (
                self.subTest(path=path),
                patch.object(provider, "custody") as credential,
                self.assertRaises(owner.Rejected),
            ):
                provider.get(path, self.configuration, uid=os.getuid())
            credential.assert_not_called()

    def test_only_fixed_https_get_is_dispatched_without_redirect(self):
        captured = []

        class Response(io.BytesIO):
            status = 200

        def read(request, timeout):
            captured.append(request)
            self.assertEqual(timeout, 30)
            return Response(b'{"success":true,"result":{"id":"synthetic"}}')

        with patch.object(
            provider.urllib.request,
            "build_opener",
            return_value=SimpleNamespace(open=read),
        ) as opener:
            self.assertEqual(
                provider.get(
                    "/pages/projects/onesa-engineering-docs",
                    self.configuration,
                    uid=os.getuid(),
                )["result"],
                {"id": "synthetic"},
            )
        self.assertIsInstance(opener.call_args.args[0], provider.NoRedirect)
        self.assertEqual(captured[0].method, "GET")
        self.assertEqual(
            captured[0].full_url,
            "https://api.cloudflare.com/client/v4/accounts/"
            + "a" * 32
            + "/pages/projects/onesa-engineering-docs",
        )
        self.assertIsNone(
            provider.NoRedirect().redirect_request(None, None, None, None, None, None)
        )

    def test_access_reads_use_only_the_separate_readonly_custody(self):
        class Response(io.BytesIO):
            status = 200

        with (
            patch.object(
                provider, "custody", return_value="synthetic-readonly-fixture-token"
            ) as credential,
            patch.object(
                provider.urllib.request,
                "build_opener",
                return_value=SimpleNamespace(
                    open=lambda *_a, **_k: Response(b'{"success":true,"result":{}}')
                ),
            ),
        ):
            provider.get("/access/organizations", self.configuration, uid=os.getuid())
        self.assertEqual(credential.call_args.args[0], provider.ACCESS)

    def test_redirect_denied_incomplete_oversized_or_failed_responses_never_succeed(
        self,
    ):
        for error in [
            urllib.error.HTTPError(
                "https://api.cloudflare.com", 302, "redirect", {}, io.BytesIO()
            ),
            urllib.error.HTTPError(
                "https://api.cloudflare.com", 403, "denied", {}, io.BytesIO()
            ),
            urllib.error.URLError("synthetic transport failure"),
        ]:
            with (
                patch.object(
                    provider.urllib.request,
                    "build_opener",
                    return_value=SimpleNamespace(
                        open=lambda *_a, error=error, **_k: (_ for _ in ()).throw(error)
                    ),
                ),
                self.assertRaises(owner.Rejected),
            ):
                provider.get(
                    "/pages/projects/onesa-engineering-docs",
                    self.configuration,
                    uid=os.getuid(),
                )

        class Response(io.BytesIO):
            status = 200

        for raw in [
            b'{"success":false,"result":{}}',
            b'{"success":true}',
            b"not-json",
            b"x" * (provider.MAX_RESPONSE + 1),
        ]:
            with (
                patch.object(
                    provider.urllib.request,
                    "build_opener",
                    return_value=SimpleNamespace(
                        open=lambda *_a, raw=raw, **_k: Response(raw)
                    ),
                ),
                self.assertRaises(owner.Rejected),
            ):
                provider.get(
                    "/pages/projects/onesa-engineering-docs",
                    self.configuration,
                    uid=os.getuid(),
                )


class DeploymentPaginationTests(unittest.TestCase):
    def row(self, number):
        return {"id": f"{number:08x}-0000-4000-8000-000000000000"}

    def response(self, rows, **info):
        return {"result": rows, "result_info": info}

    def test_all_pages_are_consumed_until_the_complete_total(self):
        first = [self.row(i) for i in range(25)]
        with patch.object(
            provider,
            "get",
            side_effect=[
                self.response(first, page=1, per_page=25, total_count=26),
                self.response([self.row(25)], page=2, per_page=25, total_count=26),
            ],
        ) as get:
            self.assertEqual(provider.deployments({}), first + [self.row(25)])
        self.assertEqual(len(get.call_args_list), 2)
        self.assertTrue(get.call_args_list[1].args[0].endswith("page=2"))

    def test_unknown_full_page_needs_the_following_empty_page(self):
        first = [self.row(i) for i in range(25)]
        with patch.object(
            provider, "get", side_effect=[self.response(first), self.response([])]
        ) as get:
            self.assertEqual(provider.deployments({}), first)
            self.assertEqual(get.call_count, 2)

    def test_incomplete_duplicate_changed_clamped_and_wrong_pages_refused(self):
        first = [self.row(i) for i in range(25)]
        for replies in [
            [self.response(first[:1], total_count=2)],
            [self.response([first[0], first[0]])],
            [self.response([], per_page=10)],
            [self.response([], page=2)],
            [
                self.response(first, total_count=26),
                self.response([self.row(25)], total_count=27),
            ],
            [self.response(first, total_count=26), self.response([], total_count=26)],
        ]:
            with (
                self.subTest(replies=replies),
                patch.object(provider, "get", side_effect=replies),
                self.assertRaises(owner.Rejected),
            ):
                provider.deployments({})

    def test_exact_known_limit_is_complete_and_unknown_overflow_is_refused(self):
        complete = [
            self.response(
                [self.row(25 * page + i) for i in range(25)],
                page=page + 1,
                per_page=25,
                total_count=1000,
            )
            for page in range(40)
        ]
        with patch.object(provider, "get", side_effect=complete):
            self.assertEqual(len(provider.deployments({})), 1000)
        overflow = [
            self.response(
                [self.row(25 * page + i) for i in range(25)], page=page + 1, per_page=25
            )
            for page in range(41)
        ]
        with (
            patch.object(provider, "get", side_effect=overflow),
            self.assertRaises(owner.Rejected),
        ):
            provider.deployments({})


if __name__ == "__main__":
    unittest.main()
