"""Demonstrate actual local alert delivery, encrypted recovery, and isolated service failure."""

import json
import os
import ssl
import subprocess
import time
from pathlib import Path

import httpx

from scripts.database.verify_restore import fingerprint

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "data/acceptance-005"
COMPOSE = [
    "docker",
    "compose",
    "--env-file",
    str(STATE / "staging.env"),
    "-p",
    "onesa-acceptance-005",
    "-f",
    "compose.yaml",
    "-f",
    "compose.production.yaml",
    "-f",
    "compose.acceptance.yaml",
]
TOKEN = (STATE / "secrets/operations_token").read_text().strip()
TLS = ssl.create_default_context(cafile=str(STATE / "staging-ca.crt"))
report = {
    "environment": "isolated local staging",
    "external_alert_delivery_tested": False,
}


def compose(*arguments, env=None, input=None):
    return subprocess.run(
        COMPOSE + list(arguments),
        check=True,
        capture_output=True,
        text=True,
        env=env,
        input=input,
    ).stdout


def status():
    return httpx.get(
        "http://localhost:9905/status",
        headers={"Authorization": "Bearer " + TOKEN},
        timeout=15,
    ).json()


def wait_for(predicate, label, seconds=90):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except (httpx.HTTPError, ValueError, KeyError):
            pass
        time.sleep(2)
    raise SystemExit("Acceptance timed out: " + label)


def delivered(name, state, since):
    return any(
        alert["name"] == name
        and alert["status"] == state
        and alert["received_at"] >= since
        for alert in status()["alerts"]
    )


started = time.time()
try:
    compose("stop", "api")
    wait_for(
        lambda: delivered("OnesaBackendDown", "firing", started), "backend-down alert"
    )
    report["backend_down_alert_delivered"] = True
finally:
    compose("start", "api")
wait_for(
    lambda: (
        httpx.get("https://localhost:3443/ready", verify=TLS, timeout=5).status_code
        == 200
    ),
    "backend recovery",
)
wait_for(
    lambda: delivered("OnesaBackendDown", "resolved", started),
    "backend recovered alert",
)
report["backend_recovery_alert_delivered"] = True

started = time.time()
try:
    compose(
        "exec",
        "-T",
        "db",
        "psql",
        "-U",
        "onesa",
        "-d",
        "onesa",
        "-c",
        "ALTER ROLE onesa_backup NOLOGIN",
    )
    response = httpx.post(
        "http://localhost:9905/backup",
        headers={"Authorization": "Bearer " + TOKEN},
        timeout=30,
    )
    assert response.status_code == 503
    wait_for(
        lambda: delivered("OnesaBackupFailed", "firing", started),
        "backup failure alert",
    )
    report["backup_failure_alert_delivered"] = True
finally:
    compose(
        "exec",
        "-T",
        "db",
        "psql",
        "-U",
        "onesa",
        "-d",
        "onesa",
        "-c",
        "ALTER ROLE onesa_backup LOGIN",
    )
response = httpx.post(
    "http://localhost:9905/backup",
    headers={"Authorization": "Bearer " + TOKEN},
    timeout=60,
)
response.raise_for_status()
wait_for(
    lambda: delivered("OnesaBackupFailed", "resolved", started),
    "backup recovered alert",
)
report["backup_recovery_alert_delivered"] = True
archive = status()["archives"][-1]
recovered = "onesa_acceptance_005_" + str(int(time.time())) + "_restore"
started = time.monotonic()
restored = compose(
    "--profile",
    "recovery",
    "run",
    "--build",
    "--rm",
    "-e",
    "ONESA_RESTORE_DATABASE=" + recovered,
    "-e",
    "ONESA_RESTORE_ARCHIVE=" + archive,
    "restore",
)
report["restore"] = json.loads(restored.strip().splitlines()[-1])
report["recovery_wall_seconds"] = time.monotonic() - started
os.environ["ONESA_PROJECT_NAME"] = "onesa-acceptance-005"
os.environ["ONESA_COMPOSE_ENV_FILE"] = str(STATE / "staging.env")
original, recovery = fingerprint("onesa"), fingerprint(recovered)
assert original == recovery, "Restored table counts/content differ"
report["tables"] = original
report["verified_tables"] = len(original)
report["data_loss_in_snapshot_seconds"] = 0
report["production_rpo_rto_achieved"] = False
report["backup_status"] = {
    key: value for key, value in status().items() if key != "alerts"
}
(STATE / "operations-recovery.json").write_text(json.dumps(report, indent=2) + "\n")
print(
    "Actual backend/backup firing and resolved alerts delivered locally; encrypted restore matched all tables"
)
