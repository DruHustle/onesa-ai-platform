"""Explicit local Oracle probe context; never a GitHub artifact or release grant."""

import json
import os
import re
import stat
from pathlib import Path
from uuid import UUID


def private_json(path):
    path = Path(path)
    mode = path.lstat()
    if (
        not stat.S_ISREG(mode.st_mode)
        or mode.st_mode & 0o077
        or mode.st_uid != os.getuid()
        or mode.st_size > 16384
    ):
        raise ValueError("Private owner context required")
    return json.loads(path.read_text())


def load_context(path):
    value = private_json(path)
    if (
        value.get("execution_context") != "owner-operated-oracle-staging"
        or value.get("repository") != "DruHustle/onesa-ai-platform"
        or not re.fullmatch(r"[a-f0-9]{40}", value.get("candidate_commit", ""))
        or type(value.get("ci_run_id")) is not int
        or value["ci_run_id"] <= 0
        or not re.fullmatch(r"prj_[A-Za-z0-9]+", value.get("project_id", ""))
        or not re.fullmatch(
            r"https://onesa-ai-platform-[a-z0-9-]+\.vercel\.app",
            value.get("frontend_origin", ""),
        )
    ):
        raise ValueError("Invalid Oracle staging probe context")
    if str(UUID(value["qualification_id"])) != value["qualification_id"]:
        raise ValueError("Invalid Oracle qualification identity")
    fixture = private_json(value["fixture_file"])
    users = fixture.get("users", [])
    if (
        fixture.get("candidate_commit") != value["candidate_commit"]
        or fixture.get("run_id") != str(value["ci_run_id"])
        or fixture.get("project_id") != value["project_id"]
        or fixture.get("scope") != "approved-synthetic-staging"
        or len(users) != 2
        or len({user.get("id") for user in users}) != 2
        or any(
            not re.fullmatch(
                r"release-audit-"
                + str(value["ci_run_id"])
                + r"-[a-f0-9]{24}@example\.com",
                user.get("email", ""),
            )
            for user in users
        )
    ):
        raise ValueError("Oracle fixture source mismatch")
    output = Path(value["output_dir"])
    mode = output.lstat()
    if (
        not stat.S_ISDIR(mode.st_mode)
        or mode.st_mode & 0o077
        or mode.st_uid != os.getuid()
    ):
        raise ValueError("Private Oracle output directory required")
    return value


def record_identity(context):
    return {
        "candidate_commit": context["candidate_commit"],
        "workflow_run_id": 0,
        "ci_run_id": context["ci_run_id"],
        "qualification_id": context["qualification_id"],
        "execution_context": context["execution_context"],
    }
