"""Bound immutable public fixture image reads; never retry a build, start or test."""

import argparse
import json
import re
import subprocess
import time


def pull(image, *, database=False):
    pattern = (
        r"pgvector/pgvector:pg16@sha256:[a-f0-9]{64}"
        if database
        else r"(?:docker.io/library/)?caddy:[A-Za-z0-9_.-]+@sha256:[a-f0-9]{64}"
    )
    if not isinstance(image, str) or not re.fullmatch(pattern, image):
        raise ValueError("An approved immutable fixture image is required")
    for attempt in range(2):
        try:
            result = subprocess.run(
                ["docker", "image", "pull", image],
                capture_output=True,
                timeout=90,
                check=False,
            )
            complete = result.returncode == 0
            if database and not complete:
                # Do not retry auth, missing manifests, daemon/config errors or
                # unknown failures. Never print arbitrary registry response text.
                detail = result.stderr[-16384:] + result.stdout[-16384:]
                fatal = re.search(
                    rb"(?:unauthorized|denied|manifest unknown|not found|"
                    rb"Cannot connect to the Docker daemon)",
                    detail,
                    re.IGNORECASE,
                )
                if fatal or not re.search(
                    rb"(?:unexpected HTTP status: (?:500|502|503|504)\b|"
                    rb"Client\.Timeout exceeded|TLS handshake timeout|i/o timeout)",
                    detail,
                ):
                    raise RuntimeError("Pinned database image read failed; no retry")
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
            if inspected.returncode != 0:
                raise RuntimeError("Pinned image identity could not be verified")
            try:
                digests = json.loads(inspected.stdout)
            except ValueError:
                raise RuntimeError(
                    "Pinned image identity could not be verified"
                ) from None
            if not isinstance(digests, list) or not any(
                isinstance(digest, str)
                and digest.endswith("@" + image.split("@", 1)[1])
                for digest in digests
            ):
                raise RuntimeError("Pinned image identity could not be verified")
            print("Pinned fixture image is available; digest verified")
            return
        if attempt == 0:
            print("Registry read did not complete; one retry of the same pinned image")
            time.sleep(3)
    checks = "Application" if database else "TLS"
    raise RuntimeError(f"Image download unavailable; {checks} checks have not started")


def main(database=False):
    compose = (
        ["docker", "compose", "config", "--format", "json"]
        if database
        else [
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
        ]
    )
    # A hosted first Compose invocation exceeded the former 15s bound before
    # any image read. Keep this read single-attempt and leave the four-minute
    # step enough time for 30 + (2 * 90) + 3 + 10 = 223 seconds in total.
    try:
        result = subprocess.run(
            compose,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Isolated compose configuration timed out; no retry") from None
    if result.returncode != 0 or len(result.stdout) > 1024 * 1024:
        raise RuntimeError("Isolated compose configuration unavailable")
    # The generated configuration contains only isolated fixtures, but do not log it.
    image = json.loads(result.stdout)["services"]["db" if database else "proxy"][
        "image"
    ]
    pull(image, database=True) if database else pull(image)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", action="store_true")
    main(database=parser.parse_args().database)
