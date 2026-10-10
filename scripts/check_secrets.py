"""Offline repository-source secret gate; diagnostics never print matched credentials."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{36,255}\b"),
    re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}\b"),
    re.compile(rb"\bre_[A-Za-z0-9_-]{30,}\b"),
    re.compile(rb"\bn(?:ak|sk)_live_[A-Za-z0-9_-]{24,}\b"),
    re.compile(rb"\bnpg_[A-Za-z0-9_-]{12,}\b"),
]
paths = (
    subprocess.check_output(
        [
            "git",
            "-C",
            str(ROOT),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ]
    )
    .decode()
    .split("\0")
)
failures = []
for name in paths:
    if not name:
        continue
    path = ROOT / name
    if (
        path.name == ".env"
        or (path.name.startswith(".env.") and not path.name.endswith(".example"))
        or path.is_file()
        and any(pattern.search(path.read_bytes()) for pattern in PATTERNS)
    ):
        failures.append(name)
if failures:
    raise SystemExit(
        "Potential private credentials in repository files: " + ", ".join(failures)
    )
print("Repository-source secret patterns and private environment file checks passed")
