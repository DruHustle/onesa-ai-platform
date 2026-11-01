"""Pinned NVIDIA visual references; importing geometry creates no telemetry or connections."""

import copy
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid5

from fastapi import Request
from sqlalchemy import select

from app.auth import DB, Auth, eligible, lock_account
from app.errors import fail
from app.twin_files import MAX_FILE, bounded_json, glb, sha
from app.twin_models import TwinAsset, TwinFile, TwinModel, TwinTemplate
from app.twin_schemas import AssetCreate, ModelCreate, TemplateCreate

ROOT = Path(__file__).parent / "twin_reference_data"
MANIFEST_SHA256 = "f6049c874e1e3f9b5860ca1bf6d5bad22b5176f7282c868253225d80bff94704"
SOURCE_REVISION = "4763fbfaa4f8e97658e68b57d01b4c86659e08b5"
IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


def read_artifact(entry: dict[str, Any], kind: str) -> bytes:
    artifact = entry[kind]
    relative = artifact["path"]
    if (
        not isinstance(relative, str)
        or not re.fullmatch(r"nvidia-[a-z-]+/[A-Za-z][A-Za-z0-9_.-]+", relative)
        or relative.split("/")[0] != entry["id"]
    ):
        raise ValueError("Invalid reference artifact path")
    path = ROOT / relative
    if ROOT.is_symlink() or path.parent.is_symlink() or path.is_symlink():
        raise ValueError("Reference artifacts must be local regular files")
    with path.open("rb") as source:
        data = source.read(MAX_FILE + 1)
    if (
        not 0 < len(data) <= MAX_FILE
        or len(data) != artifact["byteLength"]
        or sha(data) != artifact["sha256"]
    ):
        raise ValueError("Reference artifact integrity mismatch")
    return data


def manifest() -> dict[str, Any]:
    data = (ROOT / "manifest.json").read_bytes()
    if len(data) > 65536 or sha(data) != MANIFEST_SHA256:
        raise ValueError("Reference catalog integrity mismatch")
    result: dict[str, Any] = bounded_json(data)
    entries = result["assets"]
    if result["schemaVersion"] != 1 or not 1 <= len(entries) <= 12:
        raise ValueError("Unsupported reference catalog")
    if len({entry["id"] for entry in entries}) != len(entries):
        raise ValueError("Duplicate reference identity")
    for entry in entries:
        if (
            entry["sourceRevision"] != SOURCE_REVISION
            or entry["license"] != "CC-BY-4.0"
            or entry["author"] != "NVIDIA"
            or entry["visualOnly"] is not True
            or entry["unit"] != "m"
            or entry["upAxis"] != "Y"
            or entry["sourceUrl"]
            != f"https://huggingface.co/datasets/nvidia/simready-assets/tree/{SOURCE_REVISION}/"
            + entry["sourceAssetId"]
        ):
            raise ValueError("Unsupported reference provenance")
    return result


@lru_cache(maxsize=3)
def geometry(data: bytes) -> dict[str, Any]:
    # The cache key is the verified bytes, not a filename or mutable timestamp.
    return glb(data)


