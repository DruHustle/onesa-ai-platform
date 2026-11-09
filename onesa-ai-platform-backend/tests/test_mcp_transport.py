"""Exercise actual framing/lifecycle and cancellation of owned HTTP response streams."""

import asyncio
import io
import json
import os
import sys
from pathlib import Path

import httpx
import pytest

from app import mcp_transport
from app.consumer import Connection
from app.mcp_stdio import PROTOCOL_VERSION, Server


def packet(method, identifier=None, params=None):
    value = {"jsonrpc": "2.0", "method": method}
    if identifier is not None:
        value["id"] = identifier
    if params is not None:
        value["params"] = params
    return (json.dumps(value) + "\n").encode()


def initialize(reader):
    reader.feed_data(
        packet(
            "initialize",
            1,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "clientInfo": {"name": "client", "version": "1"},
                "capabilities": {},
            },
        )
    )
    reader.feed_data(packet("notifications/initialized"))


def records(output):
    return [json.loads(line) for line in output.getvalue().splitlines()]


class HeldBody(httpx.AsyncByteStream):
    def __init__(self):
        self.started = asyncio.Event()
        self.closed = asyncio.Event()

    async def __aiter__(self):
        self.started.set()
        await asyncio.Event().wait()
        yield b"unreachable"

    async def aclose(self):
        self.closed.set()


def bridge(handler):
    return Server(
        Connection(
            "onesa",
            "https://onesa.example.test",
            session="synthetic-session",
            csrf="synthetic-csrf",
            origin="https://console.example.test",
        ),
        {"text_stats"},
        httpx.MockTransport(handler),
    )


def test_cancellation_closes_http_body_and_allows_next_call_without_replay():
    async def scenario():
        body, calls = HeldBody(), []

        def handler(request):
            calls.append(request.method)
            if len(calls) == 1:
                return httpx.Response(
                    200, headers={"Content-Type": "application/json"}, stream=body
                )
            return httpx.Response(200, json={"items": [{"name": "text_stats"}]})

        reader, output = asyncio.StreamReader(limit=mcp_transport.MAX_LINE), io.StringIO()
        running = asyncio.create_task(mcp_transport.serve(bridge(handler).dispatch, reader, output))
        initialize(reader)
        reader.feed_data(packet("tools/list", "held"))
        await asyncio.wait_for(body.started.wait(), 2)
        reader.feed_data(packet("notifications/cancelled", params={"requestId": "held"}))
        await asyncio.wait_for(body.closed.wait(), 2)
        reader.feed_data(packet("tools/list", "next"))
        reader.feed_eof()
        await asyncio.wait_for(running, 2)
        assert calls == ["GET", "GET"]
        assert [item["id"] for item in records(output)] == [1, "next"]
        assert records(output)[-1]["result"]["tools"][0]["name"] == "text_stats"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "cancel",
    [
        {"requestId": "foreign"},
        {"requestId": True},
        {},
        {"requestId": [2]},
        {"requestId": 2, "reason": 12},
        {"requestId": 2, "_meta": False},
        {"requestId": 2, "extra": "private"},
    ],
)
def test_unknown_or_malformed_cancellation_never_cancels_another_request(cancel):
    async def scenario():
        started, released, cancelled = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def dispatch(value):
            if value.get("method") == "work":
                started.set()
                try:
                    await released.wait()
                except asyncio.CancelledError:
                    cancelled.set()
                    raise
            return {"jsonrpc": "2.0", "id": value["id"], "result": {}}

        reader, output = asyncio.StreamReader(limit=mcp_transport.MAX_LINE), io.StringIO()
        running = asyncio.create_task(mcp_transport.serve(dispatch, reader, output))
        reader.feed_data(packet("work", 2))
        await started.wait()
        reader.feed_data(packet("notifications/cancelled", params=cancel))
        reader.feed_data(packet("ping", 3))
        await asyncio.sleep(0)
        assert not cancelled.is_set()
        released.set()
        reader.feed_eof()
        await running
        assert {item["id"] for item in records(output)} == {2, 3}
        assert not cancelled.is_set()

    asyncio.run(scenario())


