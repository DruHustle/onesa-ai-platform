"""Bounded no-network model/package parsing and private durable development storage."""

import hashlib
import io
import json
import math
import os
import re
import shutil
import stat
import struct
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID

from basyx.aas.adapter import aasx
from basyx.aas.adapter import json as aas_json
from basyx.aas.model import DictIdentifiableStore
from defusedxml import ElementTree

MAX_FILE = 4 * 1024 * 1024
MAX_EXPANDED = 20 * 1024 * 1024


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FileStore:
    """Configured mount only; never silently falls back to a temporary directory."""

    def __init__(self, directory: str):
        self.root = Path(directory) if directory else None

    def ready(self) -> bool:
        root = self.root
        if root is None or not root.is_absolute() or root.is_symlink():
            return False
        try:
            mode = root.stat().st_mode
            return stat.S_ISDIR(mode) and not mode & 0o077 and os.access(root, os.R_OK | os.W_OK)
        except OSError:
            return False

    def path(self, owner: UUID, checksum: str) -> Path:
        if not self.ready() or not re.fullmatch("[a-f0-9]{64}", checksum):
            raise ValueError("Private durable storage is not configured or ready")
        assert self.root is not None
        folder = self.root / str(owner)
        if folder.is_symlink():
            raise ValueError("Invalid private storage directory")
        folder.mkdir(mode=0o700, exist_ok=True)
        return folder / checksum

    def put(self, owner: UUID, data: bytes) -> str:
        if not 0 < len(data) <= MAX_FILE:
            raise ValueError("File limit is 4 MiB")
        checksum = sha(data)
        path = self.path(owner, checksum)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            if self.read(owner, checksum) != data:
                raise ValueError("Stored content identity mismatch") from None
        else:
            with os.fdopen(descriptor, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        return checksum

    def read(self, owner: UUID, checksum: str) -> bytes:
        path = self.path(owner, checksum)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise ValueError("Invalid stored object")
            data = source.read(MAX_FILE + 1)
        if len(data) > MAX_FILE or sha(data) != checksum:
            raise ValueError("Stored content identity mismatch")
        return data

    def remove_owner(self, owner: UUID) -> None:
        if not self.ready():
            raise ValueError("Private durable storage is unavailable")
        assert self.root is not None
        folder = self.root / str(owner)
        if folder.is_symlink():
            raise ValueError("Invalid private storage directory")
        if folder.exists():
            shutil.rmtree(folder)


def bounded_json(data: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON keys")
            result[key] = value
        return result

    try:
        value = json.loads(data, object_pairs_hook=pairs, parse_constant=lambda _: invalid_number())
        pending = [(value, 0)]
        count = 0
        while pending:
            item, depth = pending.pop()
            count += 1
            if count > 30000 or depth > 32:
                raise ValueError("Metadata complexity limit exceeded")
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError("Nonfinite metadata number")
            children = (
                item.values() if isinstance(item, dict) else item if isinstance(item, list) else []
            )
            pending.extend((child, depth + 1) for child in children)
        return value
    except (RecursionError, UnicodeError, json.JSONDecodeError):
        raise ValueError("Invalid or excessively nested JSON") from None


def invalid_number() -> None:
    raise ValueError("Nonfinite numbers are unsupported")


def glb(data: bytes) -> dict[str, Any]:
    if not 20 <= len(data) <= MAX_FILE:
        raise ValueError("Invalid GLB size")
    magic, version, length = struct.unpack_from("<4sII", data)
    if magic != b"glTF" or version != 2 or length != len(data):
        raise ValueError("A complete GLB 2.0 file is required")
    chunks: list[tuple[int, bytes]] = []
    offset = 12
    while offset < length:
        if offset + 8 > length:
            raise ValueError("Truncated GLB chunk")
        size, kind = struct.unpack_from("<II", data, offset)
        offset += 8
        if size % 4 or offset + size > length:
            raise ValueError("Invalid GLB chunk length")
        chunks.append((kind, data[offset : offset + size]))
        offset += size
    if len(chunks) != 2 or [c[0] for c in chunks] != [0x4E4F534A, 0x004E4942]:
        raise ValueError("The pilot requires one JSON and one embedded BIN chunk")
    model = bounded_json(chunks[0][1])
    if not isinstance(model, dict) or model.get("asset", {}).get("version") != "2.0":
        raise ValueError("Only glTF 2.0 is supported")
    if any(
        model.get(key)
        for key in (
            "extensionsUsed",
            "extensionsRequired",
            "animations",
            "skins",
            "images",
            "textures",
        )
    ):
        raise ValueError(
            "Prepare an untextured static core GLB; extensions, skins and animation are unsupported"
        )
    buffers = model.get("buffers", [])
    if (
        len(buffers) != 1
        or "uri" in buffers[0]
        or not 0 < buffers[0].get("byteLength", 0) <= len(chunks[1][1])
    ):
        raise ValueError("External or invalid model buffers are unsupported")
    views = model.get("bufferViews", [])
    accessors = model.get("accessors", [])
    if len(views) > 1000 or len(accessors) > 1000:
        raise ValueError("Model accessor budget exceeded")
    for view in views:
        if (
            view.get("buffer", 0) != 0
            or not 0 <= view.get("byteOffset", 0) <= len(chunks[1][1])
            or not 0 < view.get("byteLength", 0) <= len(chunks[1][1]) - view.get("byteOffset", 0)
        ):
            raise ValueError("Model buffer view exceeds embedded bytes")
    total_vertices = 0
    for accessor in accessors:
        size = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}.get(
            accessor.get("componentType")
        )
        width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}.get(accessor.get("type"))
        count = accessor.get("count", 0)
        index = accessor.get("bufferView", -1)
        if (
            "sparse" in accessor
            or not size
            or not width
            or not isinstance(count, int)
            or not 0 < count <= 300000
            or not isinstance(index, int)
            or not 0 <= index < len(views)
        ):
            raise ValueError("Invalid or unsupported accessor")
        view = views[index]
        stride = view.get("byteStride", size * width)
        if (
            not size * width <= stride <= 252
            or accessor.get("byteOffset", 0) < 0
            or accessor.get("byteOffset", 0) + (count - 1) * stride + size * width
            > view["byteLength"]
        ):
            raise ValueError("Accessor exceeds its buffer view")
        if accessor.get("type") == "VEC3":
            total_vertices += count
        if accessor.get("componentType") == 5126:
            start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
            for item in range(count):
                values = struct.unpack_from("<" + "f" * width, chunks[1][1], start + item * stride)
                if any(not math.isfinite(value) or abs(value) > 1e6 for value in values):
                    raise ValueError("Nonfinite or unbounded geometry coordinates")
    if total_vertices > 200000:
        raise ValueError("Model vertex budget exceeded")
    nodes = model.get("nodes", [])
    meshes = model.get("meshes", [])
    if not 1 <= len(nodes) <= 100 or not 1 <= len(meshes) <= 100:
        raise ValueError("Model must contain at most 100 nodes and meshes")
    triangles = 0
    for mesh in meshes:
        for primitive in mesh.get("primitives", []):
            if primitive.get("mode", 4) != 4 or "POSITION" not in primitive.get("attributes", {}):
                raise ValueError("Only triangle meshes with positions are supported")
            refs = [
                *primitive["attributes"].values(),
                *([primitive["indices"]] if "indices" in primitive else []),
            ]
            if any(not isinstance(ref, int) or not 0 <= ref < len(accessors) for ref in refs):
                raise ValueError("Unresolved mesh accessor")
            triangles += (
                accessors[primitive.get("indices", primitive["attributes"]["POSITION"])]["count"]
                // 3
            )
    if not 1 <= triangles <= 100000:
        raise ValueError("Model triangle budget exceeded")
    parents: dict[int, int] = {}
    for index, node in enumerate(nodes):
        for key, expected in (("translation", 3), ("rotation", 4), ("scale", 3), ("matrix", 16)):
            if key in node and (
                not isinstance(node[key], list)
                or len(node[key]) != expected
                or any(
                    isinstance(v, bool) or not isinstance(v, (int, float)) or abs(v) > 1e6
                    for v in node[key]
                )
            ):
                raise ValueError("Invalid model node transform")
        if "mesh" in node and not 0 <= node["mesh"] < len(meshes):
            raise ValueError("Unresolved mesh")
        for child in node.get("children", []):
            if not isinstance(child, int) or not 0 <= child < len(nodes) or child in parents:
                raise ValueError("Ambiguous model hierarchy")
            parents[child] = index
    for index in range(len(nodes)):
        visited: set[int] = set()
        current = index
        while current in parents:
            if current in visited:
                raise ValueError("Cyclic model hierarchy")
            visited.add(current)
            current = parents[current]
    scenes = model.get("scenes", [])
    scene_index = model.get("scene", 0)
    if not isinstance(scene_index, int) or not 0 <= scene_index < len(scenes):
        raise ValueError("A default model scene is required")
    reachable: set[int] = set()
    pending = list(scenes[scene_index].get("nodes", []))
    while pending:
        index = pending.pop()
        if not isinstance(index, int) or not 0 <= index < len(nodes) or index in reachable:
            raise ValueError("Unresolved or ambiguous scene root")
        reachable.add(index)
        pending.extend(nodes[index].get("children", []))
    if any("mesh" in node and index not in reachable for index, node in enumerate(nodes)):
        raise ValueError("Every mapped mesh must belong to the default scene")
    return {
        "format": "glb",
        "version": "2.0",
        "triangles": triangles,
        "vertices": total_vertices,
        "nodes": [
            {
                "ref": f"node:{i}",
                "name": str(n.get("name", f"Part {i + 1}"))[:120],
                "hint": str(n.get("extras", {}).get("twin_component", ""))[:120],
            }
            for i, n in enumerate(nodes)
            if "mesh" in n
        ],
        "units": "glTF meters; confirm source preparation",
    }


