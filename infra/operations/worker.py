"""Private scheduled pg_dump, authenticated encryption, bounded retention and local alerts."""

import base64
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

BACKUPS = Path("/backups")
STATE = Path("/state")
MAGIC = b"ONESA-BACKUP-V1\n"
lock = threading.Lock()
status = {
    "backup_success": 0,
    "backup_last_success_timestamp_seconds": 0,
    "backup_failures_total": 0,
    "alert_deliveries_total": 0,
    "backup_in_progress": 0,
    "backup_duration_seconds": 0,
}


def credentials(owner=False):
    source = Path(
        "/run/secrets/owner_pgpass" if owner else "/run/secrets/backup_pgpass"
    )
    destination = Path("/tmp/owner.pgpass" if owner else "/tmp/backup.pgpass")
    destination.write_bytes(source.read_bytes())
    destination.chmod(0o600)
    return {
        **os.environ,
        "PGHOST": "db",
        "PGPORT": "5432",
        "PGUSER": "onesa" if owner else "onesa_backup",
        "PGPASSFILE": str(destination),
    }


def encryption_key():
    key = base64.b64decode(Path("/run/secrets/backup_key").read_bytes(), validate=True)
    if len(key) != 32:
        raise ValueError("Invalid backup key")
    return key


def encrypt(source, destination):
    nonce = secrets.token_bytes(12)
    cipher = Cipher(algorithms.AES(encryption_key()), modes.GCM(nonce)).encryptor()
    with source.open("rb") as incoming, destination.open("xb") as outgoing:
        outgoing.write(MAGIC + nonce)
        for block in iter(lambda: incoming.read(1024 * 1024), b""):
            outgoing.write(cipher.update(block))
        outgoing.write(cipher.finalize() + cipher.tag)
    destination.chmod(0o600)


