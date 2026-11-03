"""Synthetic credential/session boundaries; no hosted acceptance is claimed.

Session mutation tests use only the four relevant ORM tables in private in-memory
SQLite. PostgreSQL row hashing and the real hosted scenarios remain native gates.
"""

import hashlib
import http.cookiejar
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import fixtures
import oracle_ai_identity_probe as i
import oracle_ai_probe as probe
import test_oracle_ai_identity_release as release


class IdentityCustodyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "identity.json"
        self.binding, self.plan, self.runtime, self.held = release.fixture()
        self.environment = "production"
        self.origin = "https://platform.onesa.eu"
        self.plan["identity"]["credentials_sha256"] = (
            release.r.identity_credentials_digest(self.held)
        )
        self.held["source_custody_sha256"] = self.plan["identity"]["credentials_sha256"]
        self.held["environments"] = {
            self.environment: self.held["environments"][self.environment]
        }
        self.request = {"operation_id": str(uuid4()), "identity_custody_sha256": ""}
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.held))
        self.path.chmod(0o600)
        self.request["identity_custody_sha256"] = hashlib.sha256(
            self.path.read_bytes()
        ).hexdigest()

    def load(self):
        return i.load_identity(
            self.plan,
            self.binding,
            self.request,
            self.environment,
            self.origin,
            self.runtime[self.environment],
            path=self.path,
        )

    def test_exact_single_environment_source_custody_and_separate_password_proof(self):
        value = self.load()
        i.validate_identity(value)
        self.assertEqual(value["candidate_commit"], self.binding["candidate_commit"])
        self.assertNotEqual(
            value["accounts"]["primary"]["password"],
            value["accounts"]["primary"]["local_password"],
        )
        self.assertEqual(set(value["accounts"]), {"primary", "foreign"})

    def test_foreign_environment_original_hash_or_source_never_reaches_login(self):
        original = deepcopy(self.held)
        for mutate, reason in [
            (
                lambda v: v["environments"].update(
                    staging=deepcopy(v["environments"]["production"])
                ),
                "MUST_BE_NARROWED",
            ),
            (lambda v: v.update(source_custody_sha256="0" * 64), "MUST_BE_NARROWED"),
            (lambda v: v.update(candidate_commit="e" * 40), "MUST_BE_NARROWED"),
            (
                lambda v: v["environments"]["production"]["accounts"]["primary"].update(
                    local_user_id=str(uuid4())
                ),
                "ACCOUNT_BINDING",
            ),
            (
                lambda v: v["environments"]["production"]["accounts"]["primary"].pop(
                    "local_password"
                ),
                "ACCOUNT_BINDING",
            ),
            (lambda v: v.update(expires_at=v["created_at"]), "CREDENTIAL_EXPIRED"),
        ]:
            self.held = deepcopy(original)
            mutate(self.held)
            self.save()
            with (
                self.subTest(reason=reason),
                self.assertRaisesRegex(ValueError, reason),
            ):
                self.load()

    def test_changed_bytes_aliases_permissions_and_duplicate_json_are_refused(self):
        self.path.write_text(self.path.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "CUSTODY_CHANGED"):
            self.load()
        self.save()
        self.path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "PRIVATE_CUSTODY"):
            self.load()
        self.save()
        alias = self.path.with_name("hardlink")
        os.link(self.path, alias)
        with self.assertRaisesRegex(ValueError, "PRIVATE_CUSTODY"):
            self.load()
        alias.unlink()
        raw = self.path.read_text().replace(
            '"schema_version": 1', '"schema_version": 1, "schema_version": 1'
        )
        self.path.write_text(raw)
        self.request["identity_custody_sha256"] = hashlib.sha256(
            self.path.read_bytes()
        ).hexdigest()
        with self.assertRaisesRegex(ValueError, "DUPLICATE_FIELD"):
            self.load()

    def test_shared_fixture_parser_keeps_legacy_scope_strict_and_binds_exact_native_users(
        self,
    ):
        identity = self.load()
        config = {
            "scope": "approved-synthetic-production",
            "project_id": "prj_fixture",
            "candidate_commit": self.binding["candidate_commit"],
            "users": i.fixture_users(identity),
        }
        with self.assertRaises(fixtures.FixtureError):
            fixtures.parse_fixtures(
                json.dumps(config),
                "prj_fixture",
                "onesa-ai-platform",
                scope="approved-synthetic-production",
            )
        self.assertEqual(
            fixtures.parse_fixtures(
                json.dumps(config),
                "prj_fixture",
                "onesa-ai-platform",
                scope="approved-synthetic-production",
                identity=identity,
            ),
            config,
        )
        config["users"][1]["id"] = config["users"][0]["id"]
        with self.assertRaises(fixtures.FixtureError):
            fixtures.parse_fixtures(
                json.dumps(config),
                "prj_fixture",
                "onesa-ai-platform",
                scope="approved-synthetic-production",
                identity=identity,
            )

    def capsule(self):
        identity = self.load()
        actor = identity["accounts"]["primary"]
        cookie = {
            "domain": "platform.onesa.eu",
            "path": "/",
            "expires": datetime.now(timezone.utc).timestamp() + 300,
            "secure": True,
            "sameSite": "Lax",
        }
        return identity, {
            "schema_version": 1,
            "origin": identity["origin"],
            "issuer": identity["issuer"],
            "subject": actor["subject"],
            "local_user_id": actor["local_user_id"],
            "csrf": "c" * 43,
            "cookies": [
                {
                    **cookie,
                    "name": "onesa_session",
                    "value": "s" * 43,
                    "httpOnly": True,
                },
                {**cookie, "name": "onesa_csrf", "value": "c" * 43, "httpOnly": False},
            ],
        }

    def test_cookie_cannot_change_host_local_owner_csrf_or_scope(self):
        identity, capsule = self.capsule()
        i.validate_session(capsule, identity, "primary")
        for change in [
            lambda v: v["cookies"][0].update(domain=".onesa.eu"),
            lambda v: v["cookies"][0].update(secure=False),
            lambda v: v["cookies"][1].update(value="x" * 43),
            lambda v: v.update(
                local_user_id=identity["accounts"]["foreign"]["local_user_id"]
            ),
            lambda v: v["cookies"][0].update(httpOnly=False),
        ]:
            value = deepcopy(capsule)
            change(value)
            with self.assertRaises(ValueError):
                i.validate_session(value, identity, "primary")

    def test_session_transfer_revalidates_live_product_identity_without_exposing_pipe_output(
        self,
    ):
        identity, capsule = self.capsule()
        user = i.fixture_users(identity)[0]

        class Client:
            origin = identity["origin"]
            cookies = http.cookiejar.CookieJar()

            def call(self, method, path):
                self.observed = (method, path)
                return {
                    "id": user["id"],
                    "email": user["email"],
                    "identity_mode": "onesa",
                    "global_admin": False,
                    "administrator": False,
                }

        client = Client()
        result = subprocess.CompletedProcess([], 0, json.dumps(capsule).encode(), b"")
        with patch.object(i.subprocess, "run", return_value=result) as run:
            i.login(client, user, identity, None)
        self.assertTrue(run.call_args.kwargs["capture_output"])
        self.assertEqual(client.observed, ("GET", "/api/v1/auth/me"))
        self.assertTrue(
            all(
                not cookie.domain_specified and cookie.secure
                for cookie in client.cookies
            )
        )
        self.assertEqual(client.csrf, capsule["csrf"])
        client.origin = "https://foreign.example.test"
        with self.assertRaisesRegex(ValueError, "ORIGIN_MUST_NOT_BE_REWRITTEN"):
            i.login(client, user, identity, None)

    def test_old_owned_rows_must_survive_including_duplicate_rows(self):
        before = {
            "users": ["user"],
            "auth_sessions": ["old"],
            "records": ["same", "same"],
        }
        after = {
            "users": ["user"],
            "auth_sessions": ["old", "new-retired"],
            "records": ["same", "same", "new"],
        }
        self.assertTrue(i.preserved_owned(before, after))
        for name in before:
            changed = deepcopy(after)
            changed[name].pop(0)
            self.assertFalse(i.preserved_owned(before, changed))


