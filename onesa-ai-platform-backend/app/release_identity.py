"""Public build/instance identity for deployment-path verification, never authority."""

import hashlib
import json
import os
import re
from pathlib import Path

IDENTITY = Path("/app/source-identity.json")


def identity(environment: str) -> dict[str, str]:
    if not IDENTITY.is_file() or IDENTITY.is_symlink() or IDENTITY.stat().st_size > 4096:
        return {}
    try:
        value = json.loads(IDENTITY.read_bytes())
    except (OSError, ValueError):
        return {}
    if not isinstance(value, dict):
        return {}
    source = value.get("source_commit", "")
    archive = value.get("source_archive_sha256", "")
    if (
        not isinstance(source, str)
        or not isinstance(archive, str)
        or not re.fullmatch("[a-f0-9]{40}", source)
        or not re.fullmatch("[a-f0-9]{64}", archive)
    ):
        return {}
    # Do not expose the hostname. This stable per-container fingerprint also
    # distinguishes two instances of the same build across staging/production.
    instance = hashlib.sha256(
        (os.getenv("HOSTNAME", "") + "|" + environment + "|" + archive).encode()
    ).hexdigest()
    return {"source_commit": source, "source_archive_sha256": archive, "instance_id": instance}
