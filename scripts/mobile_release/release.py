"""Internal mobile release contract. No credentials or provider operations in tests.

Each product owns this helper locally; there are no cross-repository runtime imports.
Only workflow_dispatch on the exact reviewed main commit may publish.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import importlib
import json
import os
import plistlib
import re
import secrets
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import urllib.parse
import zipfile
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

sys.dont_write_bytecode = True
# Load local helpers only after disabling bytecode writes: the source guard must
# not create untracked files in the checkout it verifies.
ci_gate = importlib.import_module("ci_gate")
source_guard = importlib.import_module("source_guard")

ROOT = Path(__file__).resolve().parents[2]
SECRET_NAMES = {
    "android": (
        "ANDROID_PLAY_UPLOAD_KEYSTORE_BASE64",
        "ANDROID_PLAY_UPLOAD_STORE_PASSWORD",
        "ANDROID_PLAY_UPLOAD_KEY_PASSWORD",
        "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON",
    ),
    "ios": (
        "APPLE_DISTRIBUTION_P12_BASE64",
        "APPLE_DISTRIBUTION_P12_PASSWORD",
        "APPLE_PROVISIONING_PROFILE_BASE64",
        "APP_STORE_CONNECT_PRIVATE_KEY",
    ),
}
VARIABLE_NAMES = {
    "android": ("ANDROID_PLAY_UPLOAD_ALIAS", "ANDROID_PLAY_UPLOAD_CERT_SHA256"),
    "ios": (
        "APPLE_TEAM_ID",
        "APPLE_DISTRIBUTION_CERT_SHA256",
        "APP_STORE_CONNECT_KEY_ID",
        "APP_STORE_CONNECT_ISSUER_ID",
        "APP_STORE_CONNECT_APP_ID",
        "APP_STORE_CONNECT_INTERNAL_GROUP_ID",
    ),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def command(*args, cwd=None, data=None, env=None, quiet=True, timeout=180):
    """Never include secret-bearing command arguments or tool output in exceptions."""
    result = subprocess.run(
        [str(x) for x in args],
        cwd=cwd,
        input=data,
        env=env,
        stdout=subprocess.PIPE if quiet else None,
        stderr=subprocess.PIPE if quiet else None,
        timeout=timeout,
        check=False,
    )
    require(
        result.returncode == 0,
        f"{Path(str(args[0])).name} failed (exit {result.returncode})",
    )
    return result.stdout or b""


def public_environment():
    names = {name for values in SECRET_NAMES.values() for name in values}
    return {
        k: v for k, v in os.environ.items() if k not in names and k != "GITHUB_TOKEN"
    }


def load_config(root=ROOT):
    value = json.loads((root / ".github/mobile-release.json").read_text())
    require(
        value.get("schema") == 1
        and re.fullmatch(r"DruHustle/[a-z0-9-]+", value.get("repository", "")),
        "Invalid release repository contract",
    )
    require(
        value.get("framework") in {"expo", "capacitor"}, "Unsupported native framework"
    )
    require(
        re.fullmatch(r"[A-Za-z0-9]+(?:\.[A-Za-z0-9]+){2,}", value.get("appId", "")),
        "Invalid existing app ID",
    )
    for key in ("mobilePath", "xcodeContainer"):
        path = Path(value.get(key, ""))
        require(
            str(path) not in {"", "."}
            and not path.is_absolute()
            and ".." not in path.parts,
            "Release paths must stay inside this repository",
        )
    require(
        re.fullmatch(r"[A-Za-z0-9]+", value.get("scheme", "")),
        "Invalid existing Xcode scheme",
    )
    require(
        value.get("xcodeKind") in {"workspace", "project"}, "Invalid Xcode container"
    )
    ci_gate.required_checks(value)
    return value


def source_version(config, root=ROOT):
    mobile = root / config["mobilePath"]
    if config["framework"] == "expo":
        expo = json.loads((mobile / "app.json").read_text())["expo"]
        require(
            expo["android"]["package"]
            == config["appId"]
            == expo["ios"]["bundleIdentifier"],
            "Existing Expo identifiers differ from the release contract",
        )
        version = expo["version"]
    else:
        gradle = (mobile / "android/app/build.gradle").read_text()
        require(
            re.search(r'applicationId\s+"' + re.escape(config["appId"]) + '"', gradle),
            "Existing Android identifier differs from the release contract",
        )
        versions = re.findall(r'versionName\s+"([^"]+)"', gradle)
        require(len(versions) == 1, "Expected one committed marketing version")
        version = versions[0]
    require(
        re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version),
        "Use a committed three-part store marketing version",
    )
    return version


def build_number(value):
    require(
        isinstance(value, str)
        and re.fullmatch(r"[1-9][0-9]{0,9}", value)
        and int(value) <= 2100000000,
        "build_number must be an explicit positive store counter <= 2100000000",
    )
    return value


def fingerprint(value):
    normalized = value.replace(":", "").lower()
    require(
        re.fullmatch(r"[0-9a-f]{64}", normalized),
        "Expected an independently verified SHA-256 signing fingerprint",
    )
    return normalized


def preflight(platform, env=os.environ):
    missing = [
        key
        for key in SECRET_NAMES[platform] + VARIABLE_NAMES[platform]
        if not env.get(key, "").strip()
    ]
    require(
        not missing, "Missing protected mobile-internal inputs: " + ", ".join(missing)
    )
    if platform == "android":
        fingerprint(env["ANDROID_PLAY_UPLOAD_CERT_SHA256"])
        require(
            re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", env["ANDROID_PLAY_UPLOAD_ALIAS"]),
            "Invalid upload-key alias",
        )
    else:
        fingerprint(env["APPLE_DISTRIBUTION_CERT_SHA256"])
        require(
            re.fullmatch(r"[A-Z0-9]{10}", env["APPLE_TEAM_ID"]), "Invalid Apple team ID"
        )
        require(
            re.fullmatch(r"[A-Z0-9]{10}", env["APP_STORE_CONNECT_KEY_ID"]),
            "Invalid App Store Connect key ID",
        )
        require(
            re.fullmatch(r"[0-9]+", env["APP_STORE_CONNECT_APP_ID"]),
            "Invalid existing App Store Connect app ID",
        )
        for key in (
            "APP_STORE_CONNECT_ISSUER_ID",
            "APP_STORE_CONNECT_INTERNAL_GROUP_ID",
        ):
            require(re.fullmatch(r"[0-9a-fA-F-]{36}", env[key]), "Invalid " + key)


def check_source(config, expected, root=ROOT, env=os.environ, *, work=None):
    require(
        env.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and env.get("GITHUB_REF") == "refs/heads/main"
        and env.get("GITHUB_REPOSITORY") == config["repository"],
        "Publishing requires the canonical repository main dispatch",
    )
    require(
        re.fullmatch(r"[0-9a-f]{40}", expected or ""),
        "Provide the reviewed full source_sha",
    )
    local = command("git", "rev-parse", "HEAD", cwd=root).decode().strip()
    require(
        local == expected == env.get("GITHUB_SHA"),
        "Workflow, checkout and reviewed source SHA differ",
    )
    if work is None:
        require(
            not command(
                "git", "status", "--porcelain", "--untracked-files=no", cwd=root
            ).strip(),
            "Tracked source is not clean",
        )
    else:
        source_guard.verify(config, work, root)
    remote = (
        command("git", "ls-remote", "origin", "refs/heads/main", cwd=root)
        .decode()
        .split()
    )
    require(
        len(remote) == 2 and remote[0] == expected,
        "Reviewed source is no longer current main",
    )
    ci_gate.verify(config, expected, env)


def write_context(config, work, number):
    work.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": 1,
        "repository": config["repository"],
        "appId": config["appId"],
        "sourceSha": command("git", "rev-parse", "HEAD", cwd=ROOT).decode().strip(),
        "version": source_version(config),
        "buildNumber": build_number(number),
    }
    source_guard.initialize(config, work, ROOT)
    (work / "context.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def read_context(config, work):
    record = json.loads((work / "context.json").read_text())
    require(
        record["appId"] == config["appId"]
        and record["repository"] == config["repository"]
        and record["sourceSha"] == os.environ.get("GITHUB_SHA"),
        "Build context differs from the workflow",
    )
    build_number(record["buildNumber"])
    require(
        record["version"] == source_version(config),
        "Marketing version changed during packaging",
    )
    return record


def stamp_native(config, record, platform, root=ROOT, *, work=None):
    """Only the disposable runner checkout is stamped; marketing version is preserved."""
    mobile = root / config["mobilePath"]
    if work is not None:
        source_guard.verify(config, work, root)
    changed_paths = []
    if platform == "android":
        path = mobile / "android/app/build.gradle"
        original = path.read_text()
        changed, count = re.subn(
            r"(?m)^(\s*versionCode\s+)\d+\s*$",
            lambda m: m[1] + record["buildNumber"],
            original,
        )
        require(count == 1, "Expected exactly one native Android build counter")
        require(
            re.search(r'versionName\s+"' + re.escape(record["version"]) + '"', changed),
            "Native marketing version differs",
        )
        path.write_text(changed)
    else:
        candidates = [
            p
            for p in (mobile / "ios").glob("*/Info.plist")
            if p.parent.name == config["scheme"]
        ]
        if config["framework"] == "capacitor":
            candidates = [mobile / "ios/App/App/Info.plist"]
        require(
            len(candidates) == 1 and candidates[0].is_file(),
            "Expected one native app Info.plist",
        )
        path = candidates[0]
        value = plistlib.loads(path.read_bytes())
        value["CFBundleVersion"] = record["buildNumber"]
        value["CFBundleShortVersionString"] = record["version"]
        path.write_bytes(plistlib.dumps(value))
    changed_paths.append(path.relative_to(root).as_posix())
    if config["framework"] == "expo":
        path = mobile / "app.json"
        value = json.loads(path.read_text())
        value["expo"]["ios"]["buildNumber"] = record["buildNumber"]
        value["expo"]["android"]["versionCode"] = int(record["buildNumber"])
        path.write_text(json.dumps(value, indent=2) + "\n")
        changed_paths.append(path.relative_to(root).as_posix())
    if work is not None:
        source_guard.verify(
            config, work, root, stage="build-counter", allowed=changed_paths
        )


def decode_secret(name, target, maximum=32 * 1024 * 1024):
    value = os.environ.get(name, "")
    require(0 < len(value) <= maximum * 2, "Missing or oversized " + name)
    try:
        data = base64.b64decode("".join(value.split()), validate=True)
    except ValueError:
        raise ValueError("Malformed base64 in " + name) from None
    require(0 < len(data) <= maximum, "Empty or oversized " + name)
    target.write_bytes(data)
    target.chmod(0o600)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class _ScriptSources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            source = dict(attrs).get("src")
            if source:
                self.sources.append(source)


def validate_capacitor_payload(config, names, read, *, prefix=""):
    """Check the packaged app, not the pre-sync development directory."""

    def required(name):
        path = prefix + name
        require(path in names, "Standalone customer payload missing: " + name)
        value = read(path)
        require(bool(value), "Standalone customer payload is empty: " + name)
        return value

    embedded = json.loads(required("capacitor.config.json"))
    require(
        isinstance(embedded, dict) and embedded.get("appId") == config["appId"],
        "Embedded customer app ID differs",
    )
    plugins = embedded.get("plugins", {})
    customer = plugins.get("PasoFiCustomerApi", {}) if isinstance(plugins, dict) else {}
    require(
        isinstance(customer, dict)
        and customer.get("origin") == "https://pasofi.mobile.onesa.eu",
        "Embedded customer origin differs",
    )
    server = embedded.get("server", {})
    require(
        isinstance(server, dict) and not server.get("url"),
        "Release must use bundled customer assets",
    )
    parser = _ScriptSources()
    parser.feed(required("public/index.html").decode("utf-8"))
    require(parser.sources, "Standalone customer JavaScript entry missing")
    for source in parser.sources:
        url = urllib.parse.urlsplit(source)
        relative = url.path.removeprefix("./").lstrip("/")
        require(
            not (url.scheme or url.netloc or url.query or url.fragment)
            and relative.startswith("assets/")
            and relative.endswith(".js")
            and ".." not in PurePosixPath(relative).parts,
            "Customer JavaScript entry must be a bundled asset",
        )
        required("public/" + relative)


def inspect_ios_payload(app, config):
    if config["framework"] == "expo":
        require(
            (app / "main.jsbundle").is_file()
            and (app / "main.jsbundle").stat().st_size > 0,
            "Standalone JavaScript missing",
        )
    else:
        names = {
            path.relative_to(app).as_posix()
            for path in app.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        validate_capacitor_payload(
            config, names, lambda name: (app / name).read_bytes()
        )


def inspect_aab(bundle, config, record, *, unsigned=False):
    tool = os.environ["BUNDLETOOL_JAR"]
    command("java", "-jar", tool, "validate", "--bundle=" + str(bundle))
    manifest = ET.fromstring(
        command(
            "java",
            "-jar",
            tool,
            "dump",
            "manifest",
            "--bundle=" + str(bundle),
            "--module=base",
        )
    )
    key = "{http://schemas.android.com/apk/res/android}"
    app, sdk = manifest.find("application"), manifest.find("uses-sdk")
    require(
        manifest.get("package") == config["appId"]
        and manifest.get(key + "versionName") == record["version"]
        and manifest.get(key + "versionCode") == record["buildNumber"],
        "Packaged Android identity/version differs",
    )
    require(
        app is not None
        and app.get(key + "debuggable") != "true"
        and sdk is not None
        and int(sdk.get(key + "targetSdkVersion", "0")) >= 36,
        "Release bundle must be nondebuggable and target API 36 or later",
    )
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "Duplicate bundle members refused")
        if unsigned:
            require(
                not any(
                    re.fullmatch(
                        r"META-INF/(?:[^/]+\.(?:SF|RSA|DSA|EC)|SIG-[^/]+)",
                        n,
                        re.IGNORECASE,
                    )
                    for n in names
                ),
                "Release input must be unsigned; debug-signed inputs are refused",
            )
        if config["framework"] == "capacitor":
            validate_capacitor_payload(
                config, set(names), archive.read, prefix="base/assets/"
            )
        else:
            require(
                "base/assets/index.android.bundle" in names,
                "Standalone JavaScript missing",
            )
            expo = json.loads((ROOT / config["mobilePath"] / "app.json").read_text())[
                "expo"
            ]
            permissions = {
                n.get(key + "name") for n in manifest.findall("uses-permission")
            }
            require(
                not set(expo["android"].get("blockedPermissions", [])) & permissions,
                "Blocked native permission packaged",
            )
            libraries = [
                n for n in names if re.fullmatch(r"base/lib/arm64-v8a/[^/]+\.so", n)
            ]
            require(libraries, "ARM64 native payload missing")
            for name in libraries:
                data = archive.read(name)
                require(
                    len(data) >= 64 and data[:6] == b"\x7fELF\x02\x01",
                    "Unexpected ARM64 native binary",
                )
                offset = struct.unpack_from("<Q", data, 32)[0]
                stride, count = struct.unpack_from("<HH", data, 54)
                require(
                    stride >= 56
                    and count <= 4096
                    and offset + stride * count <= len(data),
                    "Malformed ELF program table",
                )
                for index in range(count):
                    start = offset + stride * index
                    require(
                        struct.unpack_from("<I", data, start)[0] != 1
                        or struct.unpack_from("<Q", data, start + 48)[0] >= 16384,
                        "Native library lacks 16 KB load alignment",
                    )


def sign_android(config, record, work):
    source_guard.verify(config, work, ROOT)
    source = (
        ROOT
        / config["mobilePath"]
        / "android/app/build/outputs/bundle/release/app-release.aab"
    )
    destination = work / "artifacts/upload.aab"
    destination.parent.mkdir(parents=True, exist_ok=True)
    require(not destination.exists(), "Release artifact already exists")
    inspect_aab(source, config, record, unsigned=True)
    expected = fingerprint(os.environ["ANDROID_PLAY_UPLOAD_CERT_SHA256"])
    with tempfile.TemporaryDirectory(prefix="android-signing-", dir=work) as directory:
        private = Path(directory)
        keystore = private / "upload.keystore"
        decode_secret("ANDROID_PLAY_UPLOAD_KEYSTORE_BASE64", keystore)
        alias = os.environ["ANDROID_PLAY_UPLOAD_ALIAS"]
        leaf = command(
            "keytool",
            "-exportcert",
            "-keystore",
            keystore,
            "-alias",
            alias,
            "-storepass:env",
            "ANDROID_PLAY_UPLOAD_STORE_PASSWORD",
        )
        require(
            hashlib.sha256(leaf).hexdigest() == expected,
            "Keystore differs from registered Play upload certificate",
        )
        subject = command(
            "openssl",
            "x509",
            "-inform",
            "DER",
            "-noout",
            "-subject",
            "-nameopt",
            "RFC2253",
            data=leaf,
        )
        require(
            not re.search(
                rb"(?:subject=|,)CN=Android Debug(?:,|$)",
                subject.strip(),
                re.IGNORECASE,
            ),
            "Debug signing identity refused",
        )
        signed = private / "signed.aab"
        command(
            "jarsigner",
            "-keystore",
            keystore,
            "-storepass:env",
            "ANDROID_PLAY_UPLOAD_STORE_PASSWORD",
            "-keypass:env",
            "ANDROID_PLAY_UPLOAD_KEY_PASSWORD",
            "-signedjar",
            signed,
            source,
            alias,
        )
        certificates = command(
            "keytool", "-J-Duser.language=en", "-printcert", "-rfc", "-jarfile", signed
        )
        require(
            len(re.findall(rb"^Signer #[0-9]+:", certificates, re.MULTILINE)) == 1,
            "Expected exactly one bundle signer",
        )
        signer = command("openssl", "x509", "-outform", "DER", data=certificates)
        require(
            hashlib.sha256(signer).hexdigest() == expected,
            "Signed bundle certificate differs",
        )
        trust = private / "verification.p12"
        command(
            "keytool",
            "-importcert",
            "-noprompt",
            "-keystore",
            trust,
            "-storepass",
            "public-certs",
            "-alias",
            "upload",
            data=leaf,
        )
        command(
            "jarsigner",
            "-verify",
            "-strict",
            "-keystore",
            trust,
            "-storepass",
            "public-certs",
            signed,
            "upload",
        )
        inspect_aab(signed, config, record)
        shutil.copyfile(signed, destination)
    receipt = {
        **record,
        "platform": "android",
        "artifactSha256": sha256(destination),
        "signerSha256": expected,
        "preparedSourceSha256": source_guard.verify(config, work, ROOT),
        "distribution": "signed-not-uploaded",
    }
    (destination.parent / "receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )


def validate_profile(profile, config, team, expected_cert, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    expiration = profile.get("ExpirationDate")
    require(isinstance(expiration, dt.datetime), "Profile expiration missing")
    if expiration.tzinfo is None:
        expiration = expiration.replace(tzinfo=dt.timezone.utc)
    entitlements = profile.get("Entitlements", {})
    app_id = entitlements.get("application-identifier", "")
    require(
        expiration > now
        and profile.get("TeamIdentifier") == [team]
        and entitlements.get("com.apple.developer.team-identifier") == team,
        "Profile is expired or belongs to another Apple team",
    )
    require(
        app_id.partition(".")[2] == config["appId"] and "*" not in app_id,
        "Provisioning profile must name the exact existing app",
    )
    require(
        not profile.get("ProvisionedDevices")
        and not profile.get("ProvisionsAllDevices")
        and entitlements.get("get-task-allow") is False,
        "App Store distribution profile required",
    )
    require(
        expected_cert
        in {
            hashlib.sha256(cert).hexdigest()
            for cert in profile.get("DeveloperCertificates", [])
        },
        "Profile does not contain the pinned distribution certificate",
    )
    require(
        re.fullmatch(r"[0-9a-fA-F-]{36}", profile.get("UUID", "")),
        "Invalid profile UUID",
    )
    return app_id


def validate_ios_info(info, config, record):
    require(
        info.get("CFBundleIdentifier") == config["appId"]
        and str(info.get("CFBundleVersion")) == record["buildNumber"]
        and info.get("CFBundleShortVersionString") == record["version"],
        "Packaged iOS identity/version differs",
    )
    require(
        info.get("CFBundleSupportedPlatforms") == ["iPhoneOS"]
        and info.get("DTPlatformName") == "iphoneos"
        and int(str(info.get("DTXcode", "0"))) >= 2600,
        "Expected an iPhoneOS build made with Xcode 26 or later",
    )


def sign_ios(config, record, work):
    source_guard.verify(config, work, ROOT)
    team = os.environ["APPLE_TEAM_ID"]
    expected = fingerprint(os.environ["APPLE_DISTRIBUTION_CERT_SHA256"])
    mobile = ROOT / config["mobilePath"]
    artifacts = work / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    require(not list(artifacts.iterdir()), "Use an empty release artifact directory")
    original_keychains = shlex.split(
        command("security", "list-keychains", "-d", "user").decode()
    )
    installed_profile = None
    with tempfile.TemporaryDirectory(prefix="apple-signing-", dir=work) as directory:
        private = Path(directory)
        keychain = private / "release.keychain-db"
        created_keychain = False
        try:
            p12, profile_file = (
                private / "identity.p12",
                private / "profile.mobileprovision",
            )
            decode_secret("APPLE_DISTRIBUTION_P12_BASE64", p12)
            decode_secret("APPLE_PROVISIONING_PROFILE_BASE64", profile_file)
            profile = plistlib.loads(
                command("security", "cms", "-D", "-i", profile_file)
            )
            application_id = validate_profile(profile, config, team, expected)
            password = secrets.token_urlsafe(32)
            command("security", "create-keychain", "-p", password, keychain)
            created_keychain = True
            command("security", "set-keychain-settings", "-lut", "21600", keychain)
            command("security", "unlock-keychain", "-p", password, keychain)
            command(
                "security",
                "import",
                p12,
                "-k",
                keychain,
                "-P",
                os.environ["APPLE_DISTRIBUTION_P12_PASSWORD"],
                "-T",
                "/usr/bin/codesign",
                "-T",
                "/usr/bin/security",
            )
            command(
                "security",
                "set-key-partition-list",
                "-S",
                "apple-tool:,apple:",
                "-s",
                "-k",
                password,
                keychain,
            )
            certificates = command("security", "find-certificate", "-a", "-p", keychain)
            leaf = None
            for pem in re.findall(
                rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
                certificates,
                re.DOTALL,
            ):
                der = command("openssl", "x509", "-outform", "DER", data=pem)
                if hashlib.sha256(der).hexdigest() == expected:
                    leaf = der
            require(
                leaf is not None, "P12 does not contain the pinned Apple certificate"
            )
            leaf_sha1 = hashlib.sha1(leaf).hexdigest().upper()
            identities = command(
                "security", "find-identity", "-v", "-p", "codesigning", keychain
            ).decode()
            require(
                re.search(
                    re.escape(leaf_sha1)
                    + r'\s+"(?:Apple Distribution|iPhone Distribution):',
                    identities,
                ),
                "Pinned identity is not a usable Apple distribution private key",
            )
            command(
                "security",
                "list-keychains",
                "-d",
                "user",
                "-s",
                keychain,
                *original_keychains,
            )
            profiles = Path.home() / "Library/MobileDevice/Provisioning Profiles"
            profiles.mkdir(parents=True, exist_ok=True)
            target_profile = profiles / (profile["UUID"] + ".mobileprovision")
            require(
                not target_profile.exists(),
                "Runner already has this provisioning profile; refusing to overwrite it",
            )
            shutil.copyfile(profile_file, target_profile)
            installed_profile = target_profile
            archive, export = private / "App.xcarchive", private / "export"
            # Pass signing configuration only to the app target. Applying a profile
            # as a global xcodebuild flag incorrectly forces it onto CocoaPods.
            project = (
                mobile
                / "ios"
                / (
                    "App/App.xcodeproj"
                    if config["framework"] == "capacitor"
                    else config["scheme"] + ".xcodeproj"
                )
            )
            ruby = """require 'xcodeproj'; p=Xcodeproj::Project.open(ARGV[0]); found=0
