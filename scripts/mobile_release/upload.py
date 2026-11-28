"""Existing-app uploads: Google Play internal only and existing internal TestFlight group.

Provider payloads and credentials are never logged. An ambiguous write is not retried.
"""

import base64
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from release import command, require, sha256

APPLE = "https://api.appstoreconnect.apple.com"
GOOGLE = "https://androidpublisher.googleapis.com"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(method, url, token=None, body=None, content_type="application/json"):
    parsed = urllib.parse.urlsplit(url)
    require(
        parsed.scheme == "https"
        and parsed.netloc
        in {
            "oauth2.googleapis.com",
            "androidpublisher.googleapis.com",
            "api.appstoreconnect.apple.com",
        }
        and not parsed.fragment,
        "Provider URL refused",
    )
    headers = {"Content-Type": content_type, "Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if body is not None and not isinstance(body, bytes):
        body = json.dumps(body, separators=(",", ":")).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=180) as response:
            payload = response.read(2 * 1024 * 1024 + 1)
            require(len(payload) <= 2 * 1024 * 1024, "Provider response exceeds bounds")
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as error:
        # Do not echo provider response: it can include account or credential data.
        raise ValueError(
            f"Provider {method} failed (HTTP {error.code}); inspect the provider console before retrying"
        ) from None
    except (urllib.error.URLError, TimeoutError):
        raise ValueError(
            "Provider response unknown; inspect the provider console before retrying this build"
        ) from None


def b64url(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def ecdsa_raw(der):
    """OpenSSL emits ASN.1 DER; JWT ES256 requires two fixed-width integers."""
    require(
        len(der) in range(68, 73)
        and der[0] == 0x30
        and der[1] == len(der) - 2
        and der[2] == 2,
        "Unexpected EC signature encoding",
    )
    size_r = der[3]
    end_r = 4 + size_r
    require(
        1 <= size_r <= 33 and end_r + 2 < len(der) and der[end_r] == 2,
        "Invalid EC signature",
    )
    size_s = der[end_r + 1]
    require(
        1 <= size_s <= 33 and end_r + 2 + size_s == len(der), "Invalid EC signature"
    )
    parts = (der[4:end_r], der[end_r + 2 :])
    require(
        all(int.from_bytes(part, "big") < 2**256 for part in parts),
        "Invalid ES256 integer",
    )
    return b"".join(int.from_bytes(part, "big").to_bytes(32, "big") for part in parts)


def jwt(header, claims, key, *, ec=False):
    unsigned = ".".join(
        b64url(json.dumps(v, separators=(",", ":")).encode()) for v in (header, claims)
    )
    signature = command(
        "openssl", "dgst", "-sha256", "-sign", key, data=unsigned.encode()
    )
    return unsigned + "." + b64url(ecdsa_raw(signature) if ec else signature)


def google_token(private):
    try:
        account = json.loads(os.environ["GOOGLE_PLAY_SERVICE_ACCOUNT_JSON"])
    except (ValueError, KeyError):
        raise ValueError("Malformed GOOGLE_PLAY_SERVICE_ACCOUNT_JSON") from None
    require(
        account.get("type") == "service_account"
        and account.get("token_uri") == "https://oauth2.googleapis.com/token"
        and re.fullmatch(
            r"[^\s@]+@[^\s@]+\.gserviceaccount\.com", account.get("client_email", "")
        ),
        "Use the existing Google Play service-account credential",
    )
    key = private / "google.pem"
    key.write_text(account["private_key"])
    key.chmod(0o600)
    now = int(time.time())
    assertion = jwt(
        {"alg": "RS256", "typ": "JWT"},
        {
            "iss": account["client_email"],
            "scope": "https://www.googleapis.com/auth/androidpublisher",
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now,
            "exp": now + 900,
        },
        key,
    )
    result = request(
        "POST",
        "https://oauth2.googleapis.com/token",
        body=urllib.parse.urlencode(
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            }
        ).encode(),
        content_type="application/x-www-form-urlencoded",
    )
    require(
        isinstance(result.get("access_token"), str)
        and result.get("token_type", "").lower() == "bearer",
        "Google did not issue an upload access token",
    )
    return result["access_token"]


def release_track(record):
    return {
        "track": "internal",
        "releases": [
            {
                "name": record["version"] + " (" + record["buildNumber"] + ")",
                "versionCodes": [record["buildNumber"]],
                "status": "completed",
            }
        ],
    }


def require_play_console_reviewed():
    # An edit commit can also submit unrelated Console changes ready for review.
    # This is a fresh operator observation for this dispatch, never a saved flag.
    require(
        os.environ.get("PLAY_CONSOLE_REVIEWED") == "true",
        "Google Play release blocked: play_console_reviewed must be explicitly true after checking "
        "this app has no unrelated ready-for-review changes or concurrent Console/API writer",
    )
    require(
        os.environ.get("GITHUB_RUN_ATTEMPT") == "1",
        "Google Play release blocked: GITHUB_RUN_ATTEMPT must be 1; inspect any previous outcome "
        "and make a new dispatch after a fresh Play Console check instead of re-running jobs",
    )