class IdentitySessionCleanupTests(unittest.TestCase):
    # These are targeted ORM semantics, never a substitute for PostgreSQL/hosted tests.
    def setUp(self):
        IdentityCustodyTests.setUp(self)
        sys.path.insert(0, str(i.ROOT / "onesa-ai-platform-backend"))
        from app.models import AuthSession, IdentitySession, SharedIdentity, User
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        self.models = User, AuthSession, IdentitySession, SharedIdentity
        self.Session = Session
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        for model in self.models:
            model.__table__.create(self.engine)
        self.identity = self.load()
        self.identity["session_journal"] = str(self.path.with_name("sessions.jsonl"))
        Path(self.identity["session_journal"]).write_text("")
        Path(self.identity["session_journal"]).chmod(0o600)
        with Session(self.engine) as db:
            for account in self.identity["accounts"].values():
                db.add(
                    User(
                        id=UUID(account["local_user_id"]),
                        email=account["email"],
                        display_name="Existing synthetic user",
                        password_hash="unchanged-existing-password-hash",
                        status="active",
                    )
                )
            db.commit()
        self.old = self.add_session("old", journal=False)
        self.before = i.session_baseline(self.engine, i.fixture_users(self.identity))

    save = IdentityCustodyTests.save
    load = IdentityCustodyTests.load

    def add_session(self, label, *, journal=True, actor="primary"):
        _, AuthSession, IdentitySession, _ = self.models
        account = self.identity["accounts"][actor]
        identifier = uuid4()
        token, csrf = (
            hashlib.sha256((label + part).encode()).hexdigest()
            for part in ["token", "csrf"]
        )
        with self.Session(self.engine) as db:
            db.add(
                AuthSession(
                    id=identifier,
                    user_id=UUID(account["local_user_id"]),
                    token_hash=token,
                    csrf_hash=csrf,
                    expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
                )
            )
            db.add(
                IdentitySession(
                    session_id=identifier,
                    issuer=self.identity["issuer"],
                    subject=account["subject"],
                    encrypted_token="synthetic-test-ciphertext",
                )
            )
            db.commit()
        if journal:
            self.append_journal(token, csrf)
        return identifier

    def append_journal(self, token, csrf):
        with Path(self.identity["session_journal"]).open("a") as stream:
            stream.write(
                json.dumps(
                    {
                        "operation_id": self.identity["operation_id"],
                        "token_sha256": token,
                        "csrf_sha256": csrf,
                    }
                )
                + "\n"
            )

    def test_only_observed_new_sessions_retire_without_disabling_existing_users_or_sessions(
        self,
    ):
        new = self.add_session("new")
        self.assertTrue(i.retire_sessions(self.engine, self.identity, self.before))
        User, AuthSession, _, _ = self.models
        with self.Session(self.engine) as db:
            self.assertIsNone(db.get(AuthSession, self.old).revoked_at)
            self.assertIsNotNone(db.get(AuthSession, new).revoked_at)
            user = db.get(
                User, UUID(self.identity["accounts"]["primary"]["local_user_id"])
            )
            self.assertEqual(
                (user.status, user.password_hash),
                ("active", "unchanged-existing-password-hash"),
            )

    def test_unobserved_concurrent_session_is_preserved_and_blocks_qualification(self):
        observed, unrelated = (
            self.add_session("observed"),
            self.add_session("unobserved", journal=False),
        )
        with self.assertRaisesRegex(ValueError, "UNOBSERVED_SESSION_UNCERTAINTY"):
            i.retire_sessions(self.engine, self.identity, self.before)
        _, AuthSession, _, _ = self.models
        with self.Session(self.engine) as db:
            self.assertIsNotNone(db.get(AuthSession, observed).revoked_at)
            self.assertIsNone(db.get(AuthSession, unrelated).revoked_at)
            self.assertIsNone(db.get(AuthSession, self.old).revoked_at)

    def test_copied_preexisting_token_cannot_authorize_revocation(self):
        _, AuthSession, _, _ = self.models
        with self.Session(self.engine) as db:
            old = db.get(AuthSession, self.old)
            self.append_journal(old.token_hash, old.csrf_hash)
        with self.assertRaisesRegex(ValueError, "CANNOT_TOUCH_EXISTING"):
            i.retire_sessions(self.engine, self.identity, self.before)
        with self.Session(self.engine) as db:
            self.assertIsNone(db.get(AuthSession, self.old).revoked_at)

    def test_unmatched_csrf_or_subject_cannot_retire_a_session(self):
        new = self.add_session("new")
        _, AuthSession, IdentitySession, _ = self.models
        with self.Session(self.engine) as db:
            db.get(IdentitySession, new).subject = self.identity["accounts"]["foreign"][
                "subject"
            ]
            db.commit()
        with self.assertRaisesRegex(ValueError, "SESSION_MAPPING"):
            i.retire_sessions(self.engine, self.identity, self.before)
        with self.Session(self.engine) as db:
            self.assertIsNone(db.get(AuthSession, new).revoked_at)

    def test_linking_precondition_does_not_create_or_change_users_and_requires_exact_final_mapping(
        self,
    ):
        i.local_accounts(self.engine, self.identity)
        with self.assertRaisesRegex(ValueError, "LOCAL_IDENTITY_MAPPING"):
            i.local_accounts(self.engine, self.identity, linked=True)
        _, _, _, SharedIdentity = self.models
        with self.Session(self.engine) as db:
            for account in self.identity["accounts"].values():
                db.add(
                    SharedIdentity(
                        issuer=self.identity["issuer"],
                        subject=account["subject"],
                        user_id=UUID(account["local_user_id"]),
                    )
                )
            db.commit()
        i.local_accounts(self.engine, self.identity, linked=True)


