"""Generate documentation data from repository sources without contacting live services."""

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from sqlalchemy.dialects import postgresql

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "onesa-ai-platform-backend"))
from app.config import Settings
from app.database import REQUIRED_SCHEMA_REVISION
from app.main import create_app
from app.models import Base

OUTPUT = ROOT / "onesa-ai-platform-frontend/apps/docs/.cache/authoritative"


def write(name, value):
    path = OUTPUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


from source_policy import sources as documentation_sources


def generate():
    from ecosystem import validate as validate_ecosystem

    validate_ecosystem()
    schema = create_app(Settings()).openapi()
    # Public application contracts only; operational/private endpoints are excluded.
    schema["paths"] = {
        p: v for p, v in schema["paths"].items() if p.startswith("/api/v1/")
    }
    schema.pop("servers", None)
    write("openapi.json", schema)
    tables = []
    erd = ["erDiagram"]
    for table in sorted(Base.metadata.tables.values(), key=lambda t: t.name):
        columns = []
        erd.append(f"  {table.name} {{")
        for col in table.columns:
            sql_type = str(col.type.compile(dialect=postgresql.dialect()))
            flags = (
                "PK"
                if col.primary_key
                else "FK"
                if col.foreign_keys
                else "UK"
                if col.unique
                else ""
            )
            erd.append(
                f"    {re.sub(r'[^a-zA-Z0-9_]', '_', sql_type)} {col.name} {flags}".rstrip()
            )
            columns.append(
                {
                    "name": col.name,
                    "type": sql_type,
                    "nullable": col.nullable,
                    "primary_key": col.primary_key,
                    "unique": bool(col.unique),
                    "foreign_keys": [
                        {"target": f.target_fullname, "ondelete": f.ondelete}
                        for f in col.foreign_keys
                    ],
                    "has_orm_default": col.default is not None,
                    "server_default": str(col.server_default.arg)
                    if col.server_default is not None
                    else None,
                }
            )
            for fk in col.foreign_keys:
                erd.append(
                    f'  {fk.column.table.name} ||--o{{ {table.name} : "{col.name}"'
                )
        erd.append("  }")
        tables.append(
            {
                "name": table.name,
                "columns": columns,
                "indexes": [
                    {
                        "name": i.name,
                        "columns": [c.name for c in i.columns],
                        "unique": i.unique,
                    }
                    for i in sorted(table.indexes, key=lambda x: x.name or "")
                ],
                "constraints": sorted(
                    str(c.sqltext)
                    if hasattr(c, "sqltext")
                    else f"{type(c).__name__}: {', '.join(col.name for col in c.columns)}"
                    for c in table.constraints
                ),
            }
        )
    schema_reference = [
        "# Implemented AI PostgreSQL schema",
        "",
        "Generated from current SQLAlchemy PostgreSQL types and the Alembic revision "
        + REQUIRED_SCHEMA_REVISION
        + ". Schema metadata is not live database data. Foreign keys do not replace user ownership checks. ORM defaults and server defaults remain distinct.",
        "",
    ]
    for table in tables:
        schema_reference += [
            "## " + table["name"],
            "",
            "| Field | PostgreSQL type | Nullable | Constraints / relationship |",
            "| --- | --- | --- | --- |",
        ]
        for column in table["columns"]:
            notes = (
                (["primary key"] if column["primary_key"] else [])
                + (["unique"] if column["unique"] else [])
                + (["ORM default"] if column["has_orm_default"] else [])
                + (
                    ["server default: " + column["server_default"]]
                    if column["server_default"]
                    else []
                )
                + [
                    "FK " + f["target"] + " / " + str(f["ondelete"])
                    for f in column["foreign_keys"]
                ]
            )
            schema_reference.append(
                "| "
                + " | ".join(
                    [
                        column["name"],
                        column["type"],
                        str(column["nullable"]),
                        "; ".join(notes),
                    ]
                )
                + " |"
            )
        schema_reference += [
            "",
            "Indexes: " + json.dumps(table["indexes"]),
            "",
            "Constraints: " + json.dumps(table["constraints"]),
            "",
        ]
    (ROOT / "docs/database/SCHEMA.md").write_text(
        "\n".join(schema_reference).rstrip() + "\n"
    )
    # Relationship lines must live outside entity definitions.
    relationships = [line for line in erd if "||--o{" in line]
    erd = [line for line in erd if "||--o{" not in line] + relationships
    (ROOT / "docs/diagrams/database.mmd").write_text("\n".join(erd) + "\n")
    groups = {
        "auth": ["users", "auth_sessions"],
        "chat": ["users", "conversations", "messages"],
        "knowledge": [
            "users",
            "documents",
            "document_chunks",
            "message_sources",
            "messages",
        ],
        "agents": ["users", "agent_runs"],
        "travel": ["users", "trips"],
    }
    catalog_path = ROOT / "docs/diagrams/catalog.json"
    catalog = json.loads(catalog_path.read_text())
    for name, requested in groups.items():
        included = {t["name"] for t in tables if t["name"] in requested}
        lines = ["erDiagram"]
        for t in tables:
            if t["name"] not in included:
                continue
            lines.append("  " + t["name"] + " {")
            for c in t["columns"]:
                flag = (
                    "PK"
                    if c["primary_key"]
                    else "FK"
                    if c["foreign_keys"]
                    else "UK"
                    if c["unique"]
                    else ""
                )
                lines.append(
                    f"    {re.sub(r'[^a-zA-Z0-9_]', '_', c['type'])} {c['name']} {flag}".rstrip()
                )
            lines.append("  }")
        for t in tables:
            if t["name"] in included:
                for c in t["columns"]:
                    for fk in c["foreign_keys"]:
                        parent = fk["target"].split(".")[0]
                        if parent in included:
                            lines.append(
                                f'  {parent} ||--o{{ {t["name"]} : "{c["name"]}"'
                            )
        identifier = "database-" + name
        (ROOT / f"docs/diagrams/{identifier}.mmd").write_text("\n".join(lines) + "\n")
        if not any(d["id"] == identifier for d in catalog):
            catalog.append(
                {
                    "id": identifier,
                    "title": f"{name.title()} data relationships",
                    "view": "implemented schema",
                    "status": "Generated from actual SQLAlchemy tables; migrations integration tested",
                    "source": f"docs/diagrams/{identifier}.mmd",
                    "url": "/database",
                    "nodes": [
                        {
                            "id": t,
                            "label": t,
                            "responsibility": "Implemented table; inspect columns, constraints and migration references in the database explorer.",
                            "url": "/database",
                        }
                        for t in sorted(included)
                    ],
                }
            )
    catalog_path.write_text(json.dumps(catalog, indent=2) + "\n")
    migrations = []
    for path in sorted(
        (ROOT / "onesa-ai-platform-backend/migrations/versions").glob("*.py")
    ):
        tree = ast.parse(path.read_text())
        values = {
            n.targets[0].id: ast.literal_eval(n.value)
            for n in tree.body
            if isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id in ["revision", "down_revision"]
        }
        migrations.append(
            {
                **values,
                "source": str(path.relative_to(ROOT)),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    write(
        "database.json",
        {
            "source": "onesa-ai-platform-backend/app/models.py",
            "model_sha256": hashlib.sha256(
                (ROOT / "onesa-ai-platform-backend/app/models.py").read_bytes()
            ).hexdigest(),
            "tables": tables,
            "migrations": migrations,
            "registry_note": "Training candidate registry is file-based; it is not a PostgreSQL table. active_run_id is a lease marker without a declared FK.",
        },
    )
    search = []
    for doc in documentation_sources(ROOT):
        rel = doc.relative_to(ROOT / "docs").with_suffix("").as_posix()
        raw = doc.read_text()
        title = next(iter(re.findall(r"^# (.+)$", raw, re.MULTILINE)), doc.stem)
        text = re.sub(r"[`#*|>]", "", raw)
        search.append(
            {
                "title": title,
                "url": "/docs" if rel == "README" else "/docs/" + rel,
                "text": text,
            }
        )
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method in ["get", "post", "put", "patch", "delete"]:
                search.append(
                    {
                        "title": method.upper() + " " + path,
                        "url": "/api-explorer",
                        "text": operation.get("summary", "")
                        + " "
                        + json.dumps(operation),
                    }
                )
    write("search.json", search)
    sources = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in documentation_sources(ROOT)
    }
    sources.update(
        {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "docs/diagrams").glob("*.mmd"))
        }
    )
    write(
        "provenance.json",
        {
            "documentation_version": "0.2.0",
            "schema_head": REQUIRED_SCHEMA_REVISION,
            "sources": sources,
            "openapi_sha256": hashlib.sha256(
                json.dumps(schema, sort_keys=True).encode()
            ).hexdigest(),
        },
    )
    split(schema, tables)
    print(
        f"Generated {len(tables)} tables, {len(search)} search entries and public API schema."
    )


