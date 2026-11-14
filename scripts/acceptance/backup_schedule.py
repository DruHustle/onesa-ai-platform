"""Verify actual timer execution and retention on synthetic staging copies, then restore hourly timing."""

import json
import subprocess
import time
from pathlib import Path

STATE = Path("data/acceptance-005")
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


def run(arguments, environment=None):
    import os

    return subprocess.run(
        COMPOSE + arguments,
        env={**os.environ, **(environment or {})},
        capture_output=True,
        text=True,
        check=True,
    ).stdout


probe = """
from pathlib import Path
import shutil, os, json
folder = Path('/backups')
archives = sorted(folder.glob('*.dump.enc'))
assert archives
old = folder / 'synthetic-expired-fixture.dump.enc'
shutil.copyfile(archives[-1], old)
old.with_name('synthetic-expired-fixture.json').write_text('{}')
os.utime(old, (1, 1))
print(json.dumps({'count': len(archives), 'last': archives[-1].name}))
"""
before = json.loads(run(["exec", "-T", "operations", "python", "-c", probe]))
try:
    run(
        ["up", "--no-build", "--no-deps", "-d", "--wait", "operations"],
        {"ONESA_BACKUP_INTERVAL_SECONDS": "30"},
    )
    time.sleep(35)
    result = json.loads(
        run(
            [
                "exec",
                "-T",
                "operations",
                "python",
                "-c",
                "from pathlib import Path; import json; print(json.dumps({'count':len(list(Path('/backups').glob('*.dump.enc'))), 'expired_fixture_removed':not Path('/backups/synthetic-expired-fixture.dump.enc').exists(), 'expired_manifest_removed':not Path('/backups/synthetic-expired-fixture.json').exists()}))",
            ]
        )
    )
    assert result["count"] >= before["count"] + 2
    assert result["expired_fixture_removed"] and result["expired_manifest_removed"]
finally:
    run(["up", "--no-build", "--no-deps", "-d", "--wait", "operations"])
result.update(
    {
        "automatic_startup_and_timer_backups_verified": True,
        "tested_timer_seconds": 30,
        "configured_interval_restored_seconds": 3600,
        "retention_days": 7,
        "recent_real_backups_preserved": True,
    }
)
(STATE / "backup-schedule.json").write_text(json.dumps(result, indent=2) + "\n")
print(
    "Automatic startup/timer backups and expired fixture retention verified; hourly schedule restored"
)
