"""Self-authored illustrative geometry and synthetic equipment. No vendor CAD or real readings."""

import io
import json
import math
import struct
from typing import Any

from basyx.aas.adapter import aasx
from basyx.aas.adapter import json as aas_json

PARTS = ("casing", "motor", "coupling-shaft", "bearing", "impeller")
MANUAL = """Onesa illustrative pump maintenance procedure — revision 2
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

Section 4 — Detailed illustrative assembly inspection
This app-owned reference is an engineering-informed end-suction pump coupled to a
TEFC squirrel-cage motor. It has no manufacturer identity, certified dimensions,
validated maintenance sequence or calibrated physics. Explosion is a visualization.
Select the pump, bearing or motor subassembly and use Explosion 0–100% to separate
modeled parts. Reassemble restores the immutable assembled transforms. Guide lines
are optional. Focus a bearing race, rolling-element set, cage, mechanical-seal ring,
impeller, stator, copper winding assembly, rotor cage or fan to inspect its geometry.
Section X crosses the shaft; Y and Z expose longitudinal internals. Reverse the cut
and move the plane to inspect both sides. Solid cut faces apply only to validated
closed surfaces; fluid cavities, shaft bores, bearing gaps and vents remain empty.
The open-ended seal spring has no cut cap. Transparent housings have no solid cap;
hide covers or isolate a part for an unobstructed view. Restore all returns every part.

Section 5 — Reference BOM and provenance
The assembly/BOM lists logical assemblies and separately selectable modeled parts.
Rolling elements are selectable as one bearing set; winding conductor bundles,
rotor lamination packs and fastener head/washer/shank assemblies are intentionally
combined. Exact wire strands, thread helices and individual steel sheets are
simplified, as stated in each component inventory note. Terminal electrical
internals, wiring and hydraulic CFD are outside this mechanical reference scope.
The parametric authoring source and topology audit are retained in this repository.
No supplier CAD, third-party asset release or external viewer is required.
"""


