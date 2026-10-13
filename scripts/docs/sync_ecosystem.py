"""Refresh reviewed committed cross-product contracts and schema snapshots offline."""

import ast
import hashlib
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[2]
folder = root / "docs/ecosystem"
import argparse

parser = argparse.ArgumentParser(
    description="Operator-only refresh of reviewed committed sibling API/schema snapshots; no network, credentials or live databases."
)
parser.add_argument("--portal", required=True, type=Path)
parser.add_argument("--robot", required=True, type=Path)
args = parser.parse_args()
manifest = json.loads((folder / "source-revisions.json").read_text())
for name in manifest:
    repo = args.portal if name == "onesa-company-portal" else args.robot
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    r = manifest[name]
    r["commit"] = sha
    if name == "onesa-ai-robot":
        for p in [
            "onesa-ai-robot-backend/robot_api/turso.py",
            "onesa-ai-robot-backend/robot_api/safety.py",
            "ros2/onesa_sim_interfaces/msg/SimulationTelemetry.msg",
            "ros2/onesa_sim_interfaces/msg/SimulationProposal.msg",
        ]:
            r["sources"][p] = ""
    for p in r["sources"]:
        raw = subprocess.check_output(["git", "show", sha + ":" + p], cwd=repo)
        r["sources"][p] = hashlib.sha256(raw).hexdigest()
    if name == "onesa-company-portal":
        contract = json.loads(
            subprocess.check_output(
                [
                    "git",
                    "show",
                    sha + ":onesa-company-portal-backend/openapi/openapi.json",
                ],
                cwd=repo,
            )
        )
        contract.pop("servers", None)
        (folder / "contracts/portal-internal.json").write_text(
            json.dumps(contract, indent=2) + "\n"
        )
        public = json.loads(json.dumps(contract))
        public["paths"] = {
            p: v for p, v in public["paths"].items() if p.startswith("/api/v1/public/")
        }
        refs = set()

        def visit(v, refs=refs, public=public):
            if isinstance(v, dict):
                ref = v.get("$ref", "")
                if ref.startswith("#/components/schemas/"):
                    k = ref.rsplit("/", 1)[-1]
                    if k not in refs:
                        refs.add(k)
                        visit(public["components"]["schemas"][k])
                for value in v.values():
                    visit(value)
            elif isinstance(v, list):
                for value in v:
                    visit(value)

        visit(public["paths"])
        public["components"]["schemas"] = {
            k: v
            for k, v in public.get("components", {}).get("schemas", {}).items()
            if k in refs
        }
        (folder / "contracts/portal-public.json").write_text(
            json.dumps(public, indent=2) + "\n"
        )
    if name == "onesa-ai-robot":
        contract = json.loads(
            subprocess.check_output(
                [
                    "git",
                    "show",
                    sha + ":onesa-ai-robot-frontend/contracts/openapi.json",
                ],
                cwd=repo,
            )
        )
        contract.pop("servers", None)
        (folder / "contracts/robot.json").write_text(
            json.dumps(contract, indent=2, sort_keys=True) + "\n"
        )
        main = ast.parse(
            subprocess.check_output(
                ["git", "show", sha + ":onesa-ai-robot-backend/robot_api/main.py"],
                cwd=repo,
                text=True,
            )
        )
        local = next(
            n.value
            for n in ast.walk(main)
            if isinstance(n, ast.Constant)
            and isinstance(n.value, str)
            and "CREATE TABLE IF NOT EXISTS sessions" in n.value
        )
        turso = ast.parse(
            subprocess.check_output(
                ["git", "show", sha + ":onesa-ai-robot-backend/robot_api/turso.py"],
                cwd=repo,
                text=True,
            )
        )
        constants = {
            n.targets[0].id: n.value.value
            for n in turso.body
            if isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Name)
            and isinstance(n.value, ast.Constant)
        }
        remote = []
        for n in ast.walk(turso):
            if isinstance(n, ast.JoinedStr):
                parts = []
                for v in n.values:
                    if isinstance(v, ast.Constant):
                        parts.append(v.value)
                    elif (
                        isinstance(v, ast.FormattedValue)
                        and isinstance(v.value, ast.Name)
                        and v.value.id in constants
                    ):
                        parts.append(constants[v.value.id])
                    else:
                        break
                else:
                    s = "".join(parts)
                    if s.startswith("CREATE TABLE IF NOT EXISTS "):
                        remote.append(s + ";")
        assert len(remote) == 2
        sql = (
            local.strip()
            + "\n\n-- Separate remote staging journal; local sessions/safety are not uploaded.\n"
            + "\n".join(remote)
            + "\n"
        )
        (folder / "robot-schema.sql").write_text(sql)
        (folder / "ROBOT_DATABASE.md").write_text(
            "# Robot database schema\n\nGenerated from pinned `robot_api/main.py` local DDL and `robot_api/turso.py` remote staging journal DDL. No live records or credential export. Local sessions and safety state remain process-local with Turso; only bounded task history and the exclusive owner lease persist remotely. Restart starts stopped and cancels unfinished execution. Remote Turso remains staging-only; this does not qualify production durability.\n\n```sql\n"
            + sql
            + "```\n"
        )
        import sqlite3

        db = sqlite3.connect(":memory:")
        db.executescript("\n".join(remote))
        lines = ["erDiagram"]
        for (table,) in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ):
            lines.append("  " + table + " {")
            for _, col, typ, notnull, default, pk in db.execute(
                "PRAGMA table_info(" + table + ")"
            ):
                lines.append("    " + typ + " " + col + (" PK" if pk else ""))
            lines.append("  }")
        (root / "docs/diagrams/robot-journal-database.mmd").write_text(
            "\n".join(lines) + "\n"
        )
