"""Bound immutable public TLS-proxy image reads; never retry a build, start or test."""

import json
import re
import subprocess
import time


def pull(image):
    if not re.fullmatch(
        r"(?:docker.io/library/)?caddy:[A-Za-z0-9_.-]+@sha256:[a-f0-9]{64}", image
    ):
        raise ValueError("An immutable official TLS-proxy image is required")
    for attempt in range(2):
        try:
            result = subprocess.run(
                ["docker", "image", "pull", image],
                capture_output=True,
                timeout=90,
                check=False,
            )
            complete = result.returncode == 0
        except subprocess.TimeoutExpired:
            complete = False
        if complete:
            inspected = subprocess.run(
                [
                    "docker",
                    "image",
                    "inspect",
                    image,
                    "--format",
                    "{{json .RepoDigests}}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if inspected.returncode != 0 or not any(
                digest.endswith("@" + image.split("@", 1)[1])
                for digest in json.loads(inspected.stdout)
            ):
                raise RuntimeError("Pinned image identity could not be verified")
            print("Pinned TLS-proxy image is available")
            return
        if attempt == 0:
            print("Registry read did not complete; one retry of the same pinned image")
            time.sleep(3)
    raise RuntimeError("Image download unavailable; TLS checks have not started")


def main():
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            "data/acceptance-005/staging.env",
            "-p",
            "onesa-acceptance-005",
            "-f",
            "compose.yaml",
            "-f",
            "compose.production.yaml",
            "-f",
            "compose.acceptance.yaml",
            "config",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode != 0 or len(result.stdout) > 1024 * 1024:
        raise RuntimeError("Isolated compose configuration unavailable")
    # The generated configuration contains only isolated fixtures, but do not log it.
    pull(json.loads(result.stdout)["services"]["proxy"]["image"])


if __name__ == "__main__":
    main()