def test_cancellation_request_cannot_be_used_as_a_notification():
    async def scenario():
        reader, output = asyncio.StreamReader(limit=mcp_transport.MAX_LINE), io.StringIO()
        initialize(reader)
        reader.feed_data(packet("notifications/cancelled", 9, {"requestId": 1}))
        reader.feed_data(packet("notifications/cancelled", params={"requestId": 1}))
        reader.feed_data(packet("ping", 10))
        reader.feed_eof()
        await mcp_transport.serve(
            bridge(lambda _: pytest.fail("Unexpected remote request")).dispatch, reader, output
        )
        result = {item["id"]: item for item in records(output)}
        assert result[1]["result"]["protocolVersion"] == PROTOCOL_VERSION
        assert result[9]["error"]["code"] == -32601
        assert result[10]["result"] == {}

    asyncio.run(scenario())


def test_outstanding_request_bound_and_duplicate_ids_preserve_original_work():
    async def scenario():
        released, responsive, started = asyncio.Event(), asyncio.Event(), []

        async def dispatch(value):
            started.append(value["id"])
            if value["method"] == "work":
                await released.wait()
            else:
                responsive.set()
            return {"jsonrpc": "2.0", "id": value["id"], "result": {}}

        reader, output = asyncio.StreamReader(limit=mcp_transport.MAX_LINE), io.StringIO()
        running = asyncio.create_task(mcp_transport.serve(dispatch, reader, output))
        for identifier in range(mcp_transport.MAX_IN_FLIGHT):
            reader.feed_data(packet("work", identifier))
        reader.feed_data(packet("work", "overflow"))
        reader.feed_data(packet("ping", 0))  # Cannot steal a pending request's ID.
        reader.feed_data(packet("ping", "responsive"))
        await asyncio.wait_for(responsive.wait(), 2)
        assert started == [0, 1, 2, 3, "responsive"]
        released.set()
        reader.feed_eof()
        await running
        found = records(output)
        assert next(r for r in found if r["id"] == "overflow")["error"]["code"] == -32000
        assert next(r for r in found if r["id"] is None)["error"]["code"] == -32600
        assert sum(r["id"] == 0 and "result" in r for r in found) == 1

    asyncio.run(scenario())


def test_fragmented_oversize_frame_is_drained_without_executing_its_tail():
    async def scenario():
        requests = []

        async def dispatch(value):
            requests.append(value)
            return {"jsonrpc": "2.0", "id": value["id"], "result": {}}

        reader, output = asyncio.StreamReader(limit=mcp_transport.MAX_LINE), io.StringIO()
        running = asyncio.create_task(mcp_transport.serve(dispatch, reader, output))
        reader.feed_data(b"x" * (mcp_transport.MAX_LINE + 1))
        await asyncio.sleep(0)
        reader.feed_data(packet("work", "hidden-tail"))
        reader.feed_data(packet("ping", "real"))
        reader.feed_eof()
        await running
        assert [value["id"] for value in requests] == ["real"]
        assert records(output)[0]["error"]["code"] == -32600

    asyncio.run(scenario())


def test_deadline_and_session_cancellation_close_owned_work(monkeypatch):
    async def scenario(cancel_session):
        body = HeldBody()
        reader, output = asyncio.StreamReader(limit=mcp_transport.MAX_LINE), io.StringIO()
        server = bridge(
            lambda _: httpx.Response(200, headers={"Content-Type": "application/json"}, stream=body)
        )
        running = asyncio.create_task(mcp_transport.serve(server.dispatch, reader, output))
        initialize(reader)
        reader.feed_data(packet("tools/list", 2))
        await body.started.wait()
        if cancel_session:
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running
        else:
            await asyncio.wait_for(body.closed.wait(), 2)
            reader.feed_eof()
            await running
            assert records(output)[-1]["error"]["message"] == "Request deadline exceeded"
        assert body.closed.is_set()

    monkeypatch.setattr(mcp_transport, "REQUEST_SECONDS", 0.05)
    asyncio.run(scenario(False))
    asyncio.run(scenario(True))