class IdentityProbeIntegrationTests(unittest.TestCase):
    # Reuse the private fixture while keeping the ordinary workflow producer live.
    setUp = IdentityCustodyTests.setUp
    save = IdentityCustodyTests.save
    load = IdentityCustodyTests.load

    def run_foundation(self, *, cleanup_failure=False):
        identity = self.load()
        output = self.path.parent
        identity["session_journal"] = str(output / "sessions.jsonl")
        plan = {**self.plan, "expected_schema_revision": "20261102_shared_identity"}
        plan_path = output / "plan.json"
        plan_path.write_text(json.dumps(plan))
        request = {
            **self.request,
            "binding": self.binding,
            "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
            "ci_run_id": 123,
        }
        calls = []

        class Session:
            def __init__(self, origin):
                self.origin = origin
                self.cookies = http.cookiejar.CookieJar()
                self.opener = types.SimpleNamespace(addheaders=[])

            def login(self, _user):
                raise AssertionError("Legacy password login must remain disabled")

            def call(self, method, path, _body=None, *, expected=200):
                calls.append((method, path, expected))
                return (
                    {"enabled": True}
                    if path.endswith("/onesa/config")
                    else {"id": "owned-conversation"}
                )

        hosted = types.SimpleNamespace(Session=Session)
        config = {
            "project_id": "prj_fixture",
            "backend_identity": {},
            "retained_frontend": {
                "served_static_artifact_verified": True,
                "authority_transferred": False,
                "new_frontend_deployment_requests": 0,
                "deployment_id": "dpl_fixture",
                "binding": {"candidate_commit": "f" * 40},
            },
        }

        def read(path):
            return plan if str(path) == "/private/plan.json" else config

        with (
            patch.object(probe, "OUTPUT", output),
            patch.object(
                probe,
                "Path",
                side_effect=lambda path: (
                    plan_path if path == "/private/plan.json" else Path(path)
                ),
            ),
            patch.object(probe, "private_json", side_effect=read),
            patch.object(
                probe, "runtime", return_value={"ONESA_PUBLIC_ORIGIN": self.origin}
            ),
            patch.object(
                probe,
                "provider",
                return_value=(
                    self.origin,
                    None,
                    {"deployment_id": "dpl_fixture", "source": "f" * 40},
                ),
            ),
            patch.object(probe, "served_backend_identity", return_value={}),
            patch.object(
                probe,
                "fixture_engine",
                return_value=types.SimpleNamespace(dispose=lambda: None),
            ),
            patch.object(probe, "fingerprints", return_value={"existing": "unchanged"}),
            patch.object(probe, "create_fixtures") as create,
            patch.object(probe, "disable_fixtures") as disable,
            patch.object(
                probe, "ordinary_production", return_value={"native_workflows": "PASS"}
            ) as ordinary,
            patch.object(i, "load_identity", return_value=identity),
            patch.object(i, "local_accounts"),
            patch.object(
                i,
                "owned_fingerprints",
                return_value={"users": ["unchanged"], "auth_sessions": []},
            ),
            patch.object(i, "session_baseline", return_value=set()),
            patch.object(
                i,
                "retire_sessions",
                return_value=True,
                side_effect=ValueError("uncertain callback session")
                if cleanup_failure
                else None,
            ) as retire,
            patch.object(i, "login", return_value={"identity_mode": "onesa"}) as login,
            patch.dict(
                sys.modules, {"hosted": types.SimpleNamespace(), "hosted_suite": hosted}
            ),
            patch.dict(os.environ, {}, clear=True),
        ):
            if cleanup_failure:
                with self.assertRaisesRegex(ValueError, "uncertain callback session"):
                    probe.execute("production", request)
                result = json.loads((output / "receipt.json").read_bytes())
            else:
                result = probe.execute("production", request)
        create.assert_not_called()
        disable.assert_not_called()
        ordinary.assert_called_once()
        retire.assert_called_once()
        self.assertEqual(login.call_count, 2)
        if cleanup_failure:
            self.assertEqual(result["status"], "FAIL")
            self.assertFalse(result["fixture_identities_disabled"])
            self.assertFalse(result["identity_sessions_retired"])
            self.assertFalse(result["fixture_identities_preserved"])
            self.assertFalse(result["existing_records_preserved"])
            self.assertTrue((output / "private-fixtures.json").is_file())
            self.assertIs(hosted.Session, Session)
            return
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["fixture_identities_disabled"])
        self.assertTrue(result["fixture_identities_preserved"])
        self.assertTrue(result["identity_sessions_retired"])
        for check in [
            "owner_isolation",
            "database_persistence",
            "session_persistence",
            "twins_disabled",
            "cybersecurity_disabled",
            "shared_identity_pkce",
            "shared_identity_mfa",
            "identity_cookie_isolation",
            "identity_local_mapping",
            "identity_fixture_preservation",
            "identity_sessions_retired",
        ]:
            self.assertEqual(result["checks"][check], "PASS")
        self.assertIn(("POST", "/api/v1/auth/login", 403), calls)
        self.assertEqual(
            [path for _method, path, status in calls if status == 404],
            [
                "/api/v1/twins/readiness",
                "/api/v1/twins/catalog",
                "/api/v1/cybersecurity/readiness",
                "/api/v1/cybersecurity/workspace",
                "/api/v1/conversations/owned-conversation",
            ],
        )

    def test_identity_profile_runs_native_foundation_checks_and_emits_preservation_cleanup(
        self,
    ):
        self.run_foundation()

    def test_uncertain_identity_cleanup_cannot_pass_or_remove_private_inputs(self):
        self.run_foundation(cleanup_failure=True)


if __name__ == "__main__":
    unittest.main()
