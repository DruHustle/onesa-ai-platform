"""Bound advisory reads; never retry findings, mutate dependencies or waive an audit."""

import argparse
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
POLICIES = {
    "infra/oracle/cloudflare-tools": "low",
    "onesa-ai-platform-frontend/apps/docs": "low",
    "onesa-ai-platform-frontend/apps/chat": "high",
}
LEVELS = ("info", "low", "moderate", "high", "critical")
HTTP_TIMEOUT_MS = 45000
PROCESS_TIMEOUT = 100


def fingerprints(prefix):
    values = {}
    for name in ("package.json", "package-lock.json"):
        path = prefix / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 8 * 1024**2:
            raise ValueError("Audit requires unchanged regular manifest/lock files")
        values[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return values


def classify(stdout, returncode, level="low"):
    """Validate npm's v2 report before trusting either its counts or exit status."""
    if len(stdout) > 4 * 1024**2:
        return "INVALID_REPORT", None
    try:
        report = json.loads(stdout)
    except (ValueError, UnicodeError):
        return "INVALID_REPORT", None
    if not isinstance(report, dict):
        return "INVALID_REPORT", None
    if "auditReportVersion" in report:
        try:
            if (
                type(report["auditReportVersion"]) is not int
                or report["auditReportVersion"] != 2
            ):
                raise ValueError
            counts = report["metadata"]["vulnerabilities"]
            entries = report["vulnerabilities"]
            if (
                not isinstance(counts, dict)
                or not isinstance(entries, dict)
                or "error" in report
            ):
                raise ValueError
            if any(
                type(counts[k]) is not int or counts[k] < 0 for k in (*LEVELS, "total")
            ):
                raise ValueError
            observed = {key: 0 for key in LEVELS}
            for value in entries.values():
                observed[value["severity"]] += 1
            if observed != {key: counts[key] for key in LEVELS} or counts[
                "total"
            ] != sum(observed.values()):
                raise ValueError
            # A disclosed finding cannot be erased by a second request.
            if any(observed[key] for key in LEVELS[LEVELS.index(level) :]):
                return "FINDINGS", observed
            if returncode != 0:
                if sum(observed.values()):
                    return "FINDINGS", observed
                return "INVALID_REPORT", None
            return "PASS", observed
        except (KeyError, TypeError, ValueError):
            return "INVALID_REPORT", None
    if "vulnerabilities" in report or "metadata" in report:
        return "INVALID_REPORT", None
    error = report.get("error")
    code = error.get("code") if isinstance(error, dict) else None
    transport_codes = {
        "ETIMEDOUT",
        "ESOCKETTIMEDOUT",
        "ECONNRESET",
        "ECONNREFUSED",
        "ECONNABORTED",
        "EAI_AGAIN",
        "ENETUNREACH",
        "E408",
        "E429",
        "E502",
        "E503",
        "E504",
    }
    if returncode != 0 and isinstance(code, str) and code in transport_codes:
        return "TRANSPORT_UNAVAILABLE", None
    if code is not None and code != "FETCH_ERROR":
        return "AUDIT_UNAVAILABLE", None
    # npm's audit-error utility emits this top-level shape for registry failures.
    # Do not inspect/log its headers or body, which may contain private registry data.
    uri = report.get("uri")
    message = report.get("message")
    timeout = isinstance(message, str) and re.fullmatch(
        r"network timeout at: (https://registry\.npmjs\.org/-/npm/v1/security/(?:advisories/bulk|audits/quick))",
        message,
    )
    if returncode != 0 and timeout and (uri is None or uri == timeout[1]):
        return "TRANSPORT_UNAVAILABLE", None
    if isinstance(uri, str):
        try:
            parsed = urlsplit(uri)
        except ValueError:
            return "INVALID_REPORT", None
        official = (
            parsed.scheme == "https"
            and parsed.netloc == "registry.npmjs.org"
            and parsed.path
            in {"/-/npm/v1/security/advisories/bulk", "/-/npm/v1/security/audits/quick"}
            and not parsed.query
            and not parsed.fragment
        )
        status = report.get("statusCode")
        if (
            returncode != 0
            and official
            and type(status) is int
            and status in {408, 429, 502, 503, 504}
        ):
            return "TRANSPORT_UNAVAILABLE", None
    return "AUDIT_UNAVAILABLE", None


def finding_details(stdout, prefix):
    """Keep actionable findings, including below-threshold ones; omit unknown/error fields."""
    entries = json.loads(stdout)["vulnerabilities"]
    packages = json.loads((prefix / "package-lock.json").read_text()).get(
        "packages", {}
    )
    values = []
    for name, entry in entries.items():
        if not re.fullmatch(r"[A-Za-z0-9@_./-]{1,200}", name):
            raise ValueError("Unrecognized advisory package name")
        nodes = entry.get("nodes", [])
        versions = {
            packages[n].get("version")
            for n in nodes
            if isinstance(n, str) and n in packages
        }
        affected = entry.get("range")
        fix = entry.get("fixAvailable")
        values.append(
            {
                "package": name,
                "severity": entry["severity"],
                "affected_range": affected[:240] if isinstance(affected, str) else None,
                "locked_versions": sorted(
                    v
                    for v in versions
                    if isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9.+_-]{1,100}", v)
                ),
                "fix_available": fix
                if isinstance(fix, bool)
                else True
                if isinstance(fix, dict)
                else None,
            }
        )
    return values


def audit(prefix, level="low"):
    if level not in POLICIES.values():
        raise ValueError("Unsupported audit threshold")
    before = fingerprints(prefix)
    for attempt in (1, 2):
        try:
            result = subprocess.run(
                [
                    "npm",
                    "--prefix",
                    str(prefix),
                    "audit",
                    f"--audit-level={level}",
                    "--json",
                    "--fetch-retries=0",
                    f"--fetch-timeout={HTTP_TIMEOUT_MS}",
                ],
                capture_output=True,
                timeout=PROCESS_TIMEOUT,
                check=False,
            )
            raw = result.stdout
            status, counts = classify(raw, result.returncode, level)
        except subprocess.TimeoutExpired as error:
            raw = error.output or b""
            status, counts = classify(raw, 124, level)
            if status != "FINDINGS":
                status, counts = "TRANSPORT_UNAVAILABLE", None
        if fingerprints(prefix) != before:
            raise ValueError(
                "Audit inputs changed; preserve work and qualify the new inputs"
            )
        print(
            json.dumps(
                {
                    "npm_audit": status,
                    "attempt": attempt,
                    "audit_level": level,
                    "counts": counts,
                    "findings": finding_details(raw, prefix)
                    if status in {"PASS", "FINDINGS"}
                    else [],
                }
            ),
            flush=True,
        )
        if status == "PASS":
            return 0
        if status == "FINDINGS":
            return 1
        if status != "TRANSPORT_UNAVAILABLE" or attempt == 2:
            return 2
        time.sleep(3)
    return 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", choices=POLICIES, required=True)
    args = parser.parse_args()
    prefix = ROOT / args.prefix
    if prefix.resolve() != prefix:
        raise ValueError("Use the canonical reviewed documentation prefix")
    raise SystemExit(audit(prefix, POLICIES[args.prefix]))


if __name__ == "__main__":
    main()