def split(schema, tables):
    from app.knowledge import embed, version

    policy = json.loads((ROOT / "docs/documentation-policy.json").read_text())
    catalog = json.loads((ROOT / "docs/diagrams/catalog.json").read_text())
    examples = examples_markdown(schema)
    (ROOT / "docs/public/examples.md").write_text(examples)
    for scope in ["public", "internal"]:
        destination = ROOT / "onesa-ai-platform-frontend/apps/docs/.generated" / scope
        docs = destination / "docs"
        static = destination / "static/generated"
        pages = destination / "pages"
        for directory in [docs, pages]:
            if directory.exists():
                shutil.rmtree(directory)
        for directory in [docs, static, pages]:
            directory.mkdir(parents=True, exist_ok=True)
        # Seed reviewed synthetic images on clean CI checkouts; never copy arbitrary assets.
        artifact_library = ROOT / f"docs/generated/{scope}"
        for folder in ["diagrams", "manuals"]:
            if (artifact_library / folder).exists():
                shutil.copytree(
                    artifact_library / folder, static / folder, dirs_exist_ok=True
                )
        if (artifact_library / "manuals.json").exists():
            shutil.copyfile(artifact_library / "manuals.json", static / "manuals.json")
        screenshots = {}
        image_directory = ROOT / f"docs/generated/{scope}/screenshots"
        for name in policy["public_screenshots"]:
            source = image_directory / f"{name}.png"
            if source.is_file():
                (static / "screenshots").mkdir(exist_ok=True)
                shutil.copyfile(source, static / "screenshots" / source.name)
                screenshots[name] = f"/generated/screenshots/{source.name}"
        (static / "screenshots.json").write_text(
            json.dumps(screenshots, indent=2) + "\n"
        )
        sources = (
            [ROOT / path for path in policy["public_sources"]]
            if scope == "public"
            else [
                p
                for p in documentation_sources(ROOT)
                if not p.is_relative_to(ROOT / "docs/public")
                and p.name
                not in [
                    "ENGINEERING_REFERENCE.md",
                    "AMENDMENT_001.md",
                    "AMENDMENT_002.md",
                    "MILESTONE_2_REQUEST.md",
                ]
            ]
        )
        search = []
        chunks = []
        for source in sources:
            if not source.is_file():
                raise ValueError(f"Missing classified source: {source}")
            relative = source.relative_to(ROOT / "docs")
            output = docs / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            raw = source.read_text()
            included = set(sources)

            def rewrite(match, source=source, included=included):
                label, target = match.groups()
                if target.startswith(("http:", "https:", "#", "/", "mailto:")):
                    return match.group(0)
                target_path, _, anchor = target.partition("#")
                resolved = (source.parent / target_path).resolve()
                if resolved in included:
                    relative_target = (
                        resolved.relative_to(ROOT / "docs").with_suffix("").as_posix()
                    )
                    route = (
                        "/docs"
                        if relative_target == "README"
                        else "/docs/" + relative_target
                    )
                    return f"[{label}]({route}" + (f"#{anchor}" if anchor else "") + ")"
                return label + " (repository reference)"

            raw = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", rewrite, raw)
            output.write_text(raw)
            title = next(iter(re.findall(r"^# (.+)$", raw, re.MULTILINE)), source.stem)
            url = (
                "/docs"
                if relative.as_posix() == "README.md"
                else "/docs/" + relative.with_suffix("").as_posix()
            )
            search.append({"title": title, "url": url, "text": raw})
            for start in range(0, len(raw), 1000):
                text = raw[start : start + 1200]
                if re.search(r"\w", text):
                    chunks.append(
                        {
                            "title": title,
                            "url": url,
                            "source": str(source.relative_to(ROOT)),
                            "classification": scope,
                            "text": text,
                            "embedding": embed([text], Settings())[0],
                        }
                    )
        public_schema = json.loads(json.dumps(schema))
        public_schema["paths"] = {
            p: v
            for p, v in schema["paths"].items()
            if not p.startswith("/api/v1/documentation/")
        }
        references = set()

        def visit(value, references=references, public_schema=public_schema):
            if isinstance(value, dict):
                ref = value.get("$ref", "")
                if ref.startswith("#/components/schemas/"):
                    name = ref.rsplit("/", 1)[-1]
                    if name not in references:
                        references.add(name)
                        visit(public_schema["components"]["schemas"][name])
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(public_schema["paths"])
        public_schema["components"]["schemas"] = {
            key: value
            for key, value in public_schema["components"]["schemas"].items()
            if key in references
        }
        doc_schema = public_schema if scope == "public" else schema
        for path, operations in doc_schema["paths"].items():
            for method, operation in operations.items():
                if method in ["get", "post", "patch", "delete", "put"]:
                    search.append(
                        {
                            "title": method.upper() + " " + path,
                            "url": "/api-explorer",
                            "text": operation.get("summary", "")
                            + " "
                            + json.dumps(operation),
                        }
                    )
        if scope == "internal":
            shutil.copyfile(OUTPUT / "database.json", static / "database.json")
            for table in tables:
                search.append(
                    {
                        "title": "Table: " + table["name"],
                        "url": "/database",
                        "text": json.dumps(table),
                    }
                )
        diagrams = [
            d.copy()
            for d in catalog
            if scope == "internal"
            or scope == "public"
            and d["id"] in policy["public_diagrams"]
        ]
        for d in diagrams:
            d["classification"] = scope
            if scope == "internal" and d["id"].startswith("public-"):
                d["url"] = "https://docs.onesa.eu" + d["url"]
                d["nodes"] = [
                    {**n, "url": "https://docs.onesa.eu" + n["url"]} for n in d["nodes"]
                ]
            source = (ROOT / d["source"]).read_text()
            d["relationships"] = [
                {"from": a, "to": b}
                for a, b in re.findall(
                    r"^\s*(\w+)(?:\[[^\n]+?\])?\s*(?:-->|-\..+?\.->)\s*(\w+)",
                    source,
                    re.MULTILINE,
                )
            ]
            search.append(
                {
                    "title": d["title"],
                    "url": "/architecture",
                    "text": source + " " + d["status"],
                }
            )
        # Product contracts are source snapshots pinned to independently reviewed revisions.
        cross = ROOT / "docs/ecosystem/contracts"
        portal_contract = json.loads((cross / f"portal-{scope}.json").read_text())
        robot_contract = json.loads((cross / "robot.json").read_text())
        for product, contract in [
            ("portal", portal_contract),
            ("robot", robot_contract),
        ]:
            (static / f"openapi-{product}.json").write_text(
                json.dumps(contract, indent=2) + "\n"
            )
        generated = {
            "openapi.json": doc_schema,
            "search.json": search,
            "diagrams.json": diagrams,
            "retrieval.json": {
                "classification": scope,
                "embedding_version": version(Settings()),
                "approved_sources": [str(p.relative_to(ROOT)) for p in sources],
                "chunks": chunks,
            },
            "provenance.json": {
                "version": policy["version"],
                "classification": scope,
                "revision": os.environ.get("GITHUB_SHA")
                or subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                ).strip(),
                "code_sha256": hashlib.sha256(
                    b"".join(
                        p.read_bytes()
                        for p in sorted(
                            (ROOT / "onesa-ai-platform-backend/app").glob("*.py")
                        )
                        + sorted(
                            (
                                ROOT / "onesa-ai-platform-backend/migrations/versions"
                            ).glob("*.py")
                        )
                    )
                ).hexdigest(),
                "sources": {
                    str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sources
                },
            },
        }
        generated["provenance.json"]["snapshot_sources"] = {
            k: v
            for k, v in json.loads(
                (ROOT / "docs/ecosystem/snapshot-hashes.json").read_text()
            ).items()
            if scope == "internal"
            or k in ["contracts/portal-public.json", "contracts/robot.json"]
        }
        for name, data in generated.items():
            (static / name).write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n"
            )
        common = [
            "architecture",
            "api-explorer",
            "downloads",
            "assistant",
            "checklists",
            "feedback",
            "gallery",
        ]
        mapping = {name: name for name in common}
        mapping.update(
            {
                "index": "public-home" if scope == "public" else "index",
                "tutorials": "public-tutorials" if scope == "public" else "tutorials",
            }
        )
        if scope == "internal":
            mapping["database"] = "database"
        for path, component in mapping.items():
            (pages / f"{path}.tsx").write_text(
                f'export {{default}} from "@site/src/pages/{component}";\n'
            )


