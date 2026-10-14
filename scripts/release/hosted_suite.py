"""Hosted release probes using owner-provisioned synthetic staging accounts only.

No database access or destructive operations. Created fixtures remain in staging
where the application has no deletion API; their IDs are kept only in the report.
"""

import base64
import hashlib
import hmac
import http.cookiejar
import io
import json
import os
import re
import secrets
import struct
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from evidence import PRODUCT, REPOSITORY, Rejected, require
from fixtures import FixtureError, decode_totp, parse_fixtures
from hosted import NoRedirect, preview_origin, request

PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/Z1sAAAAASUVORK5CYII="


class HostedRequestFailure(Rejected):
    def __init__(self, status, path, body):
        self.phase = {
            "/api/v1/auth/login": "login",
            "/api/v1/auth/me": "current-user",
        }.get(path, "workflow-request")
        self.code = "HTTP_" + str(status)
        try:
            candidate = json.loads(body).get("error", {}).get("code")
        except (ValueError, AttributeError, TypeError):
            candidate = None
        known = {
            "CREDENTIALS": "FIXTURE_CREDENTIALS_REJECTED",
            "MFA": "FIXTURE_MFA_REJECTED",
            "origin_rejected": "ORIGIN_REJECTED",
            "invitation_required": "INVITATION_REQUIRED",
        }
        if isinstance(candidate, str) and candidate in known:
            self.code = known[candidate]
        super().__init__(self.code)


class HostedStreamFailure(Rejected):
    def __init__(self, code, reason=None, provider_error_code=None):
        known = {
            "inference_unavailable": "INFERENCE_UNAVAILABLE",
            "inference_timeout": "INFERENCE_TIMEOUT",
            "generation_failed": "GENERATION_FAILED",
            "model_not_available": "MODEL_NOT_AVAILABLE",
            "invalid_inference_response": "INVALID_INFERENCE_RESPONSE",
        }
        self.code = (
            known.get(code, "UNCLASSIFIED_STREAM_ERROR")
            if isinstance(code, str)
            else "UNCLASSIFIED_STREAM_ERROR"
        )
        known_reasons = {
            "provider_stream_error",
            "invalid_stream_json",
            "invalid_stream_shape",
            "invalid_stream_delta",
            "stream_terminated_early",
            "empty_model_response",
            "response_size_limit",
            "generation_lease_lost",
        }
        self.reason = (
            reason if isinstance(reason, str) and reason in known_reasons else None
        )
        self.provider_error_code = (
            provider_error_code
            if type(provider_error_code) is int and 0 <= provider_error_code <= 999999
            else None
        )
        super().__init__("Hosted stream emitted an error")


def safe_suite_failure_reason(error):
    if isinstance(error, HostedStreamFailure):
        if error.reason:
            return "STREAM_DETAIL_" + error.reason.upper()
        return "STREAM_ERROR_" + error.code
    known = {
        "Real streamed inference missing": "STREAM_RESPONSE_MISSING",
        "Real streamed inference did not complete": "STREAM_TERMINAL_MISSING",
        "Hosted inference metadata is not real": "STREAM_MODEL_METADATA",
        "Invalid hosted stream content": "STREAM_CONTENT_TYPE",
        "Hosted model returned empty content": "STREAM_CONTENT_EMPTY",
        "Hosted conversation context was not retained": "CONTEXT_FACT_MISSING",
        "Actual chat history not persisted": "HISTORY_NOT_PERSISTED",
        "Incomplete hosted stream frame": "STREAM_FRAME_INCOMPLETE",
        "Unsupported hosted stream event": "STREAM_EVENT_UNSUPPORTED",
        "Hosted stream data must be an object": "STREAM_DATA_TYPE",
        "Hosted stream exceeds bound": "STREAM_SIZE_BOUND",
        "Hosted stream event limit reached": "STREAM_EVENT_BOUND",
    }
    return known.get(str(error), "UNCLASSIFIED_REQUEST_OR_CHECK")


def safe_suite_failure_code(error):
    if isinstance(error, (FixtureError, HostedRequestFailure)):
        return error.code
    match = re.fullmatch(
        r"Synthetic hosted request failed: [A-Z]+ [a-z-]+ HTTP ([1-5][0-9]{2})",
        str(error),
    )
    if match:
        return "HTTP_" + match[1]
    known = {
        "Secure session cookie missing": "SESSION_COOKIE",
        "CSRF token missing": "CSRF_TOKEN",
    }
    return known.get(str(error), "HOSTED_CHECK")


