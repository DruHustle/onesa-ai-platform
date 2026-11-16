"""Install checksum-verified official Node 24 inside the ignored repository runtime."""

import hashlib
import platform
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "v24.22.1"


def install():
    target = ROOT / ("data/runtime/node24-" + VERSION.removeprefix("v"))
    if (target / "bin/node").is_file():
        actual = subprocess.check_output(
            [str(target / "bin/node"), "--version"], text=True
        ).strip()
        if actual != VERSION:
            raise SystemExit("Existing runtime version mismatch; preserve it and stop")
        print(actual)
        return
    operating_system = {"Darwin": "darwin", "Linux": "linux"}.get(platform.system())
    architecture = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64"}.get(
        platform.machine()
    )
    if not operating_system or not architecture:
        raise SystemExit("Unsupported Node distribution platform")
    name = f"node-{VERSION}-{operating_system}-{architecture}"
    filename = name + ".tar.xz"
    base = f"https://nodejs.org/dist/{VERSION}/"
    staging = ROOT / ("data/runtime/node24-" + VERSION.removeprefix("v") + "-install")
    staging.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(base + "SHASUMS256.txt", timeout=30) as response:
        checksums = response.read().decode().splitlines()
    expected = next(
        line.split()[0] for line in checksums if line.split()[-1] == filename
    )
    archive = staging / filename
    with (
        urllib.request.urlopen(base + filename, timeout=30) as response,
        archive.open("wb") as output,
    ):
        shutil.copyfileobj(response, output)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise SystemExit("Node distribution checksum mismatch; refusing extraction")
    with tarfile.open(archive) as distribution:
        distribution.extractall(staging, filter="data")
    (staging / name).rename(target)
    shutil.rmtree(staging)
    subprocess.run([str(target / "bin/node"), "--version"], check=True)
    print("Official SHA-256 verified; repository-local runtime installed.")


if __name__ == "__main__":
    install()
