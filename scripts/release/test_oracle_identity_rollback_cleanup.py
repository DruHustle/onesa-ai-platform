"""Ambiguous Docker outcomes must not erase inputs or fabricate rollback proof."""

import copy
import json
import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import oracle_ai_runner as r
import oracle_identity_rollback as rollback


class DockerFixture:
    """A daemon inventory independent of whether its client receives a response."""

    postgres = "sha256:" + "9" * 64

    def __init__(self, folder, binding, plan, operation):
        self.folder, self.binding, self.plan, self.operation = (
            folder,
            binding,
            plan,
            operation,
        )
        self.rows = {}
        self.commands = []
        self.removed = []
        self.before_run = self.after_run = self.before_remove = None
        self.before_inventory = self.before_inspect = None
        self.manifest_changed = False
        self.next_id = 1

    @staticmethod
    def values(args, name):
        return [args[i + 1] for i, value in enumerate(args[:-1]) if value == name]

    def __call__(self, *args, **kwargs):
        self.commands.append((args, kwargs))
        if args[:2] == ("image", "inspect"):
            if args[2] == rollback.PG:
                row = {
                    "Id": self.postgres,
                    "Architecture": "arm64",
                    "Os": "linux",
                    "Config": {"Volumes": {"/var/lib/postgresql/data": {}}},
                }
            else:
                selected = next(
                    value
                    for value in [self.binding, self.plan["rollback"]["binding"]]
                    if value["artifact_digest"] == args[2]
                )
                row = {
                    "Id": selected["artifact_digest"],
                    "Architecture": "arm64",
                    "Os": "linux",
                    "Config": {
                        "Labels": {
                            "org.onesa.source-commit": selected["candidate_commit"]
                        }
                    },
                }
            return r.canonical([row])
        if args[:2] == ("container", "ls"):
            expression = self.values(args, "--filter")[0]
            if self.before_inventory:
                self.before_inventory(expression)
            if expression.startswith("id="):
                rows = [
                    row for row in self.rows.values() if row["Id"] == expression[3:]
                ]
            elif expression.startswith("name="):
                rows = [
                    row
                    for row in self.rows.values()
                    if re.fullmatch(expression[5:], row["Name"])
                ]
            else:
                key, value = expression.removeprefix("label=").split("=", 1)
                rows = [
                    row
                    for row in self.rows.values()
                    if row["Config"]["Labels"].get(key) == value
                ]
            return "".join(row["Id"] + "\n" for row in rows).encode()
        if args[0] == "run":
            cidfile = Path(self.values(args, "--cidfile")[0])
            self.assert_intent(cidfile)
            labels = dict(value.split("=", 1) for value in self.values(args, "--label"))
            role = labels["org.onesa.rollback-role"]
            if self.before_run:
                self.before_run(role, cidfile)
            cid = f"{self.next_id:064x}"
            self.next_id += 1
            entrypoint = args.index("--entrypoint")
            binds = self.values(args, "-v")
            tmpfs = dict(value.split(":", 1) for value in self.values(args, "--tmpfs"))
            row = {
                "Id": cid,
                "Name": "/" + self.values(args, "--name")[0],
                "Image": args[entrypoint + 2],
                "Config": {
                    "Labels": labels,
                    "User": self.values(args, "--user")[0],
                    "Entrypoint": [args[entrypoint + 1]],
                    "Cmd": list(args[entrypoint + 3 :]),
                    "Env": self.values(args, "-e"),
                },
                "HostConfig": {
                    "NetworkMode": self.values(args, "--network")[0],
                    "PortBindings": {},
                    "PublishAllPorts": False,
                    "AutoRemove": "--rm" in args,
                    "ReadonlyRootfs": "--read-only" in args,
                    "Privileged": False,
                    "CapAdd": [],
                    "CapDrop": self.values(args, "--cap-drop"),
                    "SecurityOpt": self.values(args, "--security-opt"),
                    "Memory": int(self.values(args, "--memory")[0][:-1]) * 1024**2,
                    "NanoCpus": int(self.values(args, "--cpus")[0]) * 1_000_000_000,
                    "PidsLimit": int(self.values(args, "--pids-limit")[0]),
                    "Tmpfs": tmpfs,
                    "Binds": binds,
                },
                "Mounts": [
                    {
                        "Type": "bind",
                        "Source": source,
                        "Destination": target,
                        "RW": mode == "rw",
                    }
                    for source, target, mode in [value.split(":") for value in binds]
                ]
                + [
                    {"Type": "tmpfs", "Destination": destination, "RW": True}
                    for destination in tmpfs
                ],
                "NetworkSettings": {"Networks": {"none": {}}},
                "State": {"Running": "-d" in args, "ExitCode": 0},
            }
            self.rows[cid] = row
            cidfile.write_text(cid + "\n")
            cidfile.chmod(0o600)
            if self.after_run:
                self.after_run(role, cidfile, row)
            if role == "schema":
                return b"BEGIN; SELECT 1; COMMIT;"
            if role == "database":
                return (cid + "\n").encode()
            request = json.loads(kwargs["data"])
            result = {
                "enabled_features": request["enabled_features"],
                "identity_enabled": False,
                "checks": {name: "PASS" for name in rollback.CHECKS},
            }
            if request["phase"] == "seed":
                result["fixture"] = {"owned": "synthetic-only"}
            return r.canonical(result)
        if args[0] == "inspect":
            if self.before_inspect:
                self.before_inspect(args[1])
            if args[1] not in self.rows:
                raise r.Refused("NO_SUCH_CONTAINER")
            return r.canonical([self.rows[args[1]]])
        if args[:2] == ("rm", "-f"):
            cid = args[2]
            if self.before_remove:
                self.before_remove(cid)
            self.removed.append(cid)
            del self.rows[cid]
            return (cid + "\n").encode()
        if args[0] == "exec":
            cid = args[2] if args[1] == "-i" else args[1]
            assert re.fullmatch(r"[a-f0-9]{64}", cid) and cid in self.rows
            assert (
                self.rows[cid]["Config"]["Labels"]["org.onesa.rollback-role"]
                == "database"
            )
            if "pg_dump" in args:
                return b"PGDMPsynthetic-bounded-dump"
            if "psql" in args:
                return (
                    b"f"
                    if self.manifest_changed and "onesa_identity_restored_test" in args
                    else b"e"
                ) * 64
            return b""
        raise AssertionError("Unexpected synthetic Docker command")

    def assert_intent(self, cidfile):
        intent = json.loads((self.folder / "identity-rollback-intent.json").read_text())
        specific = json.loads(cidfile.with_suffix(".intent.json").read_text())
        assert intent["operation_id"] == specific["operation_id"] == self.operation
        assert (
            intent["automatic_retry"] is False and specific["automatic_retry"] is False
        )
        assert any(row["name"] == specific["name"] for row in intent["containers"])


class RollbackCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.operation = str(uuid4())
        self.binding = {
            "artifact_digest": "sha256:" + "a" * 64,
            "candidate_commit": "b" * 40,
        }
        retained = {
            "artifact_digest": "sha256:" + "c" * 64,
            "candidate_commit": "d" * 40,
        }
        self.plan = {
            "rollback": {"binding": retained, "image": retained["artifact_digest"]}
        }
        self.daemon = DockerFixture(
            self.folder, self.binding, self.plan, self.operation
        )
        self.enterContext(patch.object(r, "docker", side_effect=self.daemon))
        self.enterContext(
            patch.object(r, "private", side_effect=lambda path, **kw: Path(path))
        )
        self.enterContext(patch.object(rollback.os, "chown"))
        self.enterContext(
            patch.object(
                rollback,
                "bound_environments",
                side_effect=lambda *args: {
                    "staging": {
                        "enabled_features": ["twins"],
                        "identity_enabled": False,
                    },
                    "production": {
                        "enabled_features": ["cybersecurity"],
                        "identity_enabled": False,
                    },
                },
            )
        )

    def check(self):
        return rollback.check(self.folder, self.binding, self.operation, self.plan)

    @property
    def socket(self):
        return self.folder / "identity-rollback-socket"

    def assert_no_pass(self, *, retained):
        self.assertFalse((self.folder / "identity-rollback-receipt.json").exists())
        self.assertEqual(self.socket.exists(), retained)
        observed = json.loads(
            (self.folder / "identity-rollback-cleanup.json").read_text()
        )
        self.assertEqual(observed["private_inputs_retained"], retained)
        self.assertEqual(observed["isolated_containers_removed"], not retained)

    def test_all_six_containers_are_bound_removed_and_absence_observed_before_pass(
        self,
    ):
        events = []
        fsync, write = os.fsync, r.write

        def synced(fd):
            events.append(
                "directory-fsync"
                if stat.S_ISDIR(os.fstat(fd).st_mode)
                else "file-fsync"
            )
            return fsync(fd)

        def written(path, value):
            if path.name == "identity-rollback-receipt.json":
                self.assertFalse(self.daemon.rows)
                self.assertFalse(self.socket.exists())
                self.assertTrue(
                    json.loads(
                        (self.folder / "identity-rollback-cleanup.json").read_text()
                    )["isolated_containers_removed"]
                )
            write(path, value)
            events.append(path.name)

        def before_run(role, cidfile):
            self.assertIn("identity-rollback-intent.json", events)
            self.assertEqual(events[-1], cidfile.with_suffix(".intent.json").name)
            self.assertEqual(events[-2], "directory-fsync")

        self.daemon.before_run = before_run
        with (
            patch.object(os, "fsync", side_effect=synced),
            patch.object(r, "write", side_effect=written),
        ):
            observed = self.check()
        self.assertEqual(observed["status"], "PASS")
        self.assertTrue(observed["isolated_containers_removed"])
        self.assertEqual(
            observed["cleanup_receipt_sha256"],
            r.sha(self.folder / "identity-rollback-cleanup.json"),
        )
        self.assertEqual(len(self.daemon.removed), 6)
        self.assertFalse(self.daemon.rows)
        self.assertFalse(self.socket.exists())
        for cid in self.daemon.removed:
            position = next(
                i
                for i, (args, _) in enumerate(self.daemon.commands)
                if args == ("rm", "-f", cid)
            )
            self.assertTrue(
                any(
                    args[:2] == ("container", "ls") and "id=" + cid in args
                    for args, _ in self.daemon.commands[position + 1 :]
                )
            )
        runs = [args for args, _ in self.daemon.commands if args[0] == "run"]
        self.assertTrue(
            all("--rm" not in args and "--cidfile" in args for args in runs)
        )
        self.assertEqual(events[-1], "identity-rollback-receipt.json")

    def test_timeout_after_created_database_or_application_is_inspected_and_cleaned_once(
        self,
    ):
        for role in ["schema", "database", "staging-seed", "production-verify"]:
            with self.subTest(role=role):
                folder = self.folder / role
                folder.mkdir()
                daemon = DockerFixture(folder, self.binding, self.plan, self.operation)

                def timeout(selected, cidfile, row, expected=role):
                    if selected == expected:
                        raise subprocess.TimeoutExpired("synthetic-docker", 1)

                daemon.after_run = timeout
                with (
                    patch.object(r, "docker", side_effect=daemon),
                    self.assertRaises(subprocess.TimeoutExpired),
                ):
                    rollback.check(folder, self.binding, self.operation, self.plan)
                self.assertFalse(daemon.rows)
                self.assertFalse((folder / "identity-rollback-socket").exists())
                self.assertFalse((folder / "identity-rollback-receipt.json").exists())
                self.assertEqual(len(daemon.removed), len(set(daemon.removed)))
                self.assertEqual(
                    sum(
                        args[0] == "run" and "org.onesa.rollback-role=" + role in args
                        for args, _ in daemon.commands
                    ),
                    1,
                )

    def test_timeout_without_cid_adopts_only_fully_inspected_exact_named_container(
        self,
    ):
        def timeout(role, cidfile, row):
            if role == "database":
                cidfile.unlink()
                raise subprocess.TimeoutExpired("synthetic-docker", 1)

        self.daemon.after_run = timeout
        with self.assertRaises(subprocess.TimeoutExpired):
            self.check()
        self.assertFalse(self.daemon.rows)
        self.assert_no_pass(retained=False)

    def test_absent_cid_and_empty_inventory_cannot_resolve_pending_create(self):
        def timeout(role, cidfile):
            if role == "database":
                raise subprocess.TimeoutExpired("synthetic-docker", 1)

        self.daemon.before_run = timeout
        with self.assertRaisesRegex(r.Refused, "CREATE_UNCONFIRMED"):
            self.check()
        self.assert_no_pass(retained=True)
        self.assertFalse(self.daemon.removed)
        before = len([args for args, _ in self.daemon.commands if args[0] == "run"])
        with self.assertRaisesRegex(r.Refused, "INSPECT_ONLY"):
            self.check()
        self.assertEqual(
            sum(args[0] == "run" for args, _ in self.daemon.commands), before
        )

    def test_cleanup_inspect_or_inventory_failure_retains_private_socket(self):
        for command in ["inspect", "inventory"]:
            with self.subTest(command=command):
                folder = self.folder / command
                folder.mkdir()
                daemon = DockerFixture(folder, self.binding, self.plan, self.operation)

                def arm(role, cidfile, row, target=daemon, selected=command):
                    if role == "production-verify":

                        def refused(*args):
                            raise r.Refused("DAEMON_UNAVAILABLE")

                        if selected == "inspect":
                            target.before_inspect = refused
                        else:
                            target.before_inventory = refused

                daemon.after_run = arm
                with (
                    patch.object(r, "docker", side_effect=daemon),
                    self.assertRaisesRegex(r.Refused, "DAEMON_UNAVAILABLE"),
                ):
                    rollback.check(folder, self.binding, self.operation, self.plan)
                self.assertTrue((folder / "identity-rollback-socket").exists())
                self.assertFalse((folder / "identity-rollback-receipt.json").exists())
                self.assertFalse(daemon.removed)

    def test_successful_remove_without_actual_absence_never_passes(self):
        original = self.daemon.__call__

        def dishonest(*args, **kwargs):
            if args[:2] == ("rm", "-f"):
                self.daemon.commands.append((args, kwargs))
                return b"synthetic-success-without-removal"
            return original(*args, **kwargs)

        with (
            patch.object(r, "docker", side_effect=dishonest),
            self.assertRaisesRegex(r.Refused, "REMOVAL_UNCONFIRMED"),
        ):
            self.check()
        self.assert_no_pass(retained=True)

    def test_remove_timeout_performs_absence_reads_but_never_retries_or_passes(self):
        attempted = []

        def timeout(cid):
            attempted.append(cid)
            del self.daemon.rows[cid]
            raise subprocess.TimeoutExpired("synthetic-docker", 1)

        self.daemon.before_remove = timeout
        with self.assertRaises(subprocess.TimeoutExpired):
            self.check()
        self.assertEqual(len(attempted), 6)
        self.assertEqual(len(set(attempted)), 6)
        self.assertFalse(self.daemon.rows)
        self.assert_no_pass(retained=True)

    def test_partial_socket_setup_preserves_truthful_cleanup_receipt(self):
        with (
            patch.object(
                rollback.os,
                "chown",
                side_effect=OSError("synthetic permission failure"),
            ),
            self.assertRaises(OSError),
        ):
            self.check()
        self.assert_no_pass(retained=False)
        self.assertFalse(any(args[0] == "run" for args, _ in self.daemon.commands))

    def test_expected_postgres_entrypoint_socket_permissions_remain_owned(self):
        def configured(role, cidfile, row):
            if role == "database":
                self.socket.chmod(0o3775)

        self.daemon.after_run = configured
        self.assertEqual(self.check()["status"], "PASS")
        self.assertFalse(self.socket.exists())

    def test_other_socket_permission_change_preserves_inputs_and_refuses_pass(self):
        def changed(role, cidfile, row):
            if role == "database":
                self.socket.chmod(0o777)

        self.daemon.after_run = changed
        with self.assertRaisesRegex(r.Refused, "SOCKET_CHANGED"):
            self.check()
        self.assert_no_pass(retained=True)

    def test_socket_stat_failure_cannot_claim_inputs_were_removed(self):
        original = Path.stat
        failed = False

        def unavailable(path, *args, **kwargs):
            nonlocal failed
            if path == self.socket and os.path.isdir(path) and not failed:
                failed = True
                raise OSError("synthetic socket stat failure")
            return original(path, *args, **kwargs)

        with (
            patch.object(Path, "stat", unavailable),
            self.assertRaisesRegex(r.Refused, "SOCKET_REMOVAL_UNCONFIRMED"),
        ):
            self.check()
        self.assert_no_pass(retained=True)
        self.assertFalse(any(args[0] == "run" for args, _ in self.daemon.commands))

    def test_socket_remove_return_without_absence_cannot_claim_success(self):
        with (
            patch.object(rollback.shutil, "rmtree"),
            self.assertRaisesRegex(r.Refused, "SOCKET_REMOVAL_UNCONFIRMED"),
        ):
            self.check()
        self.assertFalse(self.daemon.rows)
        self.assert_no_pass(retained=True)

    def test_failed_post_remove_inventory_is_not_absence(self):
        def arm(cid):
            def unavailable(expression):
                if expression == "id=" + cid:
                    raise r.Refused("FINAL_DAEMON_READ_FAILED")

            self.daemon.before_inventory = unavailable

        self.daemon.before_remove = arm
        with self.assertRaisesRegex(r.Refused, "FINAL_DAEMON_READ_FAILED"):
            self.check()
        self.assertEqual(len(self.daemon.removed), 1)
        self.assert_no_pass(retained=True)

    def test_changed_or_malformed_cid_never_removes_a_replacement(self):
        for changed in ["malformed", "foreign", "replaced-file"]:
            with self.subTest(changed=changed):
                folder = self.folder / changed
                folder.mkdir()
                daemon = DockerFixture(folder, self.binding, self.plan, self.operation)

                def alter(role, cidfile, row, mode=changed, target=folder):
                    if role == "staging-seed":
                        database_cid = target / "identity-rollback-database.cid"
                        if mode == "replaced-file":
                            value = database_cid.read_text()
                            replacement = target / "untrusted-replacement.cid"
                            replacement.write_text(value)
                            replacement.chmod(0o600)
                            replacement.replace(database_cid)
                        else:
                            database_cid.write_text(
                                "not-a-cid" if mode == "malformed" else "f" * 64
                            )

                daemon.after_run = alter
                with (
                    patch.object(r, "docker", side_effect=daemon),
                    self.assertRaisesRegex(r.Refused, "CID_"),
                ):
                    rollback.check(folder, self.binding, self.operation, self.plan)
                self.assertFalse(daemon.removed)
                self.assertTrue((folder / "identity-rollback-socket").exists())
                self.assertFalse((folder / "identity-rollback-receipt.json").exists())

    def test_unknown_operation_container_is_never_removed(self):
        def extra(role, cidfile, row):
            if role == "production-verify":
                foreign = copy.deepcopy(row)
                foreign["Id"] = "f" * 64
                foreign["Name"] = "/unrelated-container"
                self.daemon.rows[foreign["Id"]] = foreign

        self.daemon.after_run = extra
        with self.assertRaisesRegex(r.Refused, "INVENTORY_CHANGED"):
            self.check()
        self.assertFalse(self.daemon.removed)
        self.assert_no_pass(retained=True)

    def test_changed_owned_boundary_never_authorizes_cleanup(self):
        changes = {
            "image": lambda row: row.update(Image="sha256:" + "f" * 64),
            "name": lambda row: row.update(Name="/replacement"),
            "operation": lambda row: row["Config"]["Labels"].update(
                {rollback.LABEL: str(uuid4())}
            ),
            "role": lambda row: row["Config"]["Labels"].update(
                {"org.onesa.rollback-role": "foreign"}
            ),
            "network": lambda row: row["HostConfig"].update(NetworkMode="host"),
            "extra-network": lambda row: row["NetworkSettings"]["Networks"].update(
                bridge={}
            ),
            "bind-source": lambda row: row["Mounts"][0].update(Source="/foreign"),
            "bind-mode": lambda row: row["Mounts"][0].update(RW=True),
            "extra-volume": lambda row: row["Mounts"].append(
                {"Type": "volume", "Destination": "/other", "RW": True}
            ),
            "extra-tmpfs": lambda row: row["HostConfig"]["Tmpfs"].update(
                {"/other": "rw"}
            ),
            "privileged": lambda row: row["HostConfig"].update(Privileged=True),
            "command": lambda row: row["Config"].update(Cmd=["foreign"]),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                folder = self.folder / name
                folder.mkdir()
                daemon = DockerFixture(folder, self.binding, self.plan, self.operation)

                def alter(role, cidfile, row, mutate=change):
                    if role == "staging-seed":
                        mutate(row)

                daemon.after_run = alter
                with (
                    patch.object(r, "docker", side_effect=daemon),
                    self.assertRaises(r.Refused),
                ):
                    rollback.check(folder, self.binding, self.operation, self.plan)
                self.assertFalse(daemon.removed)
                self.assertTrue((folder / "identity-rollback-socket").exists())
                self.assertFalse((folder / "identity-rollback-receipt.json").exists())


if __name__ == "__main__":
    unittest.main()
