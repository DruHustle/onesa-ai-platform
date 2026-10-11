"""Exercise the final image's default CMD, never a replacement startup command."""

import argparse
import json
import subprocess
import time
import uuid


def docker(*args, check=True):
    return subprocess.run(
        ["docker", *args], check=check, capture_output=True, text=True
    ).stdout.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    image = parser.parse_args().image
    prefix = "onesa-startup-" + uuid.uuid4().hex[:12]
    names = [prefix, prefix + "-invalid"]
    try:
        config = json.loads(docker("image", "inspect", image))[0]["Config"]
        assert config["Cmd"] == ["sh", "/app/start.sh"], config["Cmd"]
        assert not config.get("Entrypoint")
        assert config["WorkingDir"] == "/app"
        docker(
            "run",
            "--rm",
            "--network",
            "none",
            image,
            "python",
            "-c",
            "import uvicorn; from app.main import create_app; assert callable(create_app)",
        )
        help_text = docker(
            "run",
            "--rm",
            "--network",
            "none",
            image,
            "python",
            "-m",
            "uvicorn",
            "--help",
        )
        for option in [
            "--factory",
            "--no-proxy-headers",
            "--no-access-log",
            "--limit-concurrency",
            "--timeout-keep-alive",
            "--timeout-graceful-shutdown",
        ]:
            assert option in help_text, option
        # Synthetic development settings test process startup independently of inference/DB readiness.
        docker(
            "run",
            "-d",
            "--name",
            names[0],
            "--network",
            "none",
            "-e",
            "PORT=18081",
            "-e",
            "ONESA_ENVIRONMENT=development",
            image,
        )
        for _ in range(60):
            probe = subprocess.run(
                [
                    "docker",
                    "exec",
                    names[0],
                    "python",
                    "-c",
                    "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:18081/health', timeout=1).status == 200",
                ],
                check=False,
                capture_output=True,
            )
            if probe.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise AssertionError("Default CMD did not serve health")
        command = docker(
            "exec",
            names[0],
            "python",
            "-c",
            "from pathlib import Path; print(Path('/proc/1/cmdline').read_bytes().replace(bytes([0]), b' ').decode())",
        )
        assert "--host 0.0.0.0" in command and "--port 18081" in command, command
        docker(
            "exec",
            names[0],
            "python",
            "-c",
            "import urllib.request, urllib.error\ntry: urllib.request.urlopen('http://127.0.0.1:18081/core-ready')\nexcept urllib.error.HTTPError as e: assert e.code == 503\nelse: raise AssertionError('Missing DB must not be ready')",
        )
        time.sleep(2)
        assert docker("inspect", "-f", "{{.State.Running}}", names[0]) == "true"
        docker("stop", "-t", "10", names[0])
        assert docker("inspect", "-f", "{{.State.ExitCode}}", names[0]) == "0"
        assert (
            "Finished server process"
            in docker("logs", names[0])
            + subprocess.run(
                ["docker", "logs", names[0]],
                check=False,
                capture_output=True,
                text=True,
            ).stderr
        )
        docker(
            "run",
            "-d",
            "--name",
            names[1],
            "--network",
            "none",
            "-e",
            "RENDER=true",
            "-e",
            "ONESA_ENVIRONMENT=production",
            image,
        )
        assert docker("wait", names[1]) == "1"
        invalid = subprocess.run(
            ["docker", "logs", names[1]], check=False, capture_output=True, text=True
        )
        assert "ValidationError" in invalid.stdout + invalid.stderr
        assert "not found" not in invalid.stdout + invalid.stderr
        print(
            "PASS: imports/options/default CMD/PORT/all-interface bind/liveness/503 dependency/graceful SIGTERM/configuration failure"
        )
    finally:
        for name in names:
            docker("rm", "-f", name, check=False)


if __name__ == "__main__":
    main()