def validated(entry: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    binary = read_artifact(entry, "glb")
    for kind in ("thumbnail", "licenseFile", "sourceFile"):
        read_artifact(entry, kind)
    details = copy.deepcopy(geometry(binary))
    if details["triangles"] != entry["triangles"]:
        raise ValueError("Reference geometry statistics mismatch")
    return binary, details


def projection(entry: dict[str, Any], details: dict[str, Any]) -> dict[str, Any]:
    return {
        **entry,
        "preview_model": {
            "id": entry["id"] + ":" + entry["glb"]["sha256"][:16],
            "file_id": "reference-preview",
            "template_id": "reference-preview",
            "definition": {
                "nodes": details["nodes"],
                "mappings": [],
                "unit": "m",
                "meters_per_unit": 1,
                "frame": "right-handed-y-up",
                "transform": IDENTITY,
                "provenance": entry["attribution"] + " Visual reference geometry only.",
                "sha256": entry["glb"]["sha256"],
                "byte_length": entry["glb"]["byteLength"],
                "rights": entry["license"],
                "illustrative": True,
            },
        },
    }


def catalog() -> dict[str, Any]:
    result = manifest()
    return {
        "version": 1,
        "assets": [projection(entry, validated(entry)[1]) for entry in result["assets"]],
        "limitations": result["limitations"],
    }


def import_reference(reference_id: str, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    from app.twins import installation, output, quota, save_file, validate_mapping

    entry = next((item for item in manifest()["assets"] if item["id"] == reference_id), None)
    if entry is None:
        fail(404, "twin_reference_not_found", "Reference model not found")
    binary, details = validated(entry)
    user = lock_account(db, auth)
    eligible(request, db, user)
    owner = user.id
    identity = f"nvidia:{reference_id}:{entry['sourceRevision']}:{entry['glb']['sha256']}"
    asset_id = uuid5(owner, identity + ":asset")
    existing = db.scalar(
        select(TwinAsset).where(TwinAsset.id == asset_id, TwinAsset.user_id == owner)
    )
    if existing is not None:
        return {"created": False, "asset": output(existing)}

    # Reserve all database quotas before touching private durable storage. Account
    # locking serializes concurrent retries, including a lost first response.
    for cls, maximum in ((TwinTemplate, 100), (TwinAsset, 100), (TwinModel, 200), (TwinFile, 200)):
        quota(db, cls, owner, maximum)
    serial = f"REFERENCE-{reference_id}-{entry['glb']['sha256'][:12]}"
    if db.scalar(
        select(TwinAsset.id).where(TwinAsset.user_id == owner, TwinAsset.serial == serial)
    ):
        fail(409, "duplicate_serial", "An installation already uses this reference serial")
    template_id = uuid5(owner, identity + ":template")
    ids = {node["ref"]: str(uuid5(template_id, node["ref"])) for node in details["nodes"]}
    body = TemplateCreate.model_validate(
        {
            "name": "NVIDIA " + entry["name"],
            "kind": entry["kind"],
            "components": [
                {
                    "id": ids[node["ref"]],
                    "name": node["name"] or entry["name"],
                    "external_id": node["ref"],
                    "inventory": "combined",
                    "inventory_note": "Visual mesh grouping; not an engineering bill of materials.",
                }
                for node in details["nodes"]
            ],
        }
    )
    template = TwinTemplate(
        id=template_id,
        user_id=owner,
        name=body.name,
        kind=body.kind,
        definition=body.model_dump(mode="json"),
    )
    db.add(template)
    db.flush()
    file = save_file(
        request,
        db,
        auth,
        reference_id + ".glb",
        binary,
        {**details, "rights": entry["license"], "illustrative": True, "reference": entry},
    )
    model_body = ModelCreate.model_validate(
        {
            "file_id": str(file.id),
            "template_id": str(template.id),
            "mappings": [
                {"node": node["ref"], "component_id": ids[node["ref"]]} for node in details["nodes"]
            ],
            "unit": "m",
            "meters_per_unit": 1,
            "provenance": entry["attribution"] + " Visual reference geometry only.",
        }
    )
    validate_mapping(model_body, file, template)
    model = TwinModel(
        id=uuid5(owner, identity + ":model"),
        user_id=owner,
        template_id=template.id,
        file_id=file.id,
        definition={
            **model_body.model_dump(mode="json"),
            "sha256": file.sha256,
            "byte_length": file.size,
            "nodes": details["nodes"],
            "rights": entry["license"],
            "illustrative": True,
            "reference": entry,
        },
    )
    db.add(model)
    db.flush()
    row = installation(
        template,
        AssetCreate(template_id=template.id, name="NVIDIA " + entry["name"], serial=serial),
        owner,
    )
    row.id = asset_id
    row.active_model_id = model.id
    row.definition = {
        **row.definition,
        "stage": "preview",
        "reference": entry,
        "visual_only": True,
    }
    db.add(row)
    db.commit()
    return {"created": True, "asset": output(row)}