def upload_google(record, artifact, token, *, call=request):
    require_play_console_reviewed()
    base = (
        GOOGLE
        + "/androidpublisher/v3/applications/"
        + urllib.parse.quote(record["appId"], safe=".")
        + "/edits"
    )
    edit = call("POST", base, token, {})
    edit_id = edit.get("id", "")
    require(
        re.fullmatch(r"[A-Za-z0-9_-]{1,160}", edit_id), "Google edit identity missing"
    )
    url = base + "/" + edit_id
    committing = False
    try:
        # Reading existing tracks also rejects a wrong/inaccessible app. Existing
        # production/closed-track configuration is left untouched.
        tracks = call("GET", url + "/tracks", token)
        require(
            isinstance(tracks.get("tracks"), list),
            "Existing Play tracks could not be verified",
        )
        existing = [t for t in tracks["tracks"] if t.get("track") == "internal"]
        require(
            len(existing) == 1,
            "Existing Google Play internal track must be configured in Play Console first",
        )
        occupied = {
            str(v)
            for t in tracks["tracks"]
            for r in t.get("releases", [])
            for v in r.get("versionCodes", [])
        }
        require(
            record["buildNumber"] not in occupied,
            "Build number is already present in Google Play; do not re-upload it",
        )
        require(
            0 < artifact.stat().st_size <= 512 * 1024 * 1024,
            "Bundle size is outside upload bounds",
        )
        uploaded = call(
            "POST",
            GOOGLE
            + "/upload"
            + urllib.parse.urlsplit(url).path
            + "/bundles?uploadType=media",
            token,
            artifact.read_bytes(),
            "application/octet-stream",
        )
        require(
            str(uploaded.get("versionCode")) == record["buildNumber"]
            and uploaded.get("sha256", "").lower() == sha256(artifact),
            "Google uploaded bundle identity/hash differs",
        )
        desired = release_track(record)
        changed = call("PUT", url + "/tracks/internal", token, desired)
        require(
            changed.get("track") == "internal"
            and changed.get("releases") == desired["releases"],
            "Google internal track response differs",
        )
        call("POST", url + ":validate", token)
        committing = True
        # Do not cancel another release that is in review. No production promotion,
        # review-bypass fallback or automatic retry is permitted.
        committed = call(
            "POST", url + ":commit?changesInReviewBehavior=ERROR_IF_IN_REVIEW", token
        )
        require(
            committed.get("id") == edit_id,
            "Google commit receipt missing; inspect Play Console",
        )
        return {
            "distribution": "internal-track-committed",
            "editId": edit_id,
            "track": "internal",
        }
    finally:
        if not committing:
            try:
                call("DELETE", url, token)
            except ValueError:
                print(
                    "Uncommitted edit cleanup could not be confirmed; inspect Play Console."
                )


def apple_token(private):
    key = private / ("AuthKey_" + os.environ["APP_STORE_CONNECT_KEY_ID"] + ".p8")
    key.write_text(os.environ["APP_STORE_CONNECT_PRIVATE_KEY"])
    key.chmod(0o600)
    now = int(time.time())
    token = jwt(
        {"alg": "ES256", "kid": os.environ["APP_STORE_CONNECT_KEY_ID"], "typ": "JWT"},
        {
            "iss": os.environ["APP_STORE_CONNECT_ISSUER_ID"],
            "iat": now,
            "exp": now + 900,
            "aud": "appstoreconnect-v1",
        },
        key,
        ec=True,
    )
    return token, key


def verify_apple_destination(record, token, *, call=request):
    app_id, group_id = (
        os.environ["APP_STORE_CONNECT_APP_ID"],
        os.environ["APP_STORE_CONNECT_INTERNAL_GROUP_ID"],
    )
    app = call("GET", APPLE + "/v1/apps/" + app_id, token).get("data", {})
    require(
        app.get("id") == app_id
        and app.get("attributes", {}).get("bundleId") == record["appId"],
        "App Store Connect record differs from existing bundle ID",
    )
    group = call(
        "GET", APPLE + "/v1/betaGroups/" + group_id + "?include=app", token
    ).get("data", {})
    require(
        group.get("id") == group_id
        and group.get("attributes", {}).get("isInternalGroup") is True
        and group.get("relationships", {}).get("app", {}).get("data", {}).get("id")
        == app_id,
        "TestFlight destination must be an existing internal group for this app",
    )