p.targets.each do |t|
 next unless t.product_type == 'com.apple.product-type.application'
 found+=1
 t.build_configurations.each do |c|
  c.build_settings['CODE_SIGN_STYLE']='Manual'
  c.build_settings['DEVELOPMENT_TEAM']=ARGV[1]
  c.build_settings['CODE_SIGN_IDENTITY']=ARGV[2]
  c.build_settings['PROVISIONING_PROFILE_SPECIFIER']=ARGV[3]
 end
end
abort 'Expected one app target' unless found == 1
p.save
"""
            source_guard.verify(config, work, ROOT)
            command("ruby", "-e", ruby, project, team, leaf_sha1, profile["UUID"])
            source_guard.verify(
                config,
                work,
                ROOT,
                stage="app-target-signing",
                allowed=[source_guard.project_path(config)],
            )
            command(
                "xcodebuild",
                "-" + config["xcodeKind"],
                config["xcodeContainer"],
                "-scheme",
                config["scheme"],
                "-configuration",
                "Release",
                "-sdk",
                "iphoneos",
                "-destination",
                "generic/platform=iOS",
                "-archivePath",
                archive,
                "CURRENT_PROJECT_VERSION=" + record["buildNumber"],
                "MARKETING_VERSION=" + record["version"],
                "archive",
                cwd=mobile,
                env=public_environment(),
                quiet=False,
                timeout=5400,
            )
            options = {
                "method": "app-store-connect",
                "destination": "export",
                "teamID": team,
                "signingStyle": "manual",
                "signingCertificate": leaf_sha1,
                "provisioningProfiles": {config["appId"]: profile["UUID"]},
                "manageAppVersionAndBuildNumber": False,
            }
            (private / "ExportOptions.plist").write_bytes(plistlib.dumps(options))
            command(
                "xcodebuild",
                "-exportArchive",
                "-archivePath",
                archive,
                "-exportPath",
                export,
                "-exportOptionsPlist",
                private / "ExportOptions.plist",
                env=public_environment(),
                quiet=False,
                timeout=1800,
            )
            packages = list(export.glob("*.ipa"))
            require(len(packages) == 1, "Expected one exported IPA")
            unpacked = private / "unpacked"
            command("ditto", "-x", "-k", packages[0], unpacked)
            apps = list((unpacked / "Payload").glob("*.app"))
            require(len(apps) == 1, "Expected one iOS app")
            app = apps[0]
            info = plistlib.loads((app / "Info.plist").read_bytes())
            validate_ios_info(info, config, record)
            command("codesign", "--verify", "--deep", "--strict", app)
            entitlements = plistlib.loads(
                command("codesign", "-d", "--entitlements", ":-", app)
            )
            require(
                entitlements.get("application-identifier") == application_id
                and entitlements.get("com.apple.developer.team-identifier") == team
                and entitlements.get("get-task-allow") is False,
                "Exported distribution entitlements differ",
            )
            command(
                "codesign", "-d", "--extract-certificates", str(private / "signer"), app
            )
            require(
                sha256(private / "signer0") == expected,
                "Exported IPA signer differs from pinned certificate",
            )
            binary = app / info["CFBundleExecutable"]
            command("xcrun", "lipo", binary, "-verify_arch", "arm64")
            require(
                re.search(
                    rb"platform\s+(IOS|2)\s*$",
                    command("xcrun", "vtool", "-show-build", binary),
                    re.MULTILINE,
                ),
                "Native executable is not iPhoneOS",
            )
            inspect_ios_payload(app, config)
            shutil.copyfile(packages[0], artifacts / "upload.ipa")
            receipt = {
                **record,
                "platform": "ios",
                "artifactSha256": sha256(artifacts / "upload.ipa"),
                "preparedSourceSha256": source_guard.verify(config, work, ROOT),
                "signerSha256": expected,
                "teamId": team,
                "distribution": "signed-not-uploaded",
            }
            (artifacts / "receipt.json").write_text(
                json.dumps(receipt, indent=2) + "\n"
            )
        finally:
            if installed_profile:
                installed_profile.unlink(missing_ok=True)
            if created_keychain:
                try:
                    command(
                        "security",
                        "list-keychains",
                        "-d",
                        "user",
                        "-s",
                        *original_keychains,
                    )
                finally:
                    command("security", "delete-keychain", keychain)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "contract",
            "source",
            "preflight",
            "context",
            "checkpoint",
            "stamp",
            "sign",
            "upload",
        ),
    )
    parser.add_argument("--platform", choices=("android", "ios"))
    parser.add_argument("--work", type=Path)
    parser.add_argument("--build-number")
    parser.add_argument("--source-sha")
    parser.add_argument(
        "--stage", choices=("verify", "native-sync", "pods"), default="verify"
    )
    args = parser.parse_args()
    config = load_config()
    if args.command == "contract":
        print(config["repository"], config["appId"], source_version(config))
    elif args.command == "source":
        check_source(config, args.source_sha)
        build_number(args.build_number)
    elif args.command == "preflight":
        preflight(args.platform)
        print(
            "Protected signing/upload input names are present; provider acceptance remains separate."
        )
    elif args.command == "context":
        write_context(config, args.work, args.build_number)
    else:
        record = read_context(config, args.work)
        if args.command == "checkpoint":
            source_guard.verify(
                config,
                args.work,
                ROOT,
                stage=args.stage,
                allowed=source_guard.preparation_paths(
                    config, args.platform, args.stage
                ),
            )
        elif args.command == "stamp":
            stamp_native(config, record, args.platform, work=args.work)
        elif args.command == "sign":
            (sign_android if args.platform == "android" else sign_ios)(
                config, record, args.work
            )
        else:
            from upload import upload

            # Verify all tracked source against the initial snapshot and only the
            # recorded, narrowly scoped native transformations before publishing.
            check_source(config, record["sourceSha"], work=args.work)
            upload(
                config,
                record,
                args.platform,
                args.work,
                source_digest=source_guard.verify(config, args.work, ROOT),
            )


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        main()
    except (
        ValueError,
        KeyError,
        OSError,
        subprocess.SubprocessError,
        KeyboardInterrupt,
    ) as error:
        # No traceback, arguments, provider payloads or credentials in CI logs.
        message = (
            str(error)
            if isinstance(error, ValueError)
            else type(error).__name__
            + ": release stopped; inspect the named prerequisite"
        )
        print("Release blocked: " + message, file=sys.stderr)
        sys.exit(1)
