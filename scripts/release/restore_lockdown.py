"""Offline-first lockdown for disposable restored databases only.

Legacy mode only invalidates restored capabilities. The explicit isolated-replay
mode also consumes an erasure ledger; neither mode approves hosted activation or
establishes the completeness/currentness of that ledger.
"""

import argparse
import json
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--apply-synthetic-lockdown", action="store_true")
    parser.add_argument("--replay-ledger")
    parser.add_argument("--apply-isolated-replay", action="store_true")
    args = parser.parse_args()
    if args.replay_ledger:
        import restore_replay

        print(
            json.dumps(
                restore_replay.run(
                    args.container,
                    args.database,
                    args.replay_ledger,
                    args.apply_isolated_replay,
                    SQL,
                )
            )
        )
        return
    expected = CONTAINER
    if args.container != expected or not re.fullmatch(
        r"onesa_audit_[0-9]+_restore", args.database
    ):
        raise SystemExit(
            "Refusing any target other than this task's new disposable restore database"
        )
    if not args.apply_synthetic_lockdown:
        raise SystemExit(
            "Explicit synthetic-lockdown switch is required; no changes applied"
        )
    command = [
        "docker",
        "exec",
        "-i",
        args.container,
        "psql",
        "-U",
        "audit_test",
        "-d",
        args.database,
        "-At",
        "-v",
        "ON_ERROR_STOP=1",
    ]
    result = subprocess.check_output(command, input=SQL, text=True)
    checks = [int(value) for value in result.splitlines() if value.isdecimal()]
    if not checks or any(checks):
        raise SystemExit("Restored capability lockdown verification failed")
    print(
        json.dumps(
            {
                "result": "PASS",
                "checks": len(checks),
                "remaining_active_capabilities": 0,
                "scope": "synthetic restore capability invalidation; erased-user/object/unpublication reconciliation and hosted recovery remain BLOCKED",
            }
        )
    )


CONTAINER = "onesa-remediation-ai-db"
SQL = "BEGIN;\nUPDATE auth_sessions SET revoked_at=now() WHERE revoked_at IS NULL;\nUPDATE identity_tokens SET revoked_at=now() WHERE revoked_at IS NULL;\nUPDATE access_grants SET expires_at=LEAST(expires_at,now());\nUPDATE identity_mail SET state='cancelled',lease_until=NULL,lease_id=NULL WHERE state IN ('queued','leased');\nUPDATE bounded_uploads SET expires_at=LEAST(expires_at,now());\nUPDATE model_leases SET expires_at=LEAST(expires_at,now());\nCOMMIT;\nSELECT count(*) FROM auth_sessions WHERE revoked_at IS NULL AND expires_at>now();\nSELECT count(*) FROM identity_tokens WHERE revoked_at IS NULL AND consumed_at IS NULL AND expires_at>now();\nSELECT count(*) FROM access_grants WHERE expires_at>now();\nSELECT count(*) FROM identity_mail WHERE state IN ('queued','leased');\nSELECT count(*) FROM bounded_uploads WHERE expires_at>now();\nSELECT count(*) FROM model_leases WHERE expires_at>now();\n"

if __name__ == "__main__":
    main()