def matching_apple_build(result, record):
    versions = {
        v["id"]: v.get("attributes", {})
        for v in result.get("included", [])
        if v.get("type") == "preReleaseVersions"
    }
    matching = []
    for build in result.get("data", []):
        version_id = (
            build.get("relationships", {})
            .get("preReleaseVersion", {})
            .get("data", {})
            .get("id")
        )
        pre = versions.get(version_id, {})
        attrs = build.get("attributes", {})
        if (
            attrs.get("version") == record["buildNumber"]
            and pre.get("version") == record["version"]
            and pre.get("platform") == "IOS"
        ):
            matching.append(build)
    require(len(matching) <= 1, "Ambiguous App Store Connect build identity")
    return matching[0] if matching else None


def upload_apple(record, artifact, private):
    token, key = apple_token(private)
    verify_apple_destination(record, token)
    query = urllib.parse.urlencode(
        {
            "filter[app]": os.environ["APP_STORE_CONNECT_APP_ID"],
            "filter[version]": record["buildNumber"],
            "include": "preReleaseVersion",
            "limit": "200",
        }
    )
    url = APPLE + "/v1/builds?" + query
    require(
        matching_apple_build(request("GET", url, token), record) is None,
        "This marketing version/build already exists in App Store Connect; inspect it instead of re-uploading",
    )
    # Modern Xcode altool reads an explicit private key path, not a user's home.
    # Validate before upload; both commands are bounded and no credential output is retained.
    help_text = command("xcrun", "altool", "--help").decode(errors="replace")
    require(
        "--p8-file-path" in help_text,
        "Installed altool lacks explicit API key-path support; update the pinned runner toolchain",
    )
    auth = (
        "--apiKey",
        os.environ["APP_STORE_CONNECT_KEY_ID"],
        "--apiIssuer",
        os.environ["APP_STORE_CONNECT_ISSUER_ID"],
        "--p8-file-path",
        key,
    )
    command(
        "xcrun",
        "altool",
        "--validate-app",
        "-f",
        artifact,
        "-t",
        "ios",
        *auth,
        timeout=900,
    )
    try:
        command(
            "xcrun",
            "altool",
            "--upload-app",
            "-f",
            artifact,
            "-t",
            "ios",
            *auth,
            timeout=1800,
        )
    except (ValueError, OSError, subprocess.SubprocessError, KeyboardInterrupt):
        # A nonzero exit, interruption or missing response does not establish that
        # Apple rejected the upload. Retain the unknown receipt; never retry here.
        raise ValueError(
            "Apple upload response unknown; inspect this exact marketing version/build in App Store Connect before another dispatch"
        ) from None
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        token, _ = apple_token(private)
        build = matching_apple_build(request("GET", url, token), record)
        if build:
            state = build["attributes"].get("processingState")
            require(
                state not in {"FAILED", "INVALID"},
                "Apple rejected processing; inspect App Store Connect",
            )
            if state == "VALID":
                require(
                    build["attributes"].get("expired") is False,
                    "Apple build is expired",
                )
                verify_apple_destination(record, token)
                request(
                    "POST",
                    APPLE
                    + "/v1/betaGroups/"
                    + os.environ["APP_STORE_CONNECT_INTERNAL_GROUP_ID"]
                    + "/relationships/builds",
                    token,
                    {"data": [{"type": "builds", "id": build["id"]}]},
                )
                return {
                    "distribution": "internal-testflight-assigned",
                    "buildId": build["id"],
                    "appStoreConnectAppId": os.environ["APP_STORE_CONNECT_APP_ID"],
                    "internalGroupId": os.environ[
                        "APP_STORE_CONNECT_INTERNAL_GROUP_ID"
                    ],
                }
        time.sleep(30)
    raise ValueError(
        "Upload accepted but Apple processing remains pending; inspect this build before another dispatch"
    )


def upload(config, record, platform, work, *, source_digest):
    if platform == "android":
        # Refuse before OAuth, provider requests, or marking an upload as started.
        require_play_console_reviewed()
    artifacts = work / "artifacts"
    receipt_file = artifacts / "receipt.json"
    receipt = json.loads(receipt_file.read_text())
    artifact = artifacts / ("upload.aab" if platform == "android" else "upload.ipa")
    require(
        all(receipt.get(key) == record[key] for key in record)
        and receipt.get("platform") == platform
        and receipt.get("artifactSha256") == sha256(artifact)
        and re.fullmatch(r"[0-9a-f]{64}", source_digest or "")
        and receipt.get("preparedSourceSha256") == source_digest
        and receipt.get("distribution") == "signed-not-uploaded",
        "Signed artifact/receipt changed before upload",
    )
    with tempfile.TemporaryDirectory(
        prefix="provider-credential-", dir=work
    ) as directory:
        private = Path(directory)
        receipt["distribution"] = "upload-started-outcome-unknown"
        receipt_file.write_text(json.dumps(receipt, indent=2) + "\n")
        result = (
            upload_google(record, artifact, google_token(private))
            if platform == "android"
            else upload_apple(record, artifact, private)
        )
    receipt.update(result)
    receipt_file.write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        result["distribution"],
        record["appId"],
        record["version"],
        "build",
        record["buildNumber"],
    )
