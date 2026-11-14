"""Check actual local secret values in generated assets and selected production images."""

import argparse
import gzip
import io
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "data/acceptance-005"
parser = argparse.ArgumentParser()
parser.add_argument("--image", action="append", default=[])
args = parser.parse_args()
values = set()
for environment in [ROOT / ".env", STATE / "staging.env"]:
    if not environment.exists():
        continue
    for line in environment.read_text().splitlines():
        name, separator, value = line.partition("=")
        if (
            separator
            and any(word in name for word in ["PASSWORD", "TOKEN", "API_KEY"])
            and len(value.strip()) >= 16
        ):
            values.add(value.strip().encode())
for path in (STATE / "secrets").iterdir():
    value = path.read_bytes().strip()
    if path.name.endswith(".pgpass"):
        value = value.split(b":")[-1]
    if len(value) >= 16:
        values.add(value)
max_length = max(map(len, values))


def contains_secret(stream):
    previous = b""
    while chunk := stream.read(1024 * 1024):
        combined = previous + chunk
        if any(value in combined for value in values):
            return True
        previous = combined[-max_length:]
    return False


count = 0
for directory in [
    ROOT / "onesa-ai-platform-frontend/apps/chat/.next",
    ROOT / "onesa-ai-platform-frontend/apps/docs/build-public",
    ROOT / "onesa-ai-platform-frontend/apps/docs/build-internal",
    ROOT / "docs/generated",
    ROOT / "packages",
]:
    for path in directory.rglob("*"):
        if path.is_file():
            count += 1
            with path.open("rb") as incoming:
                if contains_secret(incoming):
                    raise SystemExit(
                        "Secret present in artifact: " + str(path.relative_to(ROOT))
                    )
images = []
for image in args.image:
    process = subprocess.Popen(
        ["docker", "image", "save", image],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout
    with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
        for member in archive:
            if not member.isfile():
                continue
            stream = archive.extractfile(member)
            assert stream
            stream = io.BufferedReader(stream)
            if stream.peek(2).startswith(b"\x1f\x8b"):
                stream = gzip.GzipFile(fileobj=stream)
            if contains_secret(stream):
                process.kill()
                process.wait()
                raise SystemExit("Secret present in selected image: " + image)
    if process.wait() != 0:
        raise SystemExit("Selected image export failed")
    identifier = subprocess.check_output(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image], text=True
    ).strip()
    images.append({"name": image, "id": identifier})
(STATE / "artifact-secrets.json").write_text(
    json.dumps(
        {
            "result": "PASS",
            "generated_files_scanned": count,
            "images": images,
            "method": "Exact current development/staging secret values, including layer archives; source pattern scan is separate",
            "general_secret_detection_complete": False,
        },
        indent=2,
    )
    + "\n"
)
print(f"No current private secrets in {count} generated files and {len(images)} images")