class Session:
    def __init__(self, origin):
        self.origin = origin
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPCookieProcessor(self.cookies)
        )
        self.csrf = None
        self.last_model_request = 0.0

    def model_call(self, method, path, body=None, expected=200):
        # Respect the real staging service's admission budget; never raise its limits for QA.
        remaining = 30 - (time.monotonic() - self.last_model_request)
        if remaining > 0:
            time.sleep(remaining)
        self.last_model_request = time.monotonic()
        return self.call(method, path, body, expected=expected)

    def stream(self, body):
        remaining = 30 - (time.monotonic() - self.last_model_request)
        if remaining > 0:
            time.sleep(remaining)
        self.last_model_request = time.monotonic()
        headers = {
            "Origin": self.origin,
            "Content-Type": "application/json",
            "X-CSRF-Token": self.csrf or "",
            "x-vercel-protection-bypass": os.environ.get(
                "VERCEL_AUTOMATION_BYPASS_SECRET", ""
            ),
        }
        return self.opener.open(
            urllib.request.Request(
                self.origin + "/api/v1/chat/completions",
                data=json.dumps(body).encode(),
                headers=headers,
                method="POST",
            ),
            timeout=150,
        )

    def call(self, method, path, body=None, expected=200, csrf=True):
        headers = {
            "Origin": self.origin,
            "Accept": "application/json",
            "x-vercel-protection-bypass": os.environ.get(
                "VERCEL_AUTOMATION_BYPASS_SECRET", ""
            ),
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.csrf and csrf:
            headers["X-CSRF-Token"] = self.csrf
        req = urllib.request.Request(
            self.origin + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method,
        )
        try:
            with self.opener.open(req, timeout=150) as response:
                status = response.status
                # Bound streaming and file responses to avoid unbounded provider/data usage.
                content = response.read(1024 * 1024 + 1)
                require(len(content) <= 1024 * 1024, "Probe response exceeds bound")
        except urllib.error.HTTPError as error:
            status, content = error.code, error.read(4096)
        if status != expected:
            raise HostedRequestFailure(status, path, content)
        try:
            return json.loads(content)
        except ValueError:
            return content

    def login(self, user):
        payload = {"email": user["email"], "password": user["password"]}
        if PRODUCT.endswith("portal"):
            key = decode_totp(user.get("totp_secret"))
            message = struct.pack(">Q", int(time.time()) // 30)
            value = hmac.new(key, message, hashlib.sha1).digest()
            offset = value[-1] & 15
            code = (
                struct.unpack(">I", value[offset : offset + 4])[0] & 0x7FFFFFFF
            ) % 1000000
            payload["code"] = str(code).zfill(6)
        result = self.call("POST", "/api/v1/auth/login", payload)
        require(
            any(
                cookie.name == "onesa_session"
                and cookie.secure
                and cookie.has_nonstandard_attr("HttpOnly")
                for cookie in self.cookies
            ),
            "Secure session cookie missing",
        )
        self.csrf = result.get("csrf") if isinstance(result, dict) else None
        self.csrf = self.csrf or next(
            (cookie.value for cookie in self.cookies if cookie.name == "onesa_csrf"),
            None,
        )
        require(self.csrf, "CSRF token missing")
        self.call("GET", "/api/v1/auth/me")


def stream_events(response):
    """Read bounded SSE JSON as data, including split frames; never execute output."""
    total = 0
    name = ""
    data = []
    for _ in range(8192):
        line = response.readline(65537)
        if not line:
            require(not data, "Incomplete hosted stream frame")
            return
        total += len(line)
        require(
            len(line) <= 65536 and total <= 1024 * 1024, "Hosted stream exceeds bound"
        )
        text = line.decode("utf-8").rstrip("\r\n")
        if not text:
            if data:
                require(
                    name in {"message_start", "content_delta", "message_end", "error"},
                    "Unsupported hosted stream event",
                )
                value = json.loads("\n".join(data))
                require(isinstance(value, dict), "Hosted stream data must be an object")
                yield name, value
            name, data = "", []
        elif text.startswith("event: "):
            name = text[7:]
        elif text.startswith("data: "):
            data.append(text[6:])
    raise Rejected("Hosted stream event limit reached")


def generation(client, body):
    response = client.model_call("POST", "/api/v1/chat/completions", body)
    require(isinstance(response, bytes), "Real streamed inference missing")
    frames = list(stream_events(io.BytesIO(response)))
    names = [name for name, _ in frames]
    if "error" in names:
        failure = next(value for name, value in frames if name == "error")
        raise HostedStreamFailure(
            failure.get("code"),
            failure.get("failure_reason"),
            failure.get("provider_error_code"),
        )
    require(
        names
        and names[0] == "message_start"
        and names[-1] == "message_end"
        and "error" not in names,
        "Real streamed inference did not complete",
    )
    start = frames[0][1]
    require(
        start.get("model", {}).get("real_inference") is True
        and start["model"].get("backend") in {"cloudflare", "ollama", "vllm"},
        "Hosted inference metadata is not real",
    )
    chunks = [value.get("text") for name, value in frames if name == "content_delta"]
    require(
        all(isinstance(chunk, str) for chunk in chunks), "Invalid hosted stream content"
    )
    text = "".join(chunks)
    require(bool(text.strip()), "Hosted model returned empty content")
    return text, start


def upload_quota(client, other):
    owned = []
    payload = {
        "filename": "release-quota.txt",
        "media_type": "text/plain",
        "size": 1,
        "sha256": hashlib.sha256(b"x").hexdigest(),
    }
    try:
        for _ in range(2):
            identifier = client.call(
                "POST", "/api/v1/knowledge/uploads", payload, expected=201
            )["id"]
            owned.append(identifier)
        denied = client.call("POST", "/api/v1/knowledge/uploads", payload, expected=429)
        require(
            denied.get("error", {}).get("code") == "upload_quota",
            "Actual upload quota not enforced",
        )
        other.call(
            "POST",
            "/api/v1/knowledge/uploads/" + owned[0] + "/chunks",
            {"sequence": 0, "base64": base64.b64encode(b"x").decode()},
            expected=404,
        )
    finally:
        for identifier in owned:
            client.call(
                "DELETE", "/api/v1/knowledge/uploads/" + identifier, expected=204
            )


def run_suite(origin):
    checks = {
        name: "BLOCKED"
        for name in [
            "authentication",
            "user_data_isolation",
            "critical_workflows",
            "storage_integrations",
        ]
    }
    if PRODUCT.endswith("platform"):
        checks.update(
            {"inference": "BLOCKED", "embeddings": "BLOCKED", "streaming": "BLOCKED"}
        )
    record = {
        "schema_version": 1,
        "repository": REPOSITORY,
        "candidate_commit": os.environ["GITHUB_SHA"],
        "workflow_run_id": int(os.environ.get("GITHUB_RUN_ID", "0")),
        "frontend_origin": origin,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "workflow_checks": {},
        "synthetic_fixture_ids": [],
        "status": "BLOCKED",
    }
    raw = os.environ.get("STAGING_FIXTURES_JSON")
    if os.environ.get("STAGING_FIXTURE_MODE") == "temporary":
        from fixture_lifecycle import file_path, validate_owned

        path = file_path()
        require(
            path.is_file() and path.stat().st_mode & 0o077 == 0,
            "Private temporary fixture file required",
        )
        raw = path.read_text()
        validate_owned(json.loads(raw))
    if not raw:
        return record
    try:
        config = parse_fixtures(raw, os.environ["VERCEL_PROJECT_ID"], PRODUCT)
    except FixtureError as error:
        if error.code == "FIXTURE_BINDING":
            raise Rejected("Synthetic fixture scope mismatch") from None
        checks["authentication"] = "FAIL"
        record.update(
            status="FAIL", failure_code=error.code, failure_phase="fixture-validation"
        )
        return record
    users = config["users"]
    clients = [Session(origin), Session(origin)]
    active = "authentication"
    workflow = "authentication"
    try:
        for client, user in zip(clients, users, strict=True):
            client.login(user)
        checks["authentication"] = "PASS"
        if PRODUCT.endswith("platform"):
            detail = record["workflow_checks"]
            active = "authentication"
            anonymous = Session(origin)
            for path in [
                "/models",
                "/conversations",
                "/knowledge/documents",
                "/agents/runs",
                "/travel/trips",
            ]:
                anonymous.call("GET", "/api/v1" + path, expected=401)
            detail["anonymous_models_denied"] = "PASS"
            model = clients[0].call("GET", "/api/v1/models")["items"][0]
            require(
                model.get("real_inference") is True and model["backend"] != "mock",
                "Actual real hosted model required",
            )
            record["model"] = {
                key: model.get(key)
                for key in [
                    "backend",
                    "model_identifier",
                    "revision",
                    "context_tokens",
                    "real_inference",
                ]
            }
            active = "critical_workflows"
            conversation = clients[0].call(
                "POST",
                "/api/v1/conversations",
                {"title": "Release synthetic " + secrets.token_hex(8)},
                expected=201,
            )["id"]
            record["synthetic_fixture_ids"].append(conversation)
            clients[0].call("GET", "/api/v1/conversations/" + conversation)
            clients[1].call(
                "GET", "/api/v1/conversations/" + conversation, expected=404
            )
            clients[0].call(
                "POST",
                "/api/v1/conversations",
                {"title": "Denied CSRF"},
                expected=403,
                csrf=False,
            )
            checks["user_data_isolation"] = "PASS"
            active = "streaming"
            workflow = "real_context_acknowledgement"
            memory = "RELEASE-" + secrets.token_hex(8)
            _, _start = generation(
                clients[0],
                {
                    "conversation_id": conversation,
                    "content": "Remember this synthetic test code: "
                    + memory
                    + ". Acknowledge briefly.",
                    "stream": True,
                },
            )
            workflow = "real_context_recall"
            remembered, _ = generation(
                clients[0],
                {
                    "conversation_id": conversation,
                    "content": "What synthetic test code did I give you? Return only that exact code.",
                    "stream": True,
                },
            )
            require(
                memory.lower() in remembered.lower(),
                "Hosted conversation context was not retained",
            )
            workflow = "real_history_persistence"
            history = clients[0].call("GET", "/api/v1/conversations/" + conversation)[
                "messages"
            ]
            require(
                sum(message["role"] == "assistant" for message in history) >= 2
                and any(
                    memory in message["content"]["text"]
                    for message in history
                    if message["role"] == "user"
                ),
                "Actual chat history not persisted",
            )
            detail["real_context_and_history"] = "PASS"
            checks["streaming"] = checks["inference"] = "PASS"
            active = "embeddings"
            workflow = "real_rag_citations_and_isolation"
            text = b"Synthetic release qualification document: Onesa release tests use isolated fixtures."
            upload = clients[0].call(
                "POST",
                "/api/v1/knowledge/uploads",
                {
                    "filename": "release-synthetic.txt",
                    "media_type": "text/plain",
                    "size": len(text),
                    "sha256": hashlib.sha256(text).hexdigest(),
                },
                expected=201,
            )
            identifier = upload["id"]
            clients[0].call(
                "POST",
                "/api/v1/knowledge/uploads/" + identifier + "/chunks",
                {"sequence": 0, "base64": base64.b64encode(text).decode()},
            )
            document = clients[0].call(
                "POST", "/api/v1/knowledge/uploads/" + identifier + "/complete"
            )["id"]
            record["synthetic_fixture_ids"].append(document)
            clients[0].call("GET", "/api/v1/knowledge/documents/" + document)
            clients[1].call(
                "GET", "/api/v1/knowledge/documents/" + document, expected=404
            )
            retrieved = clients[0].call(
                "POST",
                "/api/v1/knowledge/search",
                {"query": "isolated release qualification"},
            )
            require(
                retrieved["backend"] in {"http", "cloudflare"}
                and any(
                    source.get("document_id") == document
                    for source in retrieved["sources"]
                ),
                "Semantic retrieval did not return the newly stored synthetic document",
            )
            checks["embeddings"] = checks["storage_integrations"] = "PASS"
            index_version = next(
                source["embedding_version"]
                for source in retrieved["sources"]
                if source.get("document_id") == document
            )
            record["embedding"] = {
                "backend": retrieved["backend"],
                "index_version_sha256": hashlib.sha256(
                    index_version.encode()
                ).hexdigest(),
                "dimensions": int(index_version.rsplit(":", 1)[-1]),
            }
            answer, grounded = generation(
                clients[0],
                {
                    "conversation_id": conversation,
                    "content": "What does the synthetic qualification document say about release tests? Attribute the answer to its title.",
                    "document_ids": [document],
                    "stream": True,
                },
            )
            require(
                any(
                    source.get("document_id") == document
                    for source in grounded.get("sources", [])
                ),
                "Real RAG citation metadata missing",
            )
            history = clients[0].call("GET", "/api/v1/conversations/" + conversation)[
                "messages"
            ]
            require(
                any(
                    any(
                        source.get("document_id") == document
                        for source in message["content"].get("sources", [])
                    )
                    for message in history
                    if message["role"] == "assistant"
                ),
                "RAG citations not persisted",
            )
            require("isolated" in answer.lower(), "Real source-grounded fact missing")
            other_search = clients[1].call(
                "POST",
                "/api/v1/knowledge/search",
                {"query": "isolated release qualification"},
            )
            require(
                not any(
                    source.get("document_id") == document
                    for source in other_search["sources"]
                ),
                "Semantic retrieval crossed ownership",
            )
            clients[1].call(
                "POST",
                "/api/v1/knowledge/search",
                {"query": "isolated release qualification", "document_ids": [document]},
                expected=404,
            )
            detail["real_rag_citations_and_isolation"] = "PASS"
            active = "critical_workflows"
            workflow = "actual_upload_quota_and_input_bound"
            upload_quota(clients[0], clients[1])
            clients[0].model_call(
                "POST",
                "/api/v1/chat/completions",
                {"conversation_id": conversation, "content": "x" * 32001},
                expected=422,
            )
            detail["actual_upload_quota_and_input_bound"] = "PASS"
            workflow = "real_agent_planning_permissions_and_isolation"
            explicit = clients[0].model_call(
                "POST",
                "/api/v1/agents/runs",
                {
                    "goal": "Synthetic explicit addition",
                    "allowed_tools": ["arithmetic"],
                    "steps": [
                        {
                            "tool": "arithmetic",
                            "arguments": {"operation": "add", "values": [2, 3]},
                        }
                    ],
                },
                expected=201,
            )
            require(
                explicit["status"] == "completed"
                and explicit["steps"][0]["result"]["result"] == 5,
                "Actual explicit tool execution failed",
            )
            clients[1].call(
                "GET", "/api/v1/agents/runs/" + explicit["id"], expected=404
            )
            clients[0].model_call(
                "POST",
                "/api/v1/agents/runs",
                {
                    "goal": "Denied tool permission",
                    "allowed_tools": [],
                    "steps": [
                        {
                            "tool": "arithmetic",
                            "arguments": {"operation": "add", "values": [2, 3]},
                        }
                    ],
                },
                expected=403,
            )
            planned = clients[0].model_call(
                "POST",
                "/api/v1/agents/runs",
                {
                    "goal": "Use arithmetic to add 17 and 25. Return one tool call using operation add and values [17,25].",
                    "allowed_tools": ["arithmetic"],
                },
                expected=201,
            )
            require(
                planned["status"] == "completed"
                and any(
                    step.get("result", {}).get("result") == 42
                    for step in planned["steps"]
                ),
                "Real model tool planning did not complete",
            )
            clients[1].call("GET", "/api/v1/agents/runs/" + planned["id"], expected=404)
            record["synthetic_fixture_ids"].extend([explicit["id"], planned["id"]])
            detail["real_agent_planning_permissions_and_isolation"] = "PASS"
            workflow = "real_travel_planning_revision_isolation_and_boundary"
            preference = {
                "destination": "Heidelberg",
                "duration": 1,
                "budget": 75,
                "currency": "EUR",
                "preferences": "Suggest just one concise walking activity. No live research or booking.",
            }
            trip = clients[0].model_call(
                "POST", "/api/v1/travel/trips", preference, expected=201
            )
            record["synthetic_fixture_ids"].append(trip["id"])
            require(
                trip["itinerary"]["backend"] == model["backend"]
                and trip["live_data_verified"] is False
                and bool(trip["notice"])
                and len(trip["itinerary"]["days"]) == 1,
                "Real itinerary or explicit live-data boundary missing",
            )
            clients[0].call("GET", "/api/v1/travel/trips/" + trip["id"])
            clients[1].call("GET", "/api/v1/travel/trips/" + trip["id"], expected=404)
            clients[1].call(
                "PUT",
                "/api/v1/travel/trips/" + trip["id"],
                {**preference, "expected_revision": 1},
                expected=404,
            )
            changed = clients[0].model_call(
                "PUT",
                "/api/v1/travel/trips/" + trip["id"],
                {
                    **preference,
                    "preferences": "Suggest one quiet walking activity, without live research.",
                    "expected_revision": 1,
                },
            )
            require(changed["revision"] == 2, "Actual trip revision not persisted")
            clients[0].model_call(
                "PUT",
                "/api/v1/travel/trips/" + trip["id"],
                {**preference, "expected_revision": 1},
                expected=409,
            )
            clients[1].call(
                "DELETE", "/api/v1/travel/trips/" + trip["id"], expected=404
            )
            clients[0].call(
                "DELETE", "/api/v1/travel/trips/" + trip["id"], expected=204
            )
            detail["real_travel_planning_revision_isolation_and_boundary"] = "PASS"
            workflow = "active_stop_and_direct_ownership_denial"
            with clients[0].stream(
                {
                    "conversation_id": conversation,
                    "content": "Write a detailed numbered explanation of vector similarity in 100 paragraphs.",
                    "stream": True,
                }
            ) as streaming:
                name, started = next(stream_events(streaming))
                require(
                    name == "message_start"
                    and started["model"]["real_inference"] is True,
                    "Actual active stream did not start",
                )
                clients[1].call(
                    "POST",
                    "/api/v1/conversations/" + conversation + "/cancel",
                    {"run_id": started["run_id"]},
                    expected=404,
                )
                clients[0].call(
                    "POST",
                    "/api/v1/conversations/" + conversation + "/cancel",
                    {"run_id": started["run_id"]},
                    expected=204,
                )
            clients[0].call(
                "PATCH",
                "/api/v1/conversations/" + conversation,
                {"title": "Synthetic stopped generation"},
            )
            detail["active_stop_and_direct_ownership_denial"] = "PASS"
            clients[0].call(
                "DELETE", "/api/v1/knowledge/documents/" + document, expected=204
            )
            clients[0].call(
                "DELETE", "/api/v1/conversations/" + conversation, expected=204
            )
            checks["critical_workflows"] = "PASS"
        else:
            active = "critical_workflows"
            # Fixture 0 must be an isolated admin; fixture 1 a restricted employee.
            clients[0].call("GET", "/api/v1/auth/me")
            clients[0].call("GET", "/api/v1/admin/files")
            clients[1].call("GET", "/api/v1/admin/files", expected=403)
            clients[0].call(
                "POST",
                "/api/v1/admin/files",
                {
                    "filename": "csrf-negative.png",
                    "base64": PNG,
                    "title": "Synthetic CSRF negative",
                },
                expected=403,
                csrf=False,
            )
            checks["user_data_isolation"] = "PASS"
            active = "storage_integrations"
            data = clients[0].call(
                "POST",
                "/api/v1/admin/files",
                {
                    "filename": "release-synthetic.png",
                    "base64": PNG,
                    "title": "Synthetic release storage " + secrets.token_hex(8),
                    "classification": "confidential",
                },
                expected=201,
            )
            identifier = data["id"]
            record["synthetic_fixture_ids"].append(identifier)
            require(
                data["sha256"] == hashlib.sha256(base64.b64decode(PNG)).hexdigest(),
                "Stored synthetic content digest differs",
            )
            clients[0].call("POST", "/api/v1/admin/files/" + identifier + "/scan", {})
            content = clients[0].call(
                "GET", "/api/v1/admin/files/" + identifier + "/download"
            )
            require(
                content == base64.b64decode(PNG),
                "Private storage/scanner roundtrip differs",
            )
            clients[1].call(
                "GET", "/api/v1/admin/files/" + identifier + "/download", expected=403
            )
            # Keep confidential classification and pending editorial approval unchanged.
            checks["storage_integrations"] = checks["critical_workflows"] = "PASS"
        record["status"] = (
            "PASS" if all(value == "PASS" for value in checks.values()) else "BLOCKED"
        )
    except (
        Rejected,
        urllib.error.URLError,
        TimeoutError,
        ValueError,
        KeyError,
    ) as error:
        checks[active] = "FAIL"
        record["status"] = "FAIL"
        record["failure_code"] = safe_suite_failure_code(error)
        record["failure_reason"] = safe_suite_failure_reason(error)
        if (
            isinstance(error, HostedStreamFailure)
            and error.provider_error_code is not None
        ):
            record["failure_provider_error_code"] = error.provider_error_code
        record["failure_workflow"] = workflow
        record["failure_phase"] = (
            error.phase if isinstance(error, HostedRequestFailure) else active
        )
    return record


def production_probes(origin):
    checks = {
        "authenticated_critical_workflows": "BLOCKED",
        "storage_integrations": "BLOCKED",
    }
    if PRODUCT.endswith("platform"):
        checks["inference_and_streaming"] = "BLOCKED"
    raw = os.environ.get("PRODUCTION_FIXTURES_JSON")
    if not raw:
        return checks
    fixture = parse_fixtures(
        raw,
        os.environ["VERCEL_PROJECT_ID"],
        PRODUCT,
        scope="approved-synthetic-production",
    )
    users = fixture["users"]
    clients = [Session(origin), Session(origin)]
    active = "authenticated_critical_workflows"
    try:
        for client, user in zip(clients, users, strict=True):
            client.login(user)
        identifier = fixture["document_id"]
        # Existing owner-provisioned synthetic fixture only; never enumerate customer content.
        if PRODUCT.endswith("portal"):
            active = "storage_integrations"
            content = clients[0].call(
                "GET", "/api/v1/admin/files/" + identifier + "/download"
            )
            require(
                hashlib.sha256(content).hexdigest() == fixture["document_sha256"],
                "Production synthetic storage digest mismatch",
            )
            clients[1].call(
                "GET", "/api/v1/admin/files/" + identifier + "/download", expected=403
            )
        else:
            active = "storage_integrations"
            clients[0].call("GET", "/api/v1/knowledge/documents/" + identifier)
            clients[1].call(
                "GET", "/api/v1/knowledge/documents/" + identifier, expected=404
            )
            found = clients[0].call(
                "POST",
                "/api/v1/knowledge/search",
                {"query": "isolated release qualification"},
            )
            require(
                found["backend"] in {"http", "cloudflare"}
                and any(
                    source["document_id"] == identifier for source in found["sources"]
                ),
                "Production semantic storage retrieval mismatch",
            )
            active = "inference_and_streaming"
            conversation = fixture["conversation_id"]
            clients[1].call(
                "GET", "/api/v1/conversations/" + conversation, expected=404
            )
            response = clients[0].call(
                "POST",
                "/api/v1/chat/completions",
                {
                    "conversation_id": conversation,
                    "content": "Return the word READY.",
                    "stream": True,
                },
            )
            require(
                isinstance(response, bytes)
                and b"event: content_delta" in response
                and b"event: message_end" in response
                and b"event: error" not in response
                and b"mock" not in response.lower(),
                "Production streamed inference failed",
            )
            checks["inference_and_streaming"] = "PASS"
        checks["storage_integrations"] = checks["authenticated_critical_workflows"] = (
            "PASS"
        )
    except (Rejected, ValueError, KeyError, urllib.error.URLError, TimeoutError):
        checks[active] = "FAIL"
    return checks


def main():
    origin = preview_origin("/tmp/vercel-url.txt")
    # Validate the actual Preview/candidate before any authenticated/writing probes.
    from hosted import frontend, preflight

    preflight()
    frontend(origin, os.environ["GITHUB_SHA"], "Staging")
    status, _ = request(origin)
    require(status in {401, 403, 302, 303, 307}, "Staging Preview is not protected")
    record = run_suite(origin)
    Path(os.environ["RUNNER_TEMP"], "hosted-suite.json").write_text(json.dumps(record))
    print("Synthetic hosted suite: " + record["status"])
    if record.get("failure_code"):
        print("Hosted check failure: " + record["failure_code"])
        print("Hosted failure reason: " + record["failure_reason"])
        if "failure_provider_error_code" in record:
            print(
                "Hosted provider error code: "
                + str(record["failure_provider_error_code"])
            )
        print(
            "Hosted failure phase: " + record.get("failure_phase", "workflow-request")
        )
        print("Hosted workflow: " + record.get("failure_workflow", "authentication"))


if __name__ == "__main__":
    try:
        main()
    except (Rejected, ValueError, KeyError, OSError):
        raise SystemExit(
            "Synthetic hosted suite blocked; configure isolated fixtures privately"
        ) from None
