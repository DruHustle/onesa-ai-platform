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
MANUAL = """Onesa illustrative pump maintenance procedure — revision 1
Self-authored synthetic demonstration; not an equipment manufacturer's instruction.

Section 1 — Identification
Confirm the installed pump serial number and selected component before inspection.
Geometry is illustrative, right-handed Y-up, in meters. It is not calibrated CAD.

Section 2 — Bearing vibration inspection
A vibration threshold is a rule output, not a confirmed fault or prediction.
Review the bearing observation timestamp, quality and operating mode. A stale or bad
reading cannot establish current condition. Compare the event with bounded history.
Inspect the bearing mounting and coupling alignment only under the equipment owner's
approved isolation and safe maintenance procedure. This workspace issues no commands.

Section 3 — Recovery
Review the hysteresis recovery event and subsequent good-quality readings. A recovery
event alone does not prove mechanical repair. Record the evidence and inspection outcome.
"""


def fixture_bytes(name: str) -> bytes:
    from pathlib import Path

    from app.twin_files import sha

    directory = Path(__file__).parent / "twin_fixture_data"
    integrity = json.loads((directory / "integrity.json").read_bytes())
    content = (directory / name).read_bytes()
    if integrity["files"].get(name) != sha(content):
        raise ValueError("Onesa-owned demonstration fixture integrity mismatch")
    return content


def pump_glb() -> bytes:
    return fixture_bytes("pump.glb")


def pump_aasx() -> bytes:
    return fixture_bytes("pump.aasx")


def aas_environment(*, external: bool = False) -> dict[str, Any]:
    return dict(json.loads(fixture_bytes("external.json" if external else "pump.json")))


def seed(request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    from app.twins import installation, output, quota, save_file

    owner = auth[0].id
    quota(db, TwinTemplate, owner, 100)
    template_id = uuid5(owner, "onesa-illustrative-pump-template-v1")
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
    components = [
        {
            "id": str(uuid5(template_id, name)),
            "name": name.replace("-", " ").title(),
            "external_id": name,
        }
        for name in PARTS
    ]
    template_body = TemplateCreate.model_validate(
        {
            "name": "Illustrative pump and motor",
            "kind": "centrifugal pump",
            "components": components,
            "relationships": [
                {"source": components[1]["id"], "target": components[2]["id"], "kind": "drives"},
                {"source": components[2]["id"], "target": components[4]["id"], "kind": "drives"},
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
        "onesa-illustrative-pump-v1.glb",
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
                {"node": f"node:{i}", "component_id": c["id"]} for i, c in enumerate(components)
            ],
            "unit": "m",
            "meters_per_unit": 1,
            "provenance": (
                "Self-authored illustrative pump v1. Right-handed Y-up meters; no"
                " collision, calibration or engineering accuracy claim."
            ),
        }
    )
    model = TwinModel(
        user_id=owner,
        template_id=template.id,
        file_id=file.id,
        definition={
            **model_body.model_dump(mode="json"),
            "sha256": file.sha256,
            "byte_length": file.size,
            "source_model_revision": "onesa-illustrative-pump:1.0.0",
            "source_component_mapping": {
                role: str(component["id"])
                for role, component in zip(PARTS, components, strict=True)
            },
            "nodes": file.details["nodes"],
        },
    )
    db.add(model)
    db.flush()
    doc = Document(
        user_id=owner,
        title="Onesa illustrative pump maintenance — sections 1–3",
        media_type="text/plain",
        text=MANUAL,
        checksum=sha(MANUAL.encode()),
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
            serial=f"ONESA-DEMO-PUMP-{number:02}",
        )
        row = installation(template, body, owner)
        row.active_model_id = model.id
        row.definition = {
            **row.definition,
            "stage": "preview",
            "demo": True,
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
