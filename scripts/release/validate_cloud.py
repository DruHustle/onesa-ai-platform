"""Offline configuration gate using the recorded official provider schema."""

import hashlib
import json
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
schema = FOLDER / "render.schema.json"
provenance = json.loads((FOLDER / "render.schema.provenance.json").read_text())
assert hashlib.sha256(schema.read_bytes()).hexdigest() == provenance["sha256"]
blueprint = yaml.safe_load((ROOT / "render.yaml").read_text())
jsonschema.validate(blueprint, json.loads(schema.read_text()))
for service in blueprint["services"]:
    assert service["branch"] == "main"
    assert service["autoDeployTrigger"] == "off"
    assert (ROOT / service["rootDir"] / service["dockerfilePath"]).is_file()
assert all(database["ipAllowList"] == [] for database in blueprint["databases"])
front = ROOT / (
    "onesa-ai-platform-frontend/apps/chat"
    if ROOT.name == "onesa-ai-platform"
    else "onesa-company-portal-frontend"
)
vercel = json.loads((front / "vercel.json").read_text())
assert vercel["git"]["deploymentEnabled"] is False
print(
    "PASS: official Blueprint schema, independent Docker contexts, main, manual deployment and private database ingress"
)
print(
    "BLOCKED: hosted domains, credentials, migrations, model/storage/email/scanner and acceptance must be verified separately"
)
