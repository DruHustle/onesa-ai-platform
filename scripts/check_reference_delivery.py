"""Verify NVIDIA public assets over HTTP from an isolated running frontend image."""

import argparse
import hashlib
import http.client
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = (
    ROOT / "onesa-ai-platform-frontend/apps/chat/public/models/nvidia/manifest.json"
)
MEDIA_TYPES = {
    "glb": "model/gltf-binary",
    "thumbnail": "image/png",
    "licenseFile": "text/plain",
    "sourceFile": "application/json",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(origin):
    target = urlsplit(origin)
    require(
        target.scheme == "http"
        and target.hostname in {"127.0.0.1", "localhost", "::1"}
        and target.username is None
        and target.password is None
        and target.path in {"", "/"}
        and not target.query
        and not target.fragment,
        "Reference delivery checks require a credential-free loopback HTTP origin",
    )
    manifest = MANIFEST.read_bytes()
    require(0 < len(manifest) <= 65536, "Invalid source manifest size")
    catalog = json.loads(manifest)
    require(
        catalog["schemaVersion"] == 1 and 1 <= len(catalog["assets"]) <= 12,
        "Invalid catalog",
    )
    files = [
        (
            "manifest.json",
            len(manifest),
            hashlib.sha256(manifest).hexdigest(),
            "application/json",
        )
    ]
    for asset in catalog["assets"]:
        for kind, media_type in MEDIA_TYPES.items():
            artifact = asset[kind]
            path = artifact["path"]
            require(
                re.fullmatch(r"nvidia-[a-z-]+/[A-Za-z][A-Za-z0-9_.-]+", path)
                is not None
                and path.split("/")[0] == asset["id"]
                and type(artifact["byteLength"]) is int
                and 0 < artifact["byteLength"] <= 4 * 1024 * 1024
                and re.fullmatch(r"[a-f0-9]{64}", artifact["sha256"]) is not None,
                "Invalid source artifact descriptor",
            )
            files.append((path, artifact["byteLength"], artifact["sha256"], media_type))
    require(len({item[0] for item in files}) == len(files), "Duplicate artifact paths")
    for path, size, checksum, media_type in files:
        # HTTPConnection neither follows redirects nor reads proxy/auth environment
        # variables. Each response is bounded by its reviewed expected length.
        connection = http.client.HTTPConnection(
            target.hostname, target.port, timeout=10
        )
        try:
            connection.request(
                "GET", "/models/nvidia/" + path, headers={"Accept-Encoding": "identity"}
            )
            response = connection.getresponse()
            require(
                response.status == 200,
                f"Reference delivery failed for {path}: HTTP {response.status}",
            )
            require(
                response.getheader("Content-Type", "").split(";", 1)[0].lower()
                == media_type,
                f"Incorrect reference media type: {path}",
            )
            require(
                response.getheader("X-Content-Type-Options", "").lower() == "nosniff",
                f"Missing reference nosniff header: {path}",
            )
            content = response.read(size + 1)
            require(
                len(content) == size
                and hashlib.sha256(content).hexdigest() == checksum,
                f"Reference delivery integrity mismatch: {path}",
            )
        finally:
            connection.close()
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin")
    count = verify(parser.parse_args().origin)
    print(
        f"PASS: {count} reference artifacts served with exact bytes, hashes and media types"
    )


if __name__ == "__main__":
    main()
