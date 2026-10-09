"""Manage only this repository's loopback Ollama process; never replace another server."""

import argparse
import json
import os
import signal
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "data/runtime/ollama"
BINARY = STATE / "ollama"
PID_FILE = STATE / "server.pid"


def occupied() -> bool:
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", 11434)) == 0


def start() -> None:
    if occupied():
        print("Port 11434 is already occupied; no new Ollama process started.")
        return
    if not BINARY.is_file():
        raise SystemExit(
            "Install the official native runtime in data/runtime/ollama first."
        )
    models = ROOT / "data/models/ollama"
    models.mkdir(parents=True, exist_ok=True)
    environment = {
        **os.environ,
        "OLLAMA_HOST": "127.0.0.1:11434",
        "OLLAMA_MODELS": str(models),
        "OLLAMA_CONTEXT_LENGTH": "8192",
        "OLLAMA_NO_CLOUD": "1",
        "OLLAMA_NUM_PARALLEL": "1",
        "OLLAMA_MAX_LOADED_MODELS": "1",
    }
    log = STATE / "server.log"
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "ab") as output:
        process = subprocess.Popen(
            [str(BINARY), "serve"],
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    PID_FILE.write_text(str(process.pid))
    for _ in range(40):
        if process.poll() is not None:
            raise SystemExit("Native Ollama exited; inspect the private runtime log.")
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:11434/api/version", timeout=1
            ) as response:
                print("Loopback Ollama ready:", json.load(response)["version"])
                return
        except OSError:
            time.sleep(0.25)
    raise SystemExit("Ollama has not become ready; inspect its private log.")


def stop() -> None:
    if not PID_FILE.exists():
        raise SystemExit(
            "No repository-managed server PID; another process will not be stopped."
        )
    pid = int(PID_FILE.read_text())
    command = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if command != f"{BINARY} serve":
        raise SystemExit(
            "PID does not match this repository's Ollama; refusing to signal it."
        )
    os.kill(pid, signal.SIGTERM)
    for _ in range(40):
        if not occupied():
            PID_FILE.unlink()
            print("Stopped this repository's Ollama server.")
            return
        time.sleep(0.25)
    raise SystemExit("Server has not stopped; no additional process was started.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["start", "stop", "restart", "status"])
    args = parser.parse_args()
    if args.command in {"stop", "restart"}:
        stop()
    if args.command in {"start", "restart"}:
        start()
    if args.command == "status":
        print("Port 11434 occupied:", occupied())


if __name__ == "__main__":
    main()
