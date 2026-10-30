"""Synthetic Docker observations: an active probe cannot wait for its own exit."""

import copy
import json
import os
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import oracle_ai_probe as producer
import oracle_ai_runner as r
import test_oracle_inventory as fixtures


class OwnedProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.control = self.root / "control"
        self.control.mkdir(mode=0o700)
        self.operation = "49795958-a596-410b-a921-9d7947d7314a"
        self.cid = "a" * 64
        self.image = "sha256:" + "b" * 64
        self.mounts = [(self.root / "output", "/private/output", True)]
        self.private = patch.object(r, "private", side_effect=self.local_private)
        self.private.start()
        self.addCleanup(self.private.stop)
        self.owned = r.OwnedProbeSnapshot(
            self.control,
            self.operation,
            self.image,
            "staging",
            self.mounts,
            "bridge",
            "0.5",
        )
        self.owned.cidfile.write_text(self.cid)
        self.owned.cidfile.chmod(0o600)
        self.clock = 0
        self.rows = {
            name: fixtures.RuntimeInventoryTests.row(name) for name in r.TARGET.values()
        }
        self.rows["independent-workload"] = fixtures.RuntimeInventoryTests.row(
            "independent-workload"
        )
        self.client = {
            "Name": "/" + self.owned.name,
            "Id": self.cid,
            "Image": self.image,
            "State": {"Running": True},
            "Config": {
                "Entrypoint": ["python3"],
                "Cmd": [
                    "/opt/onesa-ai-platform/scripts/release/oracle_ai_probe.py",
                    "staging",
                    "--stdin-request",
                ],
                "Labels": {"org.onesa.probe-operation": self.operation},
            },
            "HostConfig": {
                "AutoRemove": True,
                "Init": True,
                "ReadonlyRootfs": True,
                "Privileged": False,
                "CapAdd": None,
                "CapDrop": ["ALL"],
                "SecurityOpt": ["no-new-privileges:true"],
                "NetworkMode": "bridge",
                "Memory": 2 * 1024**3,
                "NanoCpus": 500_000_000,
                "PortBindings": {},
                "PublishAllPorts": False,
                "Tmpfs": {"/tmp": "rw,mode=700,size=512m"},
            },
            "Mounts": [
                {
                    "Type": "bind",
                    "Source": str(self.mounts[0][0]),
                    "Destination": "/private/output",
                    "RW": True,
                }
            ],
        }
        self.rows[self.owned.name] = self.client

    def local_private(self, path, directory=False):
        # Only replace root UID/ancestor requirements for these disposable files.
        path = Path(path)
        state = path.lstat()
        r.require(
            not path.is_symlink() and state.st_mode & 0o077 == 0,
            "PRIVATE_CUSTODY_REQUIRED",
        )
        r.require(path.is_dir() if directory else path.is_file(), "PRIVATE_TYPE")
        return path

    def inventory(self, owned=True):
        def docker(*args, **_kwargs):
            if args[0] == "ps":
                return "\n".join(self.rows).encode()
            self.assertEqual(args[0], "inspect")
            return json.dumps(list(self.rows.values())).encode()

        def sleep(seconds):
            self.clock += seconds

        with (
            patch.object(r, "docker", side_effect=docker),
            patch.object(r.time, "monotonic", side_effect=lambda: self.clock),
            patch.object(r.time, "sleep", side_effect=sleep),
        ):
            return r.inventory(owned_probe=self.owned) if owned else r.inventory()

    def test_old_inventory_deadlock_reproduced(self):
        with self.assertRaisesRegex(r.Refused, "INVENTORY_NOT_QUIESCENT"):
            self.inventory(owned=False)

    def test_owned_probe_allows_replacement_without_hiding_persistent_workloads(self):
        before = self.inventory()
        self.assertNotIn(self.owned.name, before)
        self.assertIn("independent-workload", before)
        self.rows[r.TARGET["staging"]]["Id"] = "new-service"
        after = self.inventory()
        r.unchanged(before, after, [r.TARGET["staging"]])
        with self.assertRaises(r.Refused):
            r.unchanged(before, after)
        del after["independent-workload"]
        with self.assertRaises(r.Refused):
            r.unchanged(before, after, [r.TARGET["staging"]])

    def test_another_auto_remove_client_still_blocks(self):
        self.rows["unknown-client"] = fixtures.RuntimeInventoryTests.row(
            "unknown-client", True
        )
        with self.assertRaisesRegex(r.Refused, "INVENTORY_NOT_QUIESCENT"):
            self.inventory()

    def test_wrong_identity_command_mount_resources_and_lifecycle_fail_closed(self):
        cases = [
            ("Id", "forged"),
            ("Image", "sha256:wrong"),
            ("Name", "/wrong"),
            ("State", {"Running": False}),
            (
                "Mounts",
                self.client["Mounts"] + [{"Type": "volume", "Destination": "/extra"}],
            ),
        ]
        for key, value in cases:
            changed = copy.deepcopy(self.client)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(r.Refused):
                self.owned.validate({self.owned.name: changed})
        for field, value in [
            ("Init", False),
            ("AutoRemove", False),
            ("Memory", 0),
            ("NanoCpus", 1),
            ("Privileged", True),
            ("NetworkMode", "host"),
            ("ReadonlyRootfs", False),
            ("CapAdd", ["SYS_ADMIN"]),
            ("CapDrop", []),
            ("SecurityOpt", []),
            ("PortBindings", {"80/tcp": [{}]}),
            ("PublishAllPorts", True),
            ("Tmpfs", {}),
        ]:
            changed = copy.deepcopy(self.client)
            changed["HostConfig"][field] = value
            with self.subTest(field=field), self.assertRaises(r.Refused):
                self.owned.validate({self.owned.name: changed})
        for field, value in [
            ("Entrypoint", ["sh"]),
            ("Cmd", ["wrong"]),
            ("Labels", {"org.onesa.probe-operation": "wrong"}),
        ]:
            changed = copy.deepcopy(self.client)
            changed["Config"][field] = value
            with self.subTest(field=field), self.assertRaises(r.Refused):
                self.owned.validate({self.owned.name: changed})
        changed = copy.deepcopy(self.client)
        changed["Mounts"][0]["RW"] = False
        with self.assertRaises(r.Refused):
            self.owned.validate({self.owned.name: changed})

    def test_missing_client_or_caller_json_is_not_an_exemption(self):
        del self.rows[self.owned.name]
        with self.assertRaisesRegex(r.Refused, "OWNED_PROBE_NOT_RUNNING"):
            self.inventory()
        with self.assertRaises(r.Refused):
            r.inventory(owned_probe={"name": self.owned.name})

    def test_cid_changes_symlinks_hardlinks_and_insecure_mode_are_rejected(self):
        self.owned.cid()
        self.owned.cidfile.write_text("c" * 64)
        with self.assertRaisesRegex(r.Refused, "CID_CHANGED"):
            self.owned.cid()
        self.owned.cidfile.unlink()
        original = self.root / "original"
        original.write_text(self.cid)
        original.chmod(0o600)
        self.owned.cidfile.symlink_to(original)
        with self.assertRaises(r.Refused):
            self.owned.cid()
        self.owned.cidfile.unlink()
        os.link(original, self.owned.cidfile)
        with self.assertRaisesRegex(r.Refused, "CID_FILE"):
            self.owned.cid()
        self.owned.cidfile.unlink()
        self.owned.cidfile.write_text(self.cid)
        self.owned.cidfile.chmod(0o644)
        with self.assertRaises(r.Refused):
            self.owned.cid()

    def test_control_directory_cannot_be_exposed_to_producer(self):
        for path in [self.root, self.control]:
            with (
                self.subTest(path=path),
                self.assertRaisesRegex(r.Refused, "MUST_NOT_BE_MOUNTED"),
            ):
                r.OwnedProbeSnapshot(
                    self.control,
                    self.operation,
                    self.image,
                    "staging",
                    [(path, "/private/output", True)],
                    "bridge",
                    "0.5",
                )

    def cleanup(self, wrong=False, stop_error=False):
        process = Mock()
        process.poll.return_value = None
        exists = True
        calls = []

        def docker(*args, **_kwargs):
            nonlocal exists
            calls.append(args)
            if args[0] == "ps":
                return self.cid.encode() if exists else b""
            if args[0] == "inspect":
                row = copy.deepcopy(self.client)
                if wrong:
                    row["Image"] = "sha256:forged"
                return json.dumps([row]).encode()
            self.assertEqual(args, ("stop", "--time", "60", self.cid))
            if stop_error:
                raise subprocess.TimeoutExpired("docker", 75)
            exists = False
            return self.cid.encode()

        with patch.object(r, "docker", side_effect=docker):
            safe = r.finish_probe_client(process, self.owned, self.root)
        return safe, calls, process

    def test_interruption_stops_only_verified_client_once(self):
        safe, calls, process = self.cleanup()
        self.assertTrue(safe)
        self.assertEqual(sum(x[0] == "stop" for x in calls), 1)
        process.terminate.assert_called_once()
        self.assertTrue(
            json.loads((self.root / "client-cleanup.json").read_text())[
                "client_exit_confirmed"
            ]
        )

    def test_wrong_identity_is_never_stopped_and_private_inputs_are_retained(self):
        safe, calls, _process = self.cleanup(wrong=True)
        self.assertFalse(safe)
        self.assertFalse(any(x[0] == "stop" for x in calls))
        self.assertTrue(
            json.loads((self.root / "client-cleanup.json").read_text())[
                "private_inputs_retained"
            ]
        )

    def test_stop_timeout_does_not_retry_or_replace_original_failure(self):
        with self.assertRaisesRegex(r.Refused, "ORIGINAL"):
            try:
                raise r.Refused("ORIGINAL")
            finally:
                safe, calls, _process = self.cleanup(stop_error=True)
                self.assertFalse(safe)
                self.assertEqual(sum(x[0] == "stop" for x in calls), 1)

    def test_exited_client_without_exact_fixture_cleanup_retains_private_inputs(self):
        binding = {"candidate_commit": "b" * 40, "component": "api"}
        for name in ["private-runtime.env", "private-provider-observation.json"]:
            path = self.root / name
            path.write_text("synthetic")
            path.chmod(0o600)
        receipt = {
            "binding": binding,
            "operation_id": self.operation,
            "environment": "staging",
            "fixture_identities_disabled": False,
            "existing_records_preserved": True,
        }
        path = self.root / "receipt.json"
        path.write_text(json.dumps(receipt))
        path.chmod(0o600)
        self.assertFalse(
            r.cleanup_probe_inputs(self.root, binding, self.operation, "staging", True)
        )
        self.assertTrue((self.root / "private-runtime.env").exists())
        (self.root / "private-input-cleanup.json").unlink()
        receipt["fixture_identities_disabled"] = True
        receipt["binding"] = {**binding, "component": "wrong"}
        path.write_text(json.dumps(receipt))
        self.assertFalse(
            r.cleanup_probe_inputs(self.root, binding, self.operation, "staging", True)
        )
        self.assertTrue((self.root / "private-runtime.env").exists())
        (self.root / "private-input-cleanup.json").unlink()
        receipt["binding"] = binding
        path.write_text(json.dumps(receipt))
        self.assertFalse(
            r.cleanup_probe_inputs(self.root, binding, self.operation, "staging", False)
        )
        self.assertTrue((self.root / "private-runtime.env").exists())
        (self.root / "private-input-cleanup.json").unlink()
        self.assertTrue(
            r.cleanup_probe_inputs(self.root, binding, self.operation, "staging", True)
        )
        self.assertFalse((self.root / "private-runtime.env").exists())

    def test_sigterm_runs_existing_cleanup_path_and_restores_handler(self):
        previous = signal.getsignal(signal.SIGTERM)

        def execute(*_args):
            os.kill(os.getpid(), signal.SIGTERM)

        with (
            patch.object(producer.sys, "argv", ["probe", "staging", "--stdin-request"]),
            patch.object(producer.sys, "stdin") as stdin,
            patch.object(producer, "execute", side_effect=execute),
            patch.object(producer, "record_boundary_failure") as record,
        ):
            stdin.buffer.read.return_value = b"{}"
            with self.assertRaisesRegex(producer.Refused, "INTERRUPTED_NOT_QUALIFIED"):
                producer.main()
            record.assert_called_once()
        self.assertEqual(signal.getsignal(signal.SIGTERM), previous)


if __name__ == "__main__":
    unittest.main()
