"""Self-authored illustrative geometry and synthetic equipment. No vendor CAD or real readings."""

import json
from typing import Any
from uuid import uuid5

from fastapi import Request
from sqlalchemy import select

from app import knowledge
from app.auth import DB, Auth
from app.models import Document
from app.twin_files import glb, sha
from app.twin_models import TwinAsset, TwinModel, TwinTemplate
from app.twin_schemas import AssetCreate, ModelCreate, TemplateCreate

PARTS = ("casing", "motor", "coupling-shaft", "bearing", "impeller")


def fixture_bytes(name: str) -> bytes:
    from pathlib import Path

    from app.twin_files import sha

    directory = Path(__file__).parent / "twin_fixture_data"
    integrity = json.loads((directory / "integrity.json").read_bytes())
    content = (directory / name).read_bytes()
    if integrity["files"].get(name) != sha(content):
        raise ValueError("Onesa-owned demonstration fixture integrity mismatch")
    return content


MANUAL = fixture_bytes("maintenance.txt").decode("utf-8")


def pump_glb() -> bytes:
    return fixture_bytes("pump.glb")


def pump_aasx() -> bytes:
    return fixture_bytes("pump.aasx")


def aas_environment(*, external: bool = False) -> dict[str, Any]:
    return dict(json.loads(fixture_bytes("external.json" if external else "pump.json")))


def seed(request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    from app.twins import installation, output, quota, save_file, validate_mapping

    owner = auth[0].id
    quota(db, TwinTemplate, owner, 100)
    template_id = uuid5(owner, "onesa-detailed-pump-template-v2")
    existing = db.scalar(
        select(TwinTemplate).where(TwinTemplate.id == template_id, TwinTemplate.user_id == owner)
    )
    if existing:
        return {
            "created": False,
            "assets": [
                output(r)
                for r in db.scalars(
                    select(TwinAsset)
                    .where(TwinAsset.user_id == owner, TwinAsset.template_id == template_id)
                    .order_by(TwinAsset.serial)
                )
            ],
        }
    manifest = json.loads(fixture_bytes("manifest.json"))
    ids = {c["id"]: str(uuid5(template_id, c["id"])) for c in manifest["components"]}
    components = [
        {
            "id": ids[c["id"]],
            "name": c["label"],
            "external_id": c["id"],
            "parent_id": ids.get(c["parentId"]),
            "renderable": c["renderable"],
            "inventory": c["inventory"],
            "inventory_note": c.get("note", ""),
            "material": c.get("material", ""),
            "housing": c.get("housing", False),
        }
        for c in manifest["components"]
    ]
    template_body = TemplateCreate.model_validate(
        {
            "name": "Detailed illustrative pump and TEFC motor",
            "kind": "centrifugal pump",
            "components": components,
            "relationships": [
                {"source": ids["motor"], "target": ids["coupling-shaft"], "kind": "drives"},
                {"source": ids["coupling-shaft"], "target": ids["impeller"], "kind": "drives"},
            ],
        }
    )
    template = TwinTemplate(
        id=template_id,
        user_id=owner,
        name=template_body.name,
        kind=template_body.kind,
        definition=template_body.model_dump(mode="json"),
    )
    db.add(template)
    db.flush()
    binary = pump_glb()
    file = save_file(
        request,
        db,
        auth,
        "onesa-detailed-reference-pump-v2.glb",
        binary,
        {
            **glb(binary),
            "rights": "Self-authored Onesa demonstration geometry",
            "illustrative": True,
        },
    )
    model_body = ModelCreate.model_validate(
        {
            "file_id": str(file.id),
            "template_id": str(template.id),
            "mappings": [
                {"node": m["sceneNode"], "component_id": ids[m["componentId"]]}
                for m in manifest["mappings"]
            ],
            "unit": "m",
            "meters_per_unit": 1,
            "inspection": {
                **manifest["inspection"],
                "motions": [
                    {**m, "component_id": ids[m["component_id"]]}
                    for m in manifest["inspection"]["motions"]
                ],
                "closed_solids": [ids[v] for v in manifest["inspection"]["closed_solids"]],
                "cover_components": [ids[v] for v in manifest["inspection"]["cover_components"]],
                "housing_components": [
                    ids[v] for v in manifest["inspection"]["housing_components"]
                ],
            },
            "provenance": (
                "Self-authored detailed mechanical reference v2. Right-handed Y-up meters; no"
                " collision, calibration or engineering accuracy claim."
            ),
        }
    )
    validate_mapping(model_body, file, template)
    model = TwinModel(
        user_id=owner,
        template_id=template.id,
        file_id=file.id,
        definition={
            **model_body.model_dump(mode="json"),
            "sha256": file.sha256,
            "byte_length": file.size,
            "source_model_revision": manifest["modelRevision"],
            "source_component_mapping": {role: identifier for role, identifier in ids.items()},
            "nodes": file.details["nodes"],
        },
    )
    db.add(model)
    db.flush()
    manual = fixture_bytes("maintenance.txt").decode("utf-8")
    doc = Document(
        user_id=owner,
        title="Onesa illustrative pump maintenance — sections 1–5",
        media_type="text/plain",
        text=manual,
        checksum=sha(manual.encode()),
        embedding_version=knowledge.version(request.app.state.settings),
    )
    db.add(doc)
    db.flush()
    knowledge.index(db, doc, request.app.state.settings)
    rows = []
    for number in (1, 2):
        body = AssetCreate(
            template_id=template.id,
            name=f"Demo pump {number:02}",
            serial=f"ONESA-DEMO-PUMP-{number:02}-V2",
        )
        row = installation(template, body, owner)
        row.active_model_id = model.id
        row.definition = {
            **row.definition,
            "stage": "preview",
            "demo": True,
            "reference_version": "2.1.0",
            "documents": [{"document_id": str(doc.id), "component_id": None}],
        }
        db.add(row)
        rows.append(row)
    db.commit()
    return {
        "created": True,
        "assets": [output(r) for r in rows],
        "notice": (
            "Illustrative geometry. No readings are invented by the browser. "
            "Connect the simulated MQTT fixture to observe condition and "
            "history."
        ),
    }