def examples_markdown(schema):
    samples = [
        ("get", "/api/v1/models", None),
        ("post", "/api/v1/conversations", {"title": "Integration example"}),
        (
            "post",
            "/api/v1/chat/completions",
            {
                "conversation_id": "00000000-0000-4000-8000-000000000001",
                "content": "Hello Onesa",
                "stream": False,
            },
        ),
        (
            "post",
            "/api/v1/knowledge/search",
            {"query": "inspection interval", "document_ids": [], "limit": 5},
        ),
        (
            "post",
            "/api/v1/agents/runs",
            {"goal": "Count words in hello platform", "allowed_tools": ["text_stats"]},
        ),
        (
            "post",
            "/api/v1/travel/trips",
            {"destination": "Berlin", "duration": 2, "budget": 250, "currency": "EUR"},
        ),
    ]
    sections = [
        "# Validated API integration examples",
        "Examples derive methods, paths and request bodies from the current OpenAPI. Use an authorized development Origin, a session issued by login and its CSRF cookie. Placeholder IDs must be replaced with owned resource IDs. No SDK is introduced before API stability.",
        "## Authentication",
        "Python requests.Session or a browser same-origin fetch can retain issued cookies. Supply your development email/password via local environment variables; never paste real credentials into documentation. POST /api/v1/auth/login uses email and password; protected mutations require X-CSRF-Token.",
        '```python\nimport os, requests\nbase = os.environ["ONESA_APPLICATION_URL"]\nsession = requests.Session()\nsession.headers["Origin"] = base\nr = session.post(base + "/api/v1/auth/login", json={"email": os.environ["ONESA_DEV_EMAIL"], "password": os.environ["ONESA_DEV_PASSWORD"]})\nr.raise_for_status()\nsession.headers["X-CSRF-Token"] = session.cookies["onesa_csrf"]\n```',
    ]
    for method, path, body in samples:
        operation = schema["paths"][path][method]
        if body:
            request_schema = operation["requestBody"]["content"]["application/json"][
                "schema"
            ]
            if "$ref" in request_schema:
                request_schema = schema["components"]["schemas"][
                    request_schema["$ref"].split("/")[-1]
                ]
            from app.agents import RunRequest
            from app.knowledge import Search
            from app.schemas import ChatRequest, ConversationCreate
            from app.travel import Preferences

            request_models = {
                "/api/v1/conversations": ConversationCreate,
                "/api/v1/chat/completions": ChatRequest,
                "/api/v1/knowledge/search": Search,
                "/api/v1/agents/runs": RunRequest,
                "/api/v1/travel/trips": Preferences,
            }
            request_models[path].model_validate(body)
            assert set(request_schema.get("required", [])) <= set(body)
            assert set(body) <= set(request_schema.get("properties", {}))
        payload = json.dumps(body) if body else ""
        py = (
            f'r = session.{method}(base + "{path}"'
            + (f", json={body!r}" if body else "")
            + ")\nr.raise_for_status()\nprint(r.json())"
        )
        ts = (
            f'const response = await fetch("{path}", {{method: "{method.upper()}", credentials: "same-origin", headers: {{"Content-Type": "application/json", "X-CSRF-Token": csrfFromSessionCookie}}'
            + (f", body: JSON.stringify({payload})" if body else "")
            + "});\nif (!response.ok) throw new Error(`HTTP ${response.status}`);\nconst result = await response.json();"
        )
        curl = (
            f'curl --request {method.upper()} "$ONESA_APPLICATION_URL{path}" --cookie "$ONESA_COOKIE_JAR" --header "Origin: $ONESA_APPLICATION_URL" --header "X-CSRF-Token: $ONESA_CSRF"'
            + (
                f" --header 'Content-Type: application/json' --data '{payload}'"
                if body
                else ""
            )
        )
        sections += [
            f"## {method.upper()} {path}",
            "### Python",
            "```python\n" + py + "\n```",
            "### TypeScript",
            "```typescript\n" + ts + "\n```",
            "### cURL",
            "```bash\n" + curl + "\n```",
        ]
    sections += [
        "## Streaming",
        "Set stream=true and use session.post(..., stream=True). Parse event/data frames using iter_lines(), accumulate content_delta, and require message_end. In TypeScript use Response.body.getReader(), TextDecoder with stream=true, and buffer complete SSE frames across chunks. AbortController cancels the request. Never treat a transport chunk as an entire event. See [streaming contract](streaming.md).",
    ]
    sections += [
        "### Runnable Python stream",
        "Use the authenticated session from the previous example and replace conversation_id with your owned conversation. The context manager closes the stream on error or cancellation.",
        "```python\nimport json\nfinished = False\nwith session.post(base + '/api/v1/chat/completions', json={'conversation_id': conversation_id, 'content': 'Hello', 'stream': True}, stream=True) as response:\n    response.raise_for_status()\n    kind = ''\n    for line in response.iter_lines(decode_unicode=True):\n        if line.startswith('event: '):\n            kind = line[7:]\n        elif line.startswith('data: '):\n            data = json.loads(line[6:])\n            if kind == 'content_delta':\n                print(data['text'], end='', flush=True)\n            elif kind == 'error':\n                raise RuntimeError('Generation failed; inspect the controlled error code')\n            elif kind == 'message_end':\n                finished = True\n    if not finished:\n        raise RuntimeError('Incomplete stream')\n```",
        "### Runnable browser TypeScript stream",
        "Run on the application origin with an authenticated session. Pass your owned conversationId and the session CSRF value. AbortController.signal closes the request when the caller cancels.",
        "```typescript\nasync function streamChat(conversationId: string, csrf: string, signal: AbortSignal) {\n  const response = await fetch('/api/v1/chat/completions', {method:'POST', credentials:'same-origin', signal, headers:{'Content-Type':'application/json','X-CSRF-Token':csrf}, body:JSON.stringify({conversation_id:conversationId,content:'Hello',stream:true})});\n  if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);\n  const reader=response.body.getReader(); const decoder=new TextDecoder();\n  let buffer='', finished=false;\n  try {\n    while (true) {\n      const {value,done}=await reader.read();\n      buffer += decoder.decode(value,{stream:!done});\n      let boundary: number;\n      while ((boundary=buffer.indexOf('\\n\\n')) >= 0) {\n        const frame=buffer.slice(0,boundary); buffer=buffer.slice(boundary+2);\n        const lines=frame.split('\\n');\n        const kind=lines.find(line=>line.startsWith('event: '))?.slice(7);\n        const payload=lines.filter(line=>line.startsWith('data: ')).map(line=>line.slice(6)).join('\\n');\n        if (!payload) continue;\n        const data=JSON.parse(payload);\n        if (kind==='content_delta') console.log(data.text);\n        if (kind==='error') throw new Error('Generation failed');\n        if (kind==='message_end') finished=true;\n      }\n      if (done) break;\n    }\n    if (!finished) throw new Error('Incomplete stream');\n  } finally { await reader.cancel(); reader.releaseLock(); }\n}\n```",
        "### cURL stream",
        '```bash\ncurl --no-buffer "$ONESA_APPLICATION_URL/api/v1/chat/completions" --cookie "$ONESA_COOKIE_JAR" --header "Origin: $ONESA_APPLICATION_URL" --header "X-CSRF-Token: $ONESA_CSRF" --header \'Content-Type: application/json\' --data \'{"conversation_id":"00000000-0000-4000-8000-000000000001","content":"Hello","stream":true}\'\n```',
    ]
    return "\n\n".join(sections) + "\n"


if __name__ == "__main__":
    generate()
