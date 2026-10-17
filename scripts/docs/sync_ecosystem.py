"""Refresh reviewed committed cross-product contracts and schema snapshots offline."""

import ast
import hashlib
import json
import re
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
    if name == "onesa-company-portal":
        paths = subprocess.check_output(
            [
                "git",
                "ls-tree",
                "-r",
                "--name-only",
                sha,
                "onesa-company-portal-backend/migrations",
            ],
            cwd=repo,
            text=True,
        ).splitlines()
        for path in paths:
            if path.endswith(".sql"):
                r["sources"][path] = ""
        r["sources"]["docs/engineering/PRIVACY_GOVERNANCE.md"] = ""
        r["sources"]["docs/engineering/ENGINEERING_DOCS_IDENTITY.md"] = ""
        r["sources"]["onesa-company-portal-backend/src/services/migration-plan.ts"] = ""
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
        migrations = sorted(
            path
            for path in r["sources"]
            if path.startswith("onesa-company-portal-backend/migrations/")
            and path.endswith(".sql")
        )
        sql = (
            "\n\n".join(
                "-- "
                + Path(path).name
                + "\n"
                + subprocess.check_output(
                    ["git", "show", sha + ":" + path], cwd=repo, text=True
                ).strip()
                for path in migrations
            )
            + "\n"
        )
        runner = subprocess.check_output(
            [
                "git",
                "show",
                sha + ":onesa-company-portal-backend/src/services/migration-plan.ts",
            ],
            cwd=repo,
            text=True,
        )
        tracker = re.findall(
            r"connection\.query\('([^']*CREATE TABLE IF NOT EXISTS schema_migrations[^']*)'\)",
            runner,
        )
        assert len(tracker) == 1
        sql = (
            "-- Migration-runner metadata; application tables follow.\n"
            + tracker[0]
            + ";\n\n"
            + sql
        )
        (folder / "portal-schema.sql").write_text(sql)
        (folder / "PORTAL_DATABASE.md").write_text(
            "# Portal database schema\n\nGenerated from "
            + str(len(migrations))
            + " pinned PostgreSQL migrations plus source-defined migration tracking, including internal governance. Schema definitions only; no live records or credentials. Production currently applies migration009; migration010 remains prepared. Preserve constraints, immutable approval triggers and migration checksums. Use the migration runner rather than applying this reference as a replacement migration plan.\n\n```sql\n"
            + sql
            + "```\n"
        )
        governance = subprocess.check_output(
            ["git", "show", sha + ":docs/engineering/PRIVACY_GOVERNANCE.md"],
            cwd=repo,
            text=True,
        )
        (folder / "PORTAL_PRIVACY_GOVERNANCE.md").write_text(governance)
        identity = subprocess.check_output(
            ["git", "show", sha + ":docs/engineering/ENGINEERING_DOCS_IDENTITY.md"],
            cwd=repo,
            text=True,
        )
        (folder / "PORTAL_ENGINEERING_DOCS_IDENTITY.md").write_text(identity)
        identity_graphs = re.findall(r"```mermaid\n(.*?)```", identity, re.DOTALL)
        assert len(identity_graphs) == 1
        (root / "docs/diagrams/engineering-docs-identity.mmd").write_text(
            identity_graphs[0].strip() + "\n"
        )
        diagram_names = [
            "privacy-document-review",
            "privacy-retention-lifecycle",
            "privacy-subject-deletion",
            "privacy-processor-assessment",
            "privacy-tailscale-administration",
            "privacy-transfer-review",
            "privacy-notice-publication",
            "privacy-vercel-transition",
        ]
        graphs = re.findall(r"```mermaid\n(.*?)```", governance, re.DOTALL)
        assert len(graphs) == len(diagram_names)
        for identifier, graph in zip(diagram_names, graphs):
            (root / "docs/diagrams" / (identifier + ".mmd")).write_text(
                graph.strip() + "\n"
            )
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
            + "\n\n-- Environment-scoped remote journal; local sessions/safety are not uploaded.\n"
            + "\n".join(remote)
            + "\n"
        )
        (folder / "robot-schema.sql").write_text(sql)
        (folder / "ROBOT_DATABASE.md").write_text(
            "# Robot database schema\n\nGenerated from pinned `robot_api/main.py` local DDL and `robot_api/turso.py` remote staging journal DDL. No live records or credential export. Local sessions and safety state remain process-local with Turso; only bounded task history and the exclusive owner lease persist remotely. Restart starts stopped and cancels unfinished execution. The adapter supports separately verified staging and production bindings; source support does not qualify hosted production durability.\n\n```sql\n"
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
hashes["PORTAL_PRIVACY_GOVERNANCE.md"] = ""
hashes["PORTAL_ENGINEERING_DOCS_IDENTITY.md"] = ""
hashes["PORTAL_DATABASE.md"] = ""
for p in hashes:
    hashes[p] = hashlib.sha256((folder / p).read_bytes()).hexdigest()
(folder / "snapshot-hashes.json").write_text(json.dumps(hashes, indent=2) + "\n")
catpath = root / "docs/diagrams/catalog.json"
cat = json.loads(catpath.read_text())
identity_diagram = {
    "id": "engineering-docs-identity",
    "title": "Engineering Docs sign-in through Onesa Portal",
    "view": "prepared identity and authorization flow",
    "status": "Prepared/default-off; hosted qualification and owner sign-in pending",
    "source": "docs/diagrams/engineering-docs-identity.mmd",
    "url": "/docs/ecosystem/PORTAL_ENGINEERING_DOCS_IDENTITY",
    "nodes": [],
}
cat = [item for item in cat if item["id"] != identity_diagram["id"]]
cat.append(identity_diagram)
privacy_titles = [
    "Privacy document draft, review and approval",
    "Retention lifecycle and activation safeguards",
    "Controlled data subject deletion request",
    "Processor assessment",
    "Tailscale administration and processor boundary",
    "International transfer review",
    "Approved bilingual privacy notice publication",
    "Vercel commercial-plan transition",
]
cat = [item for item in cat if item["id"] not in diagram_names] + [
    {
        "id": identifier,
        "title": title,
        "view": "documented governance workflow",
        "status": "Internal approval workspace; deletion automation and public publication remain separately gated",
        "source": "docs/diagrams/" + identifier + ".mmd",
        "url": "/docs/ecosystem/PORTAL_PRIVACY_GOVERNANCE",
        "nodes": [],
    }
    for identifier, title in zip(diagram_names, privacy_titles)
]
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
