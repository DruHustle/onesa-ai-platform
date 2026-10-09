"""Create isolated acceptance secrets once; never overwrite the developer environment."""

import base64
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "data/acceptance-005"
STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
private = STATE / "secrets"
private.mkdir(mode=0o700, exist_ok=True)
owner, app, backup = (secrets.token_urlsafe(32) for _ in range(3))
metrics, operations = (secrets.token_urlsafe(32) for _ in range(2))
key = base64.b64encode(secrets.token_bytes(32)).decode()
files = {
    "metrics_token": metrics,
    "operations_token": operations,
    "backup_key": key,
    "backup.pgpass": f"db:5432:*:onesa_backup:{backup}\n",
    "owner.pgpass": f"db:5432:*:onesa:{owner}\n",
}
if (STATE / "staging.env").exists():
    raise SystemExit("Acceptance environment already exists; secrets were not replaced")
for name, value in files.items():
    fd = os.open(private / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(fd, "w") as file:
        file.write(value)
content = "\n".join(
    [
        f"ONESA_DB_PASSWORD={owner}",
        f"ONESA_APP_DB_PASSWORD={app}",
        f"ONESA_BACKUP_DB_PASSWORD={backup}",
        f"ONESA_APP_DATABASE_URL=postgresql+psycopg://onesa_app:{app}@db:5432/onesa",
        f"ONESA_METRICS_TOKEN={metrics}",
        "ONESA_MODEL_BACKEND=mock",
        "ONESA_MODEL_NAME=Qwen/Qwen3-4B-Instruct-2507",
        "ONESA_MODEL_API_KEY=",
        "ONESA_ENVIRONMENT=staging",
        "ONESA_SECURE_COOKIES=true",
        "ONESA_PUBLIC_ORIGIN=https://localhost:3443",
        "ONESA_DOMAIN=localhost",
        "ONESA_AUTH_RATE_LIMIT=10",
        "ONESA_AUTH_PEER_RATE_LIMIT=1000",
        "ONESA_BACKUP_INTERVAL_SECONDS=3600",
        "ONESA_BACKUP_RETENTION_DAYS=7",
        "",
    ]
)
fd = os.open(STATE / "staging.env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as file:
    file.write(content)
print("Created isolated private staging configuration; developer .env was untouched")