def archive(data: bytes) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        entries = package.infolist()
        if len(entries) > 100:
            raise ValueError("Package entry limit exceeded")
        total = 0
        for entry in entries:
            name = entry.filename
            path = PurePosixPath(name)
            if (
                "\\" in name
                or path.is_absolute()
                or ".." in path.parts
                or name != str(path)
                or name in files
                or stat.S_ISLNK(entry.external_attr >> 16)
                or entry.flag_bits & 1
            ):
                raise ValueError("Unsafe or duplicate package path")
            if entry.is_dir():
                continue
            total += entry.file_size
            if (
                total > MAX_EXPANDED
                or entry.file_size > MAX_FILE
                or entry.file_size > max(1, entry.compress_size) * 100
            ):
                raise ValueError("Package expansion limit exceeded")
            content = package.read(entry)
            if name.endswith((".xml", ".rels")) or name == "[Content_Types].xml":
                root = ElementTree.fromstring(content)
                if any(element.attrib.get("TargetMode") == "External" for element in root.iter()):
                    raise ValueError("External package relationships are unsupported")
            files[name] = content
    return files


def preview(data: bytes, filename: str) -> tuple[dict[str, Any], dict[str, bytes]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".glb":
        return glb(data), {}
    if suffix in {".step", ".stp", ".pdf", ".txt", ".png", ".jpg"}:
        return {
            "format": "attachment",
            "renderable": False,
            "notice": "Source attachment preserved. Prepare a GLB for 3D viewing.",
        }, {}
    files: dict[str, bytes] = {}
    if suffix == ".aasx":
        files = archive(data)
        candidates = [
            (name, value) for name, value in files.items() if name.lower().endswith(".json")
        ]
        if len(candidates) != 1 or any(
            name.lower().endswith(".xml") and name != "[Content_Types].xml" for name in files
        ):
            raise ValueError(
                "The supported AASX 3.0 profile requires one AAS JSON "
                "environment; AAS XML is unsupported"
            )
        raw = candidates[0][1]
        store: DictIdentifiableStore[Any] = DictIdentifiableStore()
        with aasx.AASXReader(io.BytesIO(data), failsafe=False) as reader:
            supplementary = aasx.DictSupplementaryFileContainer()  # type: ignore[no-untyped-call]
            reader.read_into(store, supplementary)
    elif suffix == ".json":
        raw = data
    else:
        raise ValueError("Supported files: GLB, AAS JSON/AASX and source PDF/TXT/STEP/PNG/JPG")
    environment = bounded_json(raw)
    if not isinstance(environment, dict) or set(environment) - {
        "assetAdministrationShells",
        "submodels",
        "conceptDescriptions",
    }:
        raise ValueError("Unsupported AAS environment/version; expected AAS 3.0 JSON")
    # Validate with the maintained metamodel parser. Preserve original bytes and
    # full JSON alongside our explicit supported projection, including unknown submodels.
    aas_json.read_aas_json_file(io.StringIO(raw.decode()), failsafe=False)
    shells = environment.get("assetAdministrationShells", [])
    if len(shells) != 1 or shells[0].get("modelType") != "AssetAdministrationShell":
        raise ValueError("Import one AAS 3.0 equipment shell at a time")
    shell = shells[0]
    references: list[dict[str, Any]] = []
    properties: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    stack = list(environment.get("submodels", []))
    while stack:
        item = stack.pop()
        if not isinstance(item, dict):
            continue
        kind = item.get("modelType")
        if kind == "File":
            value = str(item.get("value", ""))
            embedded = value.lstrip("/") in files
            references.append(
                {
                    "id": item.get("idShort"),
                    "path": value,
                    "media_type": item.get("contentType"),
                    "embedded": embedded,
                    "status": "embedded"
                    if embedded
                    else "external_not_fetched"
                    if ":" in value
                    else "missing",
                }
            )
        elif kind == "Property":
            properties.append(
                {
                    "id": item.get("idShort"),
                    "value": str(item.get("value", ""))[:500],
                    "semantic_id": item.get("semanticId"),
                }
            )
        elif kind not in {"Submodel", "SubmodelElementCollection", "SubmodelElementList"}:
            unsupported.append({"type": kind, "id": item.get("idShort")})
        stack.extend(item.get("submodelElements", []))
        if isinstance(item.get("value"), list):
            stack.extend(item["value"])
    models = [name for name in files if name.lower().endswith(".glb")]
    model_previews = [{"path": name, **glb(files[name])} for name in models]
    return {
        "format": "aasx" if files else "aas-json",
        "specification": "AAS 3.0 JSON; AASX 3.0 JSON profile",
        "aas_id": shell["id"],
        "name": shell.get("idShort", "Imported equipment"),
        "external_id": shell.get("assetInformation", {}).get("globalAssetId", ""),
        "properties": properties,
        "references": references,
        "models": model_previews,
        "unsupported": unsupported,
        "preserved_environment": environment,
        "geometry_status": "embedded_review_required"
        if models
        else "No embedded geometry. Attach a GLB or choose the illustrative pump template.",
        "conformance": "Bounded import profile; full AAS/02026 conformance is not claimed",
    }, files