(folder / "source-revisions.json").write_text(json.dumps(manifest, indent=2) + "\n")
hashes = json.loads((folder / "snapshot-hashes.json").read_text())
for p in hashes:
    hashes[p] = hashlib.sha256((folder / p).read_bytes()).hexdigest()
(folder / "snapshot-hashes.json").write_text(json.dumps(hashes, indent=2) + "\n")
catpath = root / "docs/diagrams/catalog.json"
cat = json.loads(catpath.read_text())
cat = [d for d in cat if d["id"] != "robot-journal-database"] + [
    {
        "id": "robot-journal-database",
        "title": "Robot remote staging journal schema",
        "view": "implemented schema",
        "status": "Generated from actual pinned Turso DDL; independent task history and exclusive lease, no invented foreign keys",
        "source": "docs/diagrams/robot-journal-database.mmd",
        "url": "/docs/ecosystem/ROBOT_DATABASE",
        "nodes": [],
    }
]
map = {
    "Portal": "/docs/ecosystem/PORTAL_DESIGN",
    "AI": "/docs/architecture/SYSTEM_ARCHITECTURE",
    "Robot": "/docs/ecosystem/ROBOT_DESIGN",
    "PDB": "/docs/ecosystem/PORTAL_DATABASE",
    "ADB": "/database",
    "Turso": "/docs/ecosystem/ROBOT_DATABASE",
    "Oracle": "/docs/ecosystem/PORTAL_DESIGN",
    "Scan": "/docs/ecosystem/PORTAL_DESIGN",
    "CF": "/docs/architecture/MODEL_SERVING",
    "Actions": "/docs/engineering/DEPLOYMENT",
    "Internal": "/docs/engineering/DOCUMENTATION_HOSTING",
    "Access": "/docs/engineering/DOCUMENTATION_HOSTING",
    "Edge": "/docs/ecosystem/ROBOT_DESIGN",
}
for d in cat:
    if d["id"] == "ecosystem-current":
        for n in d["nodes"]:
            n["url"] = map.get(n["id"], d["url"])
catpath.write_text(json.dumps(cat, indent=2) + "\n")
print(
    "Pinned current committed API/schema source snapshots; generated separate Turso ERD"
)
