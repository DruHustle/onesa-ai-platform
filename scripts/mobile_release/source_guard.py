"""Bind packaging to tracked source and narrowly scoped native preparation edits."""

import hashlib
import json
import os
import stat
import subprocess


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(root, *args):
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, timeout=180, check=False
    )
    require(result.returncode == 0, "Source verification could not read Git state")
    return result.stdout


def generated_path(config, path):
    mobile = config["mobilePath"] + "/"
    if config.get("generatedNative") and any(
        path.startswith(mobile + platform + "/") for platform in ("android", "ios")
    ):
        return True
    # CocoaPods creates these inputs in repositories that do not commit them.
    return path == mobile + "ios/Podfile.lock" or path.startswith(
        mobile + "ios/" + config["scheme"] + ".xcworkspace/"
    )


def snapshot(config, root):
    source = git(root, "rev-parse", "HEAD").decode().strip()
    require(
        not git(root, "diff", "--cached", "--name-only", "-z").strip(),
        "Git index changed during packaging",
    )
    untracked = (
        git(root, "ls-files", "--others", "--exclude-standard", "-z")
        .decode()
        .split("\0")
    )
    require(
        all(not path or generated_path(config, path) for path in untracked),
        "Unexpected untracked source appeared during packaging",
    )
    files = {}
    for entry in git(root, "ls-tree", "-r", "-z", "HEAD").split(b"\0"):
        if not entry:
            continue
        metadata, encoded_path = entry.split(b"\t", 1)
        mode, kind, _ = metadata.decode().split()
        path = encoded_path.decode()
        require(
            kind == "blob" and mode in {"100644", "100755", "120000"},
            "Unsupported source tree entry",
        )
        target = root / path
        if not target.exists() and not target.is_symlink():
            files[path] = None
        elif target.is_symlink():
            files[path] = {
                "mode": "120000",
                "sha256": hashlib.sha256(os.fsencode(os.readlink(target))).hexdigest(),
            }
        else:
            require(target.is_file(), "Tracked source changed file type")
            actual_mode = "100755" if target.stat().st_mode & stat.S_IXUSR else "100644"
            with target.open("rb") as stream:
                files[path] = {
                    "mode": actual_mode,
                    "sha256": hashlib.file_digest(stream, "sha256").hexdigest(),
                }
    return {"schema": 1, "sourceSha": source, "files": files}


def initialize(config, work, root):
    require(
        not git(root, "diff", "HEAD", "--name-only", "-z").strip(),
        "Tracked source is not clean",
    )
    value = snapshot(config, root)
    value["transforms"] = []
    (work / "source-state.json").write_text(json.dumps(value, sort_keys=True) + "\n")


def verify(config, work, root, *, stage=None, allowed=()):
    path = work / "source-state.json"
    expected = json.loads(path.read_text())
    actual = snapshot(config, root)
    require(
        expected.get("schema") == 1
        and expected.get("sourceSha") == actual["sourceSha"]
        and set(expected.get("files", {})) == set(actual["files"]),
        "Prepared source identity changed",
    )
    changed = {
        name
        for name, value in actual["files"].items()
        if value != expected["files"][name]
    }
    require(
        changed <= set(allowed),
        "Source changed outside the authorized native preparation: "
        + ", ".join(sorted(changed - set(allowed))[:8]),
    )
    if changed:
        require(stage, "Source mutation requires a named native preparation step")
        expected["files"] = actual["files"]
        expected["transforms"].append({"stage": stage, "paths": sorted(changed)})
        path.write_text(json.dumps(expected, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_path(config):
    target = (
        "App/App.xcodeproj"
        if config["framework"] == "capacitor"
        else config["scheme"] + ".xcodeproj"
    )
    return config["mobilePath"] + "/ios/" + target + "/project.pbxproj"


def preparation_paths(config, platform, stage):
    mobile = config["mobilePath"] + "/"
    if stage == "native-sync":
        if config["framework"] == "capacitor":
            return (
                [
                    mobile + "android/app/capacitor.build.gradle",
                    mobile + "android/capacitor.settings.gradle",
                ]
                if platform == "android"
                else [mobile + "ios/App/CapApp-SPM/Package.swift"]
            )
        # Drone's existing generator replaces exactly its tracked placeholder.
        return (
            [mobile + platform + "/README.md"] if config.get("generatedNative") else []
        )
    if stage == "pods":
        require(platform == "ios", "CocoaPods preparation applies only to iOS")
        return [
            project_path(config),
            mobile + "ios/Podfile.lock",
            mobile
            + "ios/"
            + config["scheme"]
            + ".xcworkspace/contents.xcworkspacedata",
        ]
    require(stage == "verify", "Unknown native preparation checkpoint")
    return []
