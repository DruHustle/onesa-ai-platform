"""Restart only the explicitly isolated native Twin test API; never a general process tool."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if os.environ.get("ONESA_TWIN_E2E_CONTROL") != "native":
    raise SystemExit("Explicit native fixture control required")
if os.environ.get("ONESA_BROWSER_URL") != "http://127.0.0.1:3217":
    raise SystemExit("Only the isolated loopback Twin fixture is supported")
command = "uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8017"
pids = (
    subprocess.check_output(["lsof", "-t", "-iTCP:8017", "-sTCP:LISTEN"])
    .decode()
    .split()
)
if len(pids) != 1:
    raise SystemExit("Expected exactly one isolated fixture listener")
actual = subprocess.check_output(["ps", "-p", pids[0], "-o", "command="]).decode()
cwd = subprocess.check_output(
    ["lsof", "-a", "-p", pids[0], "-d", "cwd", "-Fn"]
).decode()
if command not in actual or str(ROOT / "onesa-ai-platform-backend") not in cwd:
    raise SystemExit("Refusing to stop an unverified process")
os.kill(int(pids[0]), signal.SIGTERM)
deadline = time.monotonic() + 10
while time.monotonic() < deadline:
    result = subprocess.run(
        ["lsof", "-t", "-iTCP:8017", "-sTCP:LISTEN"], capture_output=True, check=False
    )
    if result.returncode != 0:
        break
    time.sleep(0.1)
else:
    raise SystemExit("Isolated fixture did not stop; no duplicate API started")
environment = {
    **{
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "LANG", "LC_ALL", "TMPDIR"}
    },
    "ONESA_DATABASE_URL": "postgresql+psycopg://onesa:twin-test-only@127.0.0.1:55542/onesa_twins_final_ui_test",
    "ONESA_PUBLIC_ORIGIN": "http://127.0.0.1:3217",
    "ONESA_ENVIRONMENT": "test",
    "ONESA_DIGITAL_TWINS_ENABLED": "true",
    "ONESA_DIGITAL_TWINS_DEMO_ENABLED": "true",
    "ONESA_DIGITAL_TWINS_STORAGE_DIRECTORY": str(ROOT / "data/twins-files"),
    "ONESA_AUTH_RATE_LIMIT": "1000",
}
directory = ROOT / "data/twins-evidence"
directory.mkdir(parents=True, exist_ok=True, mode=0o700)
descriptor = os.open(
    directory / "native-api-restart.log", os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600
)
with os.fdopen(descriptor, "ab") as log:
    process = subprocess.Popen(
        [sys.executable, "-m", *command.split()],
        cwd=ROOT / "onesa-ai-platform-backend",
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=log,
        start_new_session=True,
    )
(directory / "native-api.pid").write_text(str(process.pid) + "\n")
print("Isolated native test API restarted with its existing database and files")
