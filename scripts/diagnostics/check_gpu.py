"""No model downloads; report actual hardware and optional PyTorch status."""

import importlib.util
import json
import platform
import shutil
import subprocess

report = {"os": platform.platform(), "nvidia_smi": None, "torch": "not installed"}
if shutil.which("nvidia-smi"):
    result = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,driver_version,memory.total",
            "--format=csv,noheader",
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )
    report["nvidia_smi"] = (
        result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    )
if importlib.util.find_spec("torch"):
    import torch

    report["torch"] = {
        "version": torch.__version__,
        "cuda": torch.cuda.is_available(),
        "devices": torch.cuda.device_count(),
    }
print(json.dumps(report, indent=2))
