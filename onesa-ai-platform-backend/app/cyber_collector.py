"""Optional bounded durable JSON/NDJSON delivery; no discovery, probing or commands."""

import argparse
import fcntl
import json
import os
import stat
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from app.cyber_schemas import bounded_json, parse_batch


def private(path: Path, *, directory: bool = False) -> Path:
    metadata = path.lstat()
    if (
        path.is_symlink()
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
        or not (stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode))
    ):
        raise ValueError("Collector custody must be owned, private and nonsymlinked")
    return path


def drain(config_path: Path, *, client: Any = None, pause: Any = time.sleep) -> dict[str, int]:
    private(config_path)
    if config_path.stat().st_size > 8192:
        raise ValueError("Collector configuration is oversized")
    config = bounded_json(config_path.read_bytes(), 8192)
    if not isinstance(config, dict) or set(config) != {"endpoint", "token_file", "outbox"}:
        raise ValueError("Use exactly endpoint, token_file and outbox configuration")
    endpoint = urlsplit(config["endpoint"])
    if (
        endpoint.scheme != "https"
        or not endpoint.hostname
        or endpoint.username
        or endpoint.password
        or endpoint.query
        or endpoint.fragment
        or endpoint.path != "/api/v1/cybersecurity/ingest"
    ):
        raise ValueError("Configure an explicit HTTPS security ingestion endpoint")
    credential_file = private(Path(config["token_file"]))
    if credential_file.stat().st_size > 128:
        raise ValueError("Collector credential is oversized")
    token = credential_file.read_text().strip()
    if not 40 <= len(token) <= 100 or any(char.isspace() for char in token):
        raise ValueError("A scoped private source credential is required")
    outbox = private(Path(config["outbox"]), directory=True)
    accepted, rejected = outbox / "accepted", outbox / "rejected"
    for directory in (accepted, rejected):
        directory.mkdir(mode=0o700, exist_ok=True)
        private(directory, directory=True)
    files = [p for p in outbox.rglob("*") if p.is_file()]
    if len(files) > 128 or sum(p.lstat().st_size for p in files) > 8 * 1048576:
        raise ValueError(
            "Outbox archive capacity reached; review private retention before delivery"
        )
    lock_path = outbox / ".delivery.lock"
    descriptor = os.open(lock_path, os.O_CREAT | os.O_NOFOLLOW | os.O_RDWR, 0o600)
    counts = {"accepted": 0, "rejected": 0, "pending": 0, "requests": 0}
    own_client = client is None
    client = client or httpx.Client(timeout=10, follow_redirects=False, trust_env=False)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another bounded collector drain is active") from None
        pending = sorted(p for p in outbox.iterdir() if p.suffix in {".json", ".ndjson"})
        for file in pending[:5]:
            private(file)
            raw = file.read_bytes() if file.stat().st_size <= 1048576 else b""
            try:
                if not raw:
                    raise ValueError("empty or oversized")
                parse_batch(raw, file.suffix == ".ndjson")
            except (ValueError, UnicodeError):
                os.replace(file, rejected / (str(uuid4()) + file.suffix))
                counts["rejected"] += 1
                continue
            terminal = False
            for attempt in range(3):
                counts["requests"] += 1
                try:
                    response = client.post(
                        config["endpoint"],
                        content=raw,
                        headers={
                            "Authorization": "Bearer " + token,
                            "Content-Type": "application/x-ndjson"
                            if file.suffix == ".ndjson"
                            else "application/json",
                        },
                    )
                    if response.status_code == 200:
                        receipt = bounded_json(response.content, 16384)
                        if (
                            not isinstance(receipt, dict)
                            or set(receipt) != {"inserted", "duplicates", "event_ids"}
                            or type(receipt["inserted"]) is not int
                            or type(receipt["duplicates"]) is not int
                            or not isinstance(receipt["event_ids"], list)
                        ):
                            raise ValueError("Incomplete receiver acknowledgement")
                        os.replace(file, accepted / (str(uuid4()) + file.suffix))
                        counts["accepted"] += 1
                        terminal = True
                        break
                    if response.status_code not in {408, 425, 429, 500, 502, 503, 504}:
                        os.replace(file, rejected / (str(uuid4()) + file.suffix))
                        counts["rejected"] += 1
                        terminal = True
                        break
                except (httpx.HTTPError, ValueError):
                    pass
                if attempt < 2:
                    pause((0.5, 1.0)[attempt])
            if not terminal:
                counts["pending"] += 1
        counts["pending"] += max(0, len(pending) - 5)
        return counts
    finally:
        if own_client:
            client.close()
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = drain(args.config)
        print(json.dumps(result, sort_keys=True))
    except (OSError, ValueError, httpx.HTTPError):
        # Never emit endpoint URLs, credential values, payloads or exception text.
        raise SystemExit(
            "Collector unavailable; inspect private custody/configuration and retry"
        ) from None


if __name__ == "__main__":
    main()
