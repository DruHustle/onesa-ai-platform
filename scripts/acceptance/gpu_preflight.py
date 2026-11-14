"""Collect actual NVIDIA prerequisites; never start inference or download a model."""

import argparse
import json
import platform
import shutil
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument(
    "--container", help="Existing, explicitly selected private inference container"
)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
report = {
    "environment": platform.platform(),
    "result": "BLOCKED",
    "model_inference_tested": False,
}
if not shutil.which("nvidia-smi"):
    report["blocker"] = "No NVIDIA driver/GPU available on this host"
else:
    command = [
        "nvidia-smi",
        "--query-gpu=name,driver_version,memory.total,memory.used,memory.free",
        "--format=csv,noheader,nounits",
    ]
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=15, check=False
    )
    report["host_gpu_query_exit"] = result.returncode
    report["host_gpu_inventory"] = (
        result.stdout.strip() if result.returncode == 0 else "unavailable"
    )
    if args.container and result.returncode == 0:
        result = subprocess.run(
            ["docker", "exec", args.container, *command],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        report["container_gpu_query_exit"] = result.returncode
        report["container_gpu_inventory"] = (
            result.stdout.strip() if result.returncode == 0 else "unavailable"
        )
        report["result"] = "PASS" if result.returncode == 0 else "FAIL"
        report["blocker"] = "Real model acceptance still required"
    else:
        report["blocker"] = (
            "Select an existing GPU-enabled private container after host preparation"
        )
args.output.write_text(json.dumps(report, indent=2) + "\n")
print(report["result"] + ": " + report["blocker"])
raise SystemExit(0 if report["result"] == "PASS" else 2)
