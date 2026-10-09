"""Compare source/restored schemas and content without printing private records."""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path


def query(database: str, sql: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "compose",
            *(
                ["--env-file", os.environ["ONESA_COMPOSE_ENV_FILE"]]
                if "ONESA_COMPOSE_ENV_FILE" in os.environ
                else []
            ),
            "-p",
            os.environ.get("ONESA_PROJECT_NAME", "onesa-platform"),
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "onesa",
            "-d",
            database,
            "-At",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def fingerprint(database: str) -> dict[str, dict[str, str]]:
    names = query(
        database,
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename",
    ).splitlines()
    result = {}
    for name in names:
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", name):
            raise SystemExit("Unexpected table identifier")
        value = query(
            database,
            f"SELECT count(*) || ':' || coalesce(md5(string_agg(row_hash, '' ORDER BY row_hash)), md5('')) FROM (SELECT md5(row_to_json(t)::text) AS row_hash FROM public.{name} t) rows",
        )
        count, digest = value.split(":")
        result[name] = {"rows": count, "content_digest": digest}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("restored")
    parser.add_argument("--source", default="onesa")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(
        r"[a-z][a-z0-9_]{0,62}", args.restored
    ) or not args.restored.endswith("_restore"):
        raise SystemExit("Verify an isolated _restore database")
    original, restored = fingerprint(args.source), fingerprint(args.restored)
    if original != restored:
        raise SystemExit("Backup verification failed: table counts/content differ")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        json.dump({"verified": True, "tables": original}, output, indent=2)
        output.write("\n")
    print(f"Verified all {len(original)} public tables: counts and content match")
