"""Gate current Trivy JSON results; do not suppress unfixed vendor findings."""

import argparse
import json
from collections import Counter
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("reports", nargs="+", type=Path)
args = parser.parse_args()
failed = False
for path in args.reports:
    report = json.loads(path.read_text())
    if not report.get("Results") or not report.get("ArtifactName"):
        raise SystemExit("Incomplete scanner report: " + str(path))
    counts = Counter(
        v["Severity"] for r in report["Results"] for v in r.get("Vulnerabilities", [])
    )
    secret_count = sum(len(r.get("Secrets", [])) for r in report["Results"])
    print(path.name, json.dumps(dict(counts)), "secret_findings=" + str(secret_count))
    # Only print public advisory metadata. Secret findings and raw scan remain private.
    for result in report["Results"]:
        for finding in result.get("Vulnerabilities", []):
            if finding["Severity"] in {"CRITICAL", "HIGH"}:
                print(
                    finding["Severity"],
                    finding["VulnerabilityID"],
                    finding["PkgName"],
                    finding.get("InstalledVersion", ""),
                    "fixed:",
                    finding.get("FixedVersion") or "unavailable",
                )
    failed |= bool(counts["HIGH"] or counts["CRITICAL"] or secret_count)
raise SystemExit(1 if failed else 0)