def basic_pump_glb() -> bytes:
    """Five individually selectable low-poly parts; generation is deterministic."""
    binary = bytearray()
    views: list[dict[str, Any]] = []
    accessors: list[dict[str, Any]] = []
    meshes: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    materials = []
    shapes = [
        (-0.65, 0.5, 0.47, 0.45),
        (0.75, 0.48, 0.38, 0.85),
        (0.05, 0.5, 0.09, 0.65),
        (-0.1, 0.5, 0.21, 0.14),
        (-0.66, 0.5, 0.32, 0.1),
    ]
    colors = [
        [0.20, 0.34, 0.58, 1],
        [0.23, 0.28, 0.36, 1],
        [0.63, 0.67, 0.73, 1],
        [0.84, 0.54, 0.18, 1],
        [0.27, 0.66, 0.64, 1],
    ]

    def accessor(values: list[float], width: int, kind: str) -> int:
        offset = len(binary)
        binary.extend(struct.pack("<" + "f" * len(values), *values))
        views.append(
            {"buffer": 0, "byteOffset": offset, "byteLength": len(binary) - offset}
        )
        row: dict[str, Any] = {
            "bufferView": len(views) - 1,
            "componentType": 5126,
            "count": len(values) // width,
            "type": kind,
        }
        row.update(
            min=[min(values[i::width]) for i in range(width)],
            max=[max(values[i::width]) for i in range(width)],
        )
        accessors.append(row)
        return len(accessors) - 1

    for index, (name, shape, color) in enumerate(
        zip(PARTS, shapes, colors, strict=True)
    ):
        x, y, radius, length = shape
        positions: list[float] = []
        normals: list[float] = []
        # Cylinders point along X. Flat caps and radial side normals retain useful lighting.
        for step in range(24):
            a, b = step * math.tau / 24, (step + 1) * math.tau / 24
            ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
            lo, hi = x - length / 2, x + length / 2
            for points, normal in [
                (
                    [
                        (lo, y, 0),
                        (lo, y + radius * cb, radius * sb),
                        (lo, y + radius * ca, radius * sa),
                    ],
                    (-1, 0, 0),
                ),
                (
                    [
                        (hi, y, 0),
                        (hi, y + radius * ca, radius * sa),
                        (hi, y + radius * cb, radius * sb),
                    ],
                    (1, 0, 0),
                ),
            ]:
                for point in points:
                    positions.extend(point)
                    normals.extend(normal)
            for px, py, pz, ny, nz in [
                (lo, y + radius * ca, radius * sa, ca, sa),
                (lo, y + radius * cb, radius * sb, cb, sb),
                (hi, y + radius * ca, radius * sa, ca, sa),
                (hi, y + radius * ca, radius * sa, ca, sa),
                (lo, y + radius * cb, radius * sb, cb, sb),
                (hi, y + radius * cb, radius * sb, cb, sb),
            ]:
                positions.extend((px, py, pz))
                normals.extend((0, ny, nz))
        pos = accessor(positions, 3, "VEC3")
        normal_index = accessor(normals, 3, "VEC3")
        materials.append(
            {
                "name": name,
                "pbrMetallicRoughness": {
                    "baseColorFactor": color,
                    "metallicFactor": 0.45,
                    "roughnessFactor": 0.4,
                },
                "doubleSided": True,
            }
        )
        meshes.append(
            {
                "name": name,
                "primitives": [
                    {
                        "attributes": {"POSITION": pos, "NORMAL": normal_index},
                        "material": index,
                    }
                ],
            }
        )
        nodes.append(
            {
                "name": name.replace("-", " ").title(),
                "mesh": index,
                "extras": {"twin_component": name},
            }
        )
    model = {
        "asset": {
            "version": "2.0",
            "generator": (
                "Onesa self-authored illustrative pump v1; meters; no engineering accuracy claim"
            ),
        },
        "scene": 0,
        "scenes": [{"nodes": list(range(5))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": views,
        "accessors": accessors,
    }
    raw = json.dumps(model, sort_keys=True, separators=(",", ":")).encode()
    raw += b" " * (-len(raw) % 4)
    binary.extend(b"\0" * (-len(binary) % 4))
    return (
        struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(raw) + 8 + len(binary))
        + struct.pack("<II", len(raw), 0x4E4F534A)
        + raw
        + struct.pack("<II", len(binary), 0x004E4942)
        + binary
    )


_REFERENCE: tuple[bytes, dict[str, Any], bytes] | None = None


def reference() -> tuple[bytes, dict[str, Any], bytes]:
    """Reproduce local viewing geometry with this app's locked authoring dependency."""
    global _REFERENCE
    if _REFERENCE is None:
        import subprocess
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory(
            prefix="onesa-reference-authoring-"
        ) as directory:
            subprocess.run(
                [
                    "node",
                    str(Path(__file__).with_name("author_reference.mjs")),
                    directory,
                ],
                check=True,
                capture_output=True,
            )
            target = Path(directory)
            _REFERENCE = (
                (target / "pump.glb").read_bytes(),
                json.loads((target / "assembly.json").read_bytes()),
                (target / "topology-audit.json").read_bytes(),
            )
    return _REFERENCE


def pump_glb() -> bytes:
    return reference()[0]


def aas_environment(*, external: bool = False) -> dict[str, Any]:
    return {
        "assetAdministrationShells": [
            {
                "modelType": "AssetAdministrationShell",
                "id": "urn:onesa:demo:pump:aas:1",
                "idShort": "IllustrativePump",
                "assetInformation": {
                    "assetKind": "Instance",
                    "globalAssetId": "urn:onesa:demo:pump:1",
                },
                "submodels": [
                    {
                        "type": "ModelReference",
                        "keys": [
                            {
                                "type": "Submodel",
                                "value": "urn:onesa:demo:pump:models:1",
                            }
                        ],
                    }
                ],
            }
        ],
        "submodels": [
            {
                "modelType": "Submodel",
                "id": "urn:onesa:demo:pump:models:1",
                "idShort": "Models3D",
                "semanticId": {
                    "type": "ExternalReference",
                    "keys": [
                        {
                            "type": "GlobalReference",
                            "value": "https://admin-shell.io/idta/Models3D/1/0",
                        }
                    ],
                },
                "submodelElements": [
                    {
                        "modelType": "File",
                        "idShort": "IllustrativeModel",
                        "contentType": "model/gltf-binary",
                        "value": "https://example.invalid/pump.glb"
                        if external
                        else "/aasx/files/pump.glb",
                    },
                    {
                        "modelType": "File",
                        "idShort": "MaintenanceProcedure",
                        "contentType": "text/plain",
                        "value": "/aasx/files/maintenance.txt",
                    },
                    {
                        "modelType": "Property",
                        "idShort": "GeometryPurpose",
                        "valueType": "xs:string",
                        "value": "Illustrative visualization only",
                    },
                    {
                        "modelType": "MultiLanguageProperty",
                        "idShort": "PreservedUnknownProjection",
                        "value": [
                            {
                                "language": "en",
                                "text": "Preserved in original package and source environment",
                            }
                        ],
                    },
                ],
            }
        ],
        "conceptDescriptions": [],
    }


def pump_aasx() -> bytes:
    raw = json.dumps(aas_environment())
    objects = aas_json.read_aas_json_file(io.StringIO(raw), failsafe=False)
    files = aasx.DictSupplementaryFileContainer()  # type: ignore[no-untyped-call]
    files.add_file("/aasx/files/pump.glb", io.BytesIO(pump_glb()), "model/gltf-binary")
    files.add_file(
        "/aasx/files/maintenance.txt", io.BytesIO(MANUAL.encode()), "text/plain"
    )
    target = io.BytesIO()
    with aasx.AASXWriter(target) as writer:
        writer.write_aas("urn:onesa:demo:pump:aas:1", objects, files, write_json=True)
    return target.getvalue()


def generate() -> None:
    import hashlib
    import zipfile
    from pathlib import Path

    target = (
        Path(__file__).resolve().parents[2]
        / "onesa-ai-platform-backend/app/twin_fixture_data"
    )
    target.mkdir(exist_ok=True)
    raw_package = pump_aasx()
    deterministic = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(raw_package)) as source,
        zipfile.ZipFile(
            deterministic, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as output,
    ):
        for name in sorted(source.namelist()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, source.read(name))
    model, assembly, audit = reference()
    files = {
        "assembly.json": (
            json.dumps(assembly, sort_keys=True, indent=2) + "\n"
        ).encode(),
        "topology-audit.json": audit,
        "pump.glb": model,
        "pump.aasx": deterministic.getvalue(),
        "pump.json": (
            json.dumps(aas_environment(), sort_keys=True, indent=2) + "\n"
        ).encode(),
        "external.json": (
            json.dumps(aas_environment(external=True), sort_keys=True, indent=2) + "\n"
        ).encode(),
        "maintenance.txt": MANUAL.encode(),
    }
    manifest = {
        "schemaVersion": "1.0.0",
        "modelRevision": "onesa-end-suction-pump-tefc-motor:2.0.0",
        "artifact": {
            "sha256": hashlib.sha256(model).hexdigest(),
            "byteLength": len(model),
            "mediaType": "model/gltf-binary",
        },
        "provenance": {
            "description": "Onesa-authored detailed mechanical reference with modeled internals; illustrative, not calibrated CAD or planning geometry",
            "rights": "Onesa-owned synthetic demonstration; Onesa-owned illustrative demonstration asset",
            "illustrative": True,
        },
        "unit": "m",
        "metersPerUnit": 1,
        "coordinateFrame": "right-handed-y-up",
        "transform": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
        "components": assembly["components"],
        "mappings": [
            {
                "sceneNode": f"node:{index}",
                "componentId": node["extras"]["twin_component"],
            }
            for index, node in enumerate(
                json.loads(model[20 : 20 + struct.unpack_from("<I", model, 12)[0]])[
                    "nodes"
                ]
            )
            if "mesh" in node
        ],
        "inspection": {
            **{
                k: assembly["inspection"][k]
                for k in ("version", "reference", "description", "unavailable")
            },
            "motions": [
                {
                    **{k: motion[k] for k in ("translation", "rotation", "pivot")},
                    "component_id": motion["componentId"],
                }
                for motion in assembly["inspection"]["motions"]
            ],
            "closed_solids": assembly["inspection"]["closedSolids"],
            "housing_components": assembly["inspection"]["housingComponents"],
            "cover_components": assembly["inspection"]["coverComponents"],
            "scope_notes": assembly["inspection"]["scopeNotes"],
        },
    }
    files["manifest.json"] = (
        json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    ).encode()
    files["scenarios.json"] = (
        json.dumps(
            {
                "schemaVersion": "1.0.0",
                "mode": "simulated",
                "scenario": "pump-bearing-vibration-v1",
                "metric": "vibration",
                "unit": "mm/s",
                "high": 5,
                "hysteresis": 1,
                "observations": [
                    {"offsetSeconds": 0, "value": 2, "expected": "normal"},
                    {"offsetSeconds": 1, "value": 6, "expected": "rule_alarm"},
                    {"offsetSeconds": 2, "value": 4.5, "expected": "rule_alarm"},
                    {"offsetSeconds": 3, "value": 3, "expected": "normal"},
                ],
                "afterSecondsWithoutObservation": 15,
                "expectedAfterDisconnect": "stale",
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode()
    for name, content in files.items():
        (target / name).write_bytes(content)
    (target / "integrity.json").write_text(
        json.dumps(
            {
                "fixtureVersion": "2.0.0",
                "source": "scripts/twins/generate_fixtures.py",
                "files": {
                    name: hashlib.sha256(content).hexdigest()
                    for name, content in sorted(files.items())
                },
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    generate()
