"""Pinned MCP stdio lifecycle and least-authority tool transport."""

import asyncio
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from app.consumer import Connection
from app.mcp_stdio import MAX_LINE, PROTOCOL_VERSION, Server, run


def server(allowed=None, handler=None):
    connection = Connection(
        "onesa",
        "https://onesa.example.test",
        session="synthetic-session",
        csrf="synthetic-csrf",
        origin="https://console.example.test",
    )
    return Server(
        connection,
        {"text_stats"} if allowed is None else allowed,
        httpx.MockTransport(handler or (lambda _: httpx.Response(401, text="private-details"))),
    )


async def initialize(s):
    first = await s.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "clientInfo": {"name": "test", "version": "1"},
                "capabilities": {},
            },
        }
    )
    assert first["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert first["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert await s.dispatch({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_discovery_and_explicit_tool_call_preserve_server_permission_boundary():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers["Origin"] == "https://console.example.test"
        assert request.headers["X-CSRF-Token"] == "synthetic-csrf"
        assert request.headers["Cookie"] == "onesa_session=synthetic-session"
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"name": "text_stats"},
                        {"name": "launch_aircraft"},
                        {"name": "arithmetic"},
                    ]
                },
            )
        body = json.loads(request.content)
        assert request.url.path == "/api/v1/agents/runs"
        assert body["allowed_tools"] == ["text_stats"]
        assert body["steps"] == [{"tool": "text_stats", "arguments": {"text": "Two words"}}]
        return httpx.Response(
            201,
            json={
                "status": "completed",
                "steps": [
                    {
                        "tool": "text_stats",
                        "status": "completed",
                        "result": {"words": 2, "characters": 9},
                    }
                ],
            },
        )

    async def scenario():
        s = server(handler=handler)
        await initialize(s)
        catalog = await s.dispatch({"jsonrpc": "2.0", "id": "list", "method": "tools/list"})
        assert [t["name"] for t in catalog["result"]["tools"]] == ["text_stats"]
        assert catalog["result"]["tools"][0]["annotations"]["readOnlyHint"] is True
        denied = await s.dispatch(
            {
                "jsonrpc": "2.0",
                "id": "deny",
                "method": "tools/call",
                "params": {"name": "launch_aircraft", "arguments": {}},
            }
        )
        assert denied["error"]["code"] == -32602
        result = await s.dispatch(
            {
                "jsonrpc": "2.0",
                "id": "call",
                "method": "tools/call",
                "params": {"name": "text_stats", "arguments": {"text": "Two words"}},
            }
        )
        assert result["result"]["isError"] is False
        assert json.loads(result["result"]["content"][0]["text"]) == {"words": 2, "characters": 9}

    asyncio.run(scenario())
    assert [r.method for r in calls].count("POST") == 1


def test_no_initialization_no_remote_requests_and_notifications_cannot_call_tools():
    def forbidden(_):
        pytest.fail("Invalid lifecycle must not contact the server")

    async def scenario():
        s = server(handler=forbidden)
        result = await s.dispatch({"jsonrpc": "2.0", "id": 0, "method": "tools/list"})
        assert result["error"]["code"] == -32002
        await initialize(s)
        assert (
            await s.dispatch(
                {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "text_stats"}}
            )
            is None
        )
        unknown = await s.dispatch({"jsonrpc": "2.0", "id": 3, "method": "execute_shell"})
        assert unknown["error"]["code"] == -32601
        again = await s.dispatch({"jsonrpc": "2.0", "id": 4, "method": "initialize", "params": {}})
        assert again["error"]["code"] == -32602

    asyncio.run(scenario())


@pytest.mark.parametrize("status", [401, 403, 429, 503, 307])
def test_revoked_or_refused_identity_is_redacted_without_retry(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            text="private-details synthetic-session synthetic-csrf",
            headers={"Location": "https://foreign.example.test"},
        )

    async def scenario():
        s = server(handler=handler)
        await initialize(s)
        response = await s.dispatch(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "text_stats", "arguments": {"text": "x"}},
            }
        )
        assert response["result"]["isError"] is True
        assert all(
            secret not in json.dumps(response)
            for secret in ("private-details", "synthetic-session", "synthetic-csrf")
        )

    asyncio.run(scenario())
    assert len(calls) == 1


def test_empty_permissions_cannot_be_widened_by_discovery():
    def handler(_):
        return httpx.Response(200, json={"items": [{"name": "arithmetic"}]})

    async def scenario():
        s = server(set(), handler)
        await initialize(s)
        result = await s.dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert result["result"]["tools"] == []

    asyncio.run(scenario())
    with pytest.raises(ValueError):
        server({"launch_aircraft"})


@pytest.mark.parametrize(
    "value",
    [
        [],
        None,
        {"jsonrpc": "1.0", "id": 1, "method": "ping"},
        {"jsonrpc": "2.0", "id": True, "method": "ping"},
        {"jsonrpc": "2.0", "id": 1, "method": 23},
    ],
)
def test_malformed_rpc_is_rejected(value):
    assert asyncio.run(server().dispatch(value))["error"]["code"] == -32600


def test_stdio_bounds_invalid_lines_and_recovers_for_next_request():
    source = io.BytesIO(
        b"broken\n"
        + b"x" * (MAX_LINE + 100)
        + b"\n"
        + b'{"jsonrpc":"2.0","id":7,"method":"ping"}\n'
        + b'{"jsonrpc":"2.0","id":NaN,"method":"ping"}\n'
    )
    output = io.StringIO()
    asyncio.run(run(server(), source, output))
    records = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [r.get("error", {}).get("code") for r in records] == [-32700, -32600, None, -32700]
    assert records[2]["id"] == 7 and records[2]["result"] == {}


def test_real_subprocess_only_emits_protocol_json_without_opening_a_port(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(root),
        "ONESA_MCP_API_URL": "https://onesa.example.test",
        "ONESA_MCP_ORIGIN": "https://console.example.test",
        "ONESA_MCP_SESSION": "synthetic-session",
        "ONESA_MCP_CSRF": "synthetic-csrf",
    }
    completed = subprocess.run(
        [sys.executable, "-m", "app.mcp_stdio"],
        input=b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n',
        capture_output=True,
        env=env,
        cwd=tmp_path,
        timeout=5,
    )
    assert completed.returncode == 0 and completed.stderr == b""
    assert json.loads(completed.stdout) == {"jsonrpc": "2.0", "id": 1, "result": {}}
    assert b"synthetic-session" not in completed.stdout


@pytest.mark.parametrize("steps", [None, {}, ["private-result"]])
def test_malformed_remote_tool_results_remain_redacted_tool_errors(steps):
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"items": [{"name": "text_stats"}]})
        return httpx.Response(201, json={"status": "completed", "steps": steps})

    async def scenario():
        s = server(handler=handler)
        await initialize(s)
        response = await s.dispatch(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "text_stats", "arguments": {"text": "x"}},
            }
        )
        assert response["result"]["isError"] is True
        assert "private-result" not in json.dumps(response)

    asyncio.run(scenario())