def decrypt(source, destination):
    # Decrypt fully to a private temporary file before pg_restore; authentication is mandatory.
    with source.open("rb") as incoming, destination.open("xb") as outgoing:
        if incoming.read(len(MAGIC)) != MAGIC:
            raise ValueError("Unknown archive")
        nonce = incoming.read(12)
        remaining = source.stat().st_size - len(MAGIC) - 12 - 16
        if remaining < 1:
            raise ValueError("Truncated archive")
        incoming.seek(-16, 2)
        tag = incoming.read(16)
        incoming.seek(len(MAGIC) + 12)
        cipher = Cipher(
            algorithms.AES(encryption_key()), modes.GCM(nonce, tag)
        ).decryptor()
        while remaining:
            block = incoming.read(min(remaining, 1024 * 1024))
            if not block:
                raise ValueError("Truncated archive")
            remaining -= len(block)
            outgoing.write(cipher.update(block))
        outgoing.write(cipher.finalize())
    destination.chmod(0o600)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as incoming:
        for block in iter(lambda: incoming.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def backup():
    if not lock.acquire(blocking=False):
        return False
    status["backup_in_progress"] = 1
    started = time.monotonic()
    try:
        environment = credentials()
        with tempfile.TemporaryDirectory(prefix="onesa-backup-") as directory:
            plain = Path(directory) / "database.dump"
            subprocess.run(
                [
                    "pg_dump",
                    "-d",
                    "onesa",
                    "--format=custom",
                    "--no-owner",
                    "--no-acl",
                    "-f",
                    str(plain),
                ],
                env=environment,
                check=True,
                capture_output=True,
                timeout=600,
            )
            subprocess.run(
                ["pg_restore", "--list", str(plain)],
                check=True,
                capture_output=True,
                timeout=30,
            )
            name = (
                time.strftime("database-%Y%m%dT%H%M%SZ", time.gmtime())
                + "-"
                + secrets.token_hex(3)
            )
            temporary = BACKUPS / (name + ".partial")
            target = BACKUPS / (name + ".dump.enc")
            try:
                encrypt(plain, temporary)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
            # Listing alone does not qualify restoration; acceptance restores into a fresh database.
            manifest = {
                "file": target.name,
                "created_at": time.time(),
                "encrypted_sha256": digest(target),
                "plaintext_sha256": digest(plain),
            }
            (BACKUPS / (name + ".json")).write_text(json.dumps(manifest))
            (BACKUPS / (name + ".json")).chmod(0o600)
        days = int(os.environ.get("ONESA_BACKUP_RETENTION_DAYS", "7"))
        if not 1 <= days <= 3650:
            raise ValueError("Invalid retention")
        archives = sorted(BACKUPS.glob("*.dump.enc"), key=lambda p: p.stat().st_mtime)
        for archive in archives[:-1]:
            if archive.stat().st_mtime < time.time() - days * 86400:
                archive.unlink()
                archive.with_name(
                    archive.name.removesuffix(".dump.enc") + ".json"
                ).unlink(missing_ok=True)
        status["backup_success"] = 1
        status["backup_last_success_timestamp_seconds"] = time.time()
        return True
    except (OSError, ValueError, subprocess.SubprocessError):
        status["backup_success"] = 0
        status["backup_failures_total"] += 1
        # Never log SQL, credentials, document data or subprocess stderr.
        print(json.dumps({"event": "backup_failed"}), flush=True)
        return False
    finally:
        status["backup_duration_seconds"] = time.monotonic() - started
        status["backup_in_progress"] = 0
        try:
            (STATE / "backup-status.json").write_text(json.dumps(status))
        finally:
            lock.release()


def schedule():
    interval = int(os.environ.get("ONESA_BACKUP_INTERVAL_SECONDS", "3600"))
    if not 30 <= interval <= 86400:
        raise ValueError("Invalid backup interval")
    while True:
        backup()
        time.sleep(interval)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, code, body=b"", content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        token = Path("/run/secrets/operations_token").read_text().strip()
        return secrets.compare_digest(
            self.headers.get("Authorization", ""), "Bearer " + token
        )

    def do_GET(self):
        if self.path == "/health":
            return self.reply(200, b'{"status":"ok"}')
        if not self.authorized():
            return self.reply(403)
        if self.path == "/metrics":
            values = {
                **status,
                "storage_available_bytes": shutil.disk_usage(BACKUPS).free,
                "storage_total_bytes": shutil.disk_usage(BACKUPS).total,
                "backup_files": len(list(BACKUPS.glob("*.dump.enc"))),
            }
            output = (
                "\n".join(
                    f"onesa_operations_{name} {value}" for name, value in values.items()
                )
                + "\n"
            )
            return self.reply(200, output.encode(), "text/plain; version=0.0.4")
        if self.path == "/status":
            deliveries = []
            path = STATE / "alerts.jsonl"
            if path.exists():
                deliveries = [
                    json.loads(line) for line in path.read_text().splitlines()[-50:]
                ]
            return self.reply(
                200,
                json.dumps(
                    {
                        **status,
                        "archives": sorted(p.name for p in BACKUPS.glob("*.dump.enc")),
                        "alerts": deliveries,
                    }
                ).encode(),
            )
        self.reply(404)

    def do_POST(self):
        if not self.authorized():
            return self.reply(403)
        length = int(self.headers.get("Content-Length", "0"))
        if length > 65536:
            return self.reply(413)
        if self.path == "/backup":
            return self.reply(200 if backup() else 503)
        if self.path == "/alerts":
            try:
                data = json.loads(self.rfile.read(length))
                alerts = [
                    {
                        "name": str(item.get("labels", {}).get("alertname", "unknown"))[
                            :100
                        ],
                        "status": item.get("status", "unknown"),
                        "received_at": time.time(),
                    }
                    for item in data.get("alerts", [])[:50]
                ]
                with (STATE / "alerts.jsonl").open("a") as output:
                    for alert in alerts:
                        output.write(json.dumps(alert) + "\n")
                status["alert_deliveries_total"] += len(alerts)
                return self.reply(200)
            except (ValueError, TypeError):
                return self.reply(400)
        self.reply(404)


def restore():
    target = os.environ.get("ONESA_RESTORE_DATABASE", "")
    archive = BACKUPS / os.environ.get("ONESA_RESTORE_ARCHIVE", "")
    import re

    if (
        len(target) > 63
        or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}_restore", target)
        or archive.parent != BACKUPS
        or not archive.is_file()
    ):
        raise SystemExit(
            "Use an existing encrypted archive and a new safe _restore database"
        )
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="onesa-restore-") as directory:
        plain = Path(directory) / "verified.dump"
        decrypt(archive, plain)
        environment = credentials(owner=True)
        subprocess.run(
            ["createdb", target],
            env=environment,
            check=True,
            capture_output=True,
            timeout=30,
        )
        subprocess.run(
            [
                "pg_restore",
                "-d",
                target,
                "--no-owner",
                "--no-acl",
                "--exit-on-error",
                str(plain),
            ],
            env=environment,
            check=True,
            capture_output=True,
            timeout=600,
        )
    print(
        json.dumps(
            {
                "restored": True,
                "database": target,
                "seconds": time.monotonic() - started,
            }
        )
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["restore"]:
        restore()
    else:
        STATE.mkdir(exist_ok=True)
        previous = STATE / "backup-status.json"
        if previous.exists():
            status.update(json.loads(previous.read_text()))
        status["backup_in_progress"] = 0
        threading.Thread(target=schedule, daemon=True).start()
        ThreadingHTTPServer(("0.0.0.0", 9000), Handler).serve_forever()
