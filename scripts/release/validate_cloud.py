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
assert not blueprint.get("databases"), "Reuse the existing Neon project"
assert len(blueprint["services"]) == 1 and blueprint["services"][0]["type"] == "web"
assert all(service["plan"] == "free" for service in blueprint["services"])
assert not any(
    "generateValue" in entry
    for service in blueprint["services"]
    for entry in service["envVars"]
), "Preserve existing credentials"
front = ROOT / (
    "onesa-ai-platform-frontend/apps/chat"
    if ROOT.name == "onesa-ai-platform"
    else "onesa-company-portal-frontend"
)
vercel = json.loads((front / "vercel.json").read_text())
deployments = vercel["git"]["deploymentEnabled"]
assert deployments is False or deployments == {
    "main": False,
    "dev": False,
    "staging": True,
}, "Native production/dev deployments must remain disabled"
print(
    "PASS: official Blueprint schema, independent Docker contexts, main, manual Free API deployment and no duplicate database"
)
print(
    "BLOCKED: hosted domains, credentials, migrations, model/storage/email/scanner and acceptance must be verified separately"
)
