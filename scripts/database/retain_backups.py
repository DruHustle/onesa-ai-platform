"""Apply explicit backup retention; preview is the default and latest dump is preserved."""

import argparse
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("directory", type=Path)
parser.add_argument("--days", type=int, default=30)
parser.add_argument("--apply", action="store_true")
args = parser.parse_args()
if args.days < 1 or args.directory.is_symlink():
    raise SystemExit("Use a real backup directory and positive retention days")
files = sorted(
    (p for p in args.directory.glob("*.dump") if p.is_file() and not p.is_symlink()),
    key=lambda p: p.stat().st_mtime,
)
for path in files[:-1]:
    if path.stat().st_mtime < time.time() - args.days * 86400:
        print(("Removing " if args.apply else "Would remove ") + path.name)
        if args.apply:
            path.unlink()
