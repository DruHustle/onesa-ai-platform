"""Run through `make openapi`; keep the implemented API contract reproducible."""

import json
from pathlib import Path

from app.config import Settings
from app.main import create_app

root = Path(__file__).resolve().parents[1]
output = root / "docs/api/openapi.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(create_app(Settings()).openapi(), indent=2) + "\n")