def test_actual_child_stdio_remains_responsive_with_stdin_open(tmp_path):
    root = Path(__file__).resolve().parents[1]

    async def scenario():
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "app.mcp_stdio",
            cwd=tmp_path,
            env={
                "PATH": os.environ["PATH"],
                "PYTHONPATH": str(root),
                "ONESA_MCP_API_URL": "https://onesa.example.test",
                "ONESA_MCP_ORIGIN": "https://console.example.test",
                "ONESA_MCP_SESSION": "synthetic-session",
                "ONESA_MCP_CSRF": "synthetic-csrf",
            },
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            child.stdin.write(packet("ping", "first"))
            await child.stdin.drain()
            assert json.loads(await asyncio.wait_for(child.stdout.readline(), 3))["id"] == "first"
            child.stdin.write(packet("notifications/cancelled", params={"requestId": "first"}))
            child.stdin.write(packet("ping", "second"))
            await child.stdin.drain()
            assert json.loads(await asyncio.wait_for(child.stdout.readline(), 3))["id"] == "second"
            child.stdin.close()
            assert await asyncio.wait_for(child.wait(), 3) == 0
            assert await child.stderr.read() == b""
        finally:
            if child.returncode is None:
                child.kill()
                await child.wait()

    asyncio.run(scenario())


def test_child_cancels_pending_http_work_before_stdin_closes(tmp_path):
    # Run the real pipe adapter in another process. Only its upstream API is a
    # synthetic held response; no provider, customer data or credential is used.
    program = r"""
import asyncio, sys
import httpx
from app.consumer import Connection
from app.mcp_stdio import Server, run
class Body(httpx.AsyncByteStream):
    async def __aiter__(self):
        print('synthetic-http-started', file=sys.stderr, flush=True)
        await asyncio.Event().wait()
        yield b'unreachable'
    async def aclose(self):
        print('synthetic-http-closed', file=sys.stderr, flush=True)
connection = Connection('onesa', 'https://onesa.example.test', session='synthetic-session',
    csrf='synthetic-csrf', origin='https://console.example.test')
transport = httpx.MockTransport(lambda _: httpx.Response(200,
    headers={'Content-Type':'application/json'}, stream=Body()))
asyncio.run(run(Server(connection, {'text_stats'}, transport), sys.stdin.buffer, sys.stdout))
"""
    root = Path(__file__).resolve().parents[1]

    async def scenario():
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            program,
            cwd=tmp_path,
            env={"PATH": os.environ["PATH"], "PYTHONPATH": str(root)},
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            child.stdin.write(
                packet(
                    "initialize",
                    1,
                    {
                        "protocolVersion": PROTOCOL_VERSION,
                        "clientInfo": {"name": "external-test-client", "version": "1"},
                        "capabilities": {},
                    },
                )
            )
            child.stdin.write(packet("notifications/initialized"))
            child.stdin.write(packet("tools/list", "held"))
            await child.stdin.drain()
            assert json.loads(await asyncio.wait_for(child.stdout.readline(), 3))["id"] == 1
            assert await asyncio.wait_for(child.stderr.readline(), 3) == b"synthetic-http-started\n"
            child.stdin.write(packet("notifications/cancelled", params={"requestId": "held"}))
            child.stdin.write(packet("ping", "after-cancel"))
            await child.stdin.drain()
            assert (
                json.loads(await asyncio.wait_for(child.stdout.readline(), 3))["id"]
                == "after-cancel"
            )
            assert await asyncio.wait_for(child.stderr.readline(), 3) == b"synthetic-http-closed\n"
            child.stdin.close()
            assert await asyncio.wait_for(child.wait(), 3) == 0
            assert await child.stdout.read() == b""
            assert await child.stderr.read() == b""
        finally:
            if child.returncode is None:
                child.kill()
                await child.wait()

    asyncio.run(scenario())
