"""Manage only repository-owned loopback documentation gateways."""

import argparse
import os
import signal
import socket
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "data/runtime/docs"


def run(action):
    STATE.mkdir(parents=True, exist_ok=True)
    for scope, port in [("public", 3200), ("internal", 3201)]:
        pidfile = STATE / f"{scope}.pid"
        command = [
            str(ROOT / ".venv/bin/python"),
            str(ROOT / "scripts/docs/gateway.py"),
            "--scope",
            scope,
        ]
        if action == "stop":
            if not pidfile.exists():
                continue
            pid = int(pidfile.read_text())
            observed = subprocess.run(
                ["ps", "-p", str(pid), "-o", "command="],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            if observed.endswith(" " + " ".join(command[1:])) and (
                observed.startswith(
                    (
                        command[0] + " ",
                        str((ROOT / ".venv/bin/python").resolve()) + " ",
                        str(
                            (ROOT / ".venv/bin/python").resolve().parent.parent
                            / "Resources/Python.app/Contents/MacOS/Python"
                        )
                        + " ",
                    )
                )
            ):
                os.kill(pid, signal.SIGTERM)
                for _ in range(40):
                    with socket.socket() as probe:
                        if probe.connect_ex(("127.0.0.1", port)) != 0:
                            break
                    time.sleep(0.1)
                else:
                    raise SystemExit(f"{scope} gateway has not stopped")
                pidfile.unlink()
            else:
                print(f"Refused to signal stale/foreign {scope} PID.")
            continue
        with socket.socket() as probe:
            occupied = probe.connect_ex(("127.0.0.1", port)) == 0
        if action == "status" or occupied:
            print(
                f"{scope} loopback port {port}: {'occupied' if occupied else 'not running'}"
            )
            continue
        if not (
            ROOT / f"onesa-ai-platform-frontend/apps/docs/build-{scope}/index.html"
        ).exists():
            raise SystemExit(f"Build {scope} before starting its gateway")
        fd = os.open(
            STATE / f"{scope}.log", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
        )
        with os.fdopen(fd, "ab") as log:
            process = subprocess.Popen(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=ROOT,
                start_new_session=True,
            )
        pidfile.write_text(str(process.pid))
        print(f"Started {scope} protected delivery at http://localhost:{port}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop", "status"])
    run(parser.parse_args().action)
