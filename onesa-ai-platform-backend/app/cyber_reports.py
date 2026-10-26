"""Bounded offline CycloneDX 1.6 subset. No feed, URL fetch or exploitability claim."""

import hashlib
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.cyber_schemas import Identifier, Short, Wire, utc


class Component(Wire):
    type: Literal["application", "library", "operating-system", "firmware", "device"]
    ref: str = Field(alias="bom-ref", min_length=1, max_length=128)
    name: Identifier
    version: Identifier | None = None
    group: Identifier | None = None
    purl: str | None = Field(default=None, max_length=512, pattern=r"^pkg:")


class Rating(Wire):
    severity: Literal["none", "info", "low", "medium", "high", "critical", "unknown"]
    score: Annotated[float, Field(ge=0, le=10, allow_inf_nan=False)] | None = None
    method: Literal["CVSSv2", "CVSSv3", "CVSSv31", "CVSSv4", "OWASP", "other"] | None = None


class Affect(Wire):
    ref: Identifier


class AdvisorySource(Wire):
    name: Identifier


class Vulnerability(Wire):
    id: Identifier
    source: AdvisorySource | None = None
    ratings: list[Rating] = Field(default_factory=list, max_length=5)
    affects: list[Affect] = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)


class ToolComponent(Wire):
    type: Literal["application"]
    name: Short
    version: Short


class Tools(Wire):
    components: list[ToolComponent] = Field(min_length=1, max_length=5)


class Metadata(Wire):
    tools: Tools
    timestamp: str

    @model_validator(mode="after")
    def real_date(self) -> Self:
        utc(self.timestamp)
        return self


class CycloneDX(Wire):
    bomFormat: Literal["CycloneDX"]
    specVersion: Literal["1.6"]
    version: int = Field(ge=1, le=1000000)
    serialNumber: str | None = None
    metadata: Metadata
    components: list[Component] = Field(min_length=1, max_length=250)
    vulnerabilities: list[Vulnerability] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def references(self) -> Self:
        if self.serialNumber is not None:
            UUID(self.serialNumber.removeprefix("urn:uuid:"))
            if not self.serialNumber.startswith("urn:uuid:"):
                raise ValueError("Use a CycloneDX urn:uuid serial number")
        refs = {component.ref for component in self.components}
        if len(refs) != len(self.components):
            raise ValueError("Component bom-ref values must be unique")
        if any(affect.ref not in refs for vuln in self.vulnerabilities for affect in vuln.affects):
            raise ValueError("Every vulnerability reference must resolve within this inventory")
        return self


def raw_sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
