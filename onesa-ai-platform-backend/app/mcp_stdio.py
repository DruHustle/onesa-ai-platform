"""Local MCP stdio bridge to explicitly permitted, existing read-only tools.

No HTTP listener, model planner, arbitrary URL, remote command or physical tool.
The subprocess receives a separately commissioned identity through its environment.
"""

import asyncio
import io
import json
import os
import sys
from typing import Any, BinaryIO, TextIO

import httpx

from app.consumer import CompletionError, Connection, json_response
from app.mcp_context import METHODS as CONTEXT_METHODS
from app.mcp_context import Context, ContextError
from app.mcp_transport import MAX_LINE, error, serve

PROTOCOL_VERSION = "2025-11-25"
SCHEMAS: dict[str, dict[str, Any]] = {
    "text_stats": {
        "type": "object",
        "properties": {"text": {"type": "string", "maxLength": 4000}},
        "required": ["text"],
        "additionalProperties": False,
    },
    "arithmetic": {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["add", "multiply", "divide"]},
            "values": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 20},
        },
        "required": ["operation", "values"],
        "additionalProperties": False,
    },
}


class Server:
    def __init__(
        self,
        connection: Connection,
        allowed: set[str],
        transport: httpx.AsyncBaseTransport | None = None,
        *,
        resources: set[str] | None = None,
        prompts: set[str] | None = None,
    ) -> None:
        if connection.provider != "onesa" or not allowed <= SCHEMAS.keys():
            raise ValueError("MCP requires an Onesa identity and known read-only permissions")
        self.connection, self.allowed, self.transport = connection, frozenset(allowed), transport
        self.context = Context(connection, resources or set(), prompts or set(), transport)
        self.initialized = False
        self.ready = False

    async def request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        async with asyncio.timeout(25), self.connection.client(self.transport) as client:
            # Agent-run creation returns 201; read its bounded body with the same
            # parser by requesting an explicit expected status, never accepting redirects.
            return await json_response(
                client, method, path, payload, expected_status=201 if method == "POST" else 200
            )

    async def dispatch(self, value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict) or value.get("jsonrpc") != "2.0":
            return error(None, -32600, "Invalid request")
        identifier = value.get("id")
        if "id" in value and (type(identifier) not in {str, int}):
            return error(None, -32600, "Invalid request identifier")
        method, params = value.get("method"), value.get("params", {})
        if not isinstance(method, str) or not isinstance(params, dict):
            return error(identifier, -32600, "Invalid request")
        if "id" not in value:
            if method == "notifications/initialized" and self.initialized:
                self.ready = True
            return None  # Notifications cannot execute tools or request remote work.
        if method == "initialize":
            if (
                self.initialized
                or not isinstance(params.get("protocolVersion"), str)
                or not isinstance(params.get("clientInfo"), dict)
                or not isinstance(params.get("capabilities"), dict)
            ):
                return error(identifier, -32602, "Invalid initialization")
            self.initialized = True
            result: dict[str, Any] = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}, **self.context.capabilities()},
                "serverInfo": {"name": "onesa-read-only-tools", "version": "1.2.0"},
            }
        elif method == "ping":
            result = {}
        elif not self.ready:
            return error(identifier, -32002, "Initialize the MCP session first")
        elif method in CONTEXT_METHODS:
            try:
                result = await self.context.dispatch(method, params)
            except ContextError as refused:
                return error(identifier, refused.code, refused.message)
        else:
            if method not in {"tools/list", "tools/call"}:
                return error(identifier, -32601, "Method not found")
            try:
                # Remote discovery authenticates on every request; it cannot widen
                # the operator's fixed local allowlist or introduce an unknown tool.
                catalog = await self.request("GET", "api/v1/agents/tools")
                advertised = {item["name"] for item in catalog["items"]}
                available = self.allowed & advertised
                if method == "tools/list":
                    if set(params) - {"_meta"} or not isinstance(params.get("_meta", {}), dict):
                        return error(identifier, -32602, "No pagination is available")
                    result = {
                        "tools": [
                            {
                                "name": name,
                                "description": "Bounded local computation.",
                                "inputSchema": SCHEMAS[name],
                                "annotations": {
                                    "readOnlyHint": True,
                                    "destructiveHint": False,
                                    "openWorldHint": False,
                                },
                            }
                            for name in sorted(available)
                        ]
                    }
                elif method == "tools/call":
                    name, arguments = params.get("name"), params.get("arguments", {})
                    if (
                        not isinstance(name, str)
                        or name not in available
                        or not isinstance(arguments, dict)
                        or set(params) - {"name", "arguments", "_meta"}
                    ):
                        return error(identifier, -32602, "Tool or arguments are not permitted")
                    # Explicit steps bypass model planning. The existing API still
                    # validates schema, identity, permission, limits and execution.
                    record = await self.request(
                        "POST",
                        "api/v1/agents/runs",
                        {
                            "goal": "Explicit read-only MCP tool request",
                            "steps": [{"tool": name, "arguments": arguments}],
                            "allowed_tools": [name],
                        },
                    )
                    steps = record["steps"]
                    if (
                        record.get("status") != "completed"
                        or not isinstance(steps, list)
                        or len(steps) != 1
                        or not isinstance(steps[0], dict)
                        or steps[0].get("tool") != name
                        or steps[0].get("status") != "completed"
                    ):
                        raise CompletionError()
                    result = {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    steps[0]["result"], ensure_ascii=False, allow_nan=False
                                ),
                            }
                        ],
                        "isError": False,
                    }
                else:
                    return error(identifier, -32601, "Method not found")
            except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError, TimeoutError):
                # No provider body, private record or exception enters the protocol.
                if method == "tools/call":
                    result = {
                        "content": [
                            {"type": "text", "text": "Tool unavailable or request refused"}
                        ],
                        "isError": True,
                    }
                else:
                    return error(identifier, -32603, "Tool catalog unavailable")
        return {"jsonrpc": "2.0", "id": identifier, "result": result}


async def run(server: Server, stdin: BinaryIO, stdout: TextIO) -> None:
    reader = asyncio.StreamReader(limit=MAX_LINE)
    if isinstance(stdin, io.BytesIO):
        reader.feed_data(stdin.read())
        reader.feed_eof()
        await serve(server.dispatch, reader, stdout)
    else:
        protocol = asyncio.StreamReaderProtocol(reader)
        transport, _ = await asyncio.get_running_loop().connect_read_pipe(lambda: protocol, stdin)
        try:
            await serve(server.dispatch, reader, stdout)
        finally:
            transport.close()


def main() -> None:
    try:
        connection = Connection(
            provider="onesa",
            base_url=os.environ.get("ONESA_MCP_API_URL", ""),
            origin=os.environ.get("ONESA_MCP_ORIGIN", ""),
            session=os.environ.get("ONESA_MCP_SESSION", ""),
            csrf=os.environ.get("ONESA_MCP_CSRF", ""),
        )
        allowed = {
            name.strip()
            for name in os.environ.get("ONESA_MCP_ALLOWED_TOOLS", "").split(",")
            if name.strip()
        }
        resources = {
            uri.strip()
            for uri in os.environ.get("ONESA_MCP_ALLOWED_RESOURCES", "").split(",")
            if uri.strip()
        }
        prompts = {
            name.strip()
            for name in os.environ.get("ONESA_MCP_ALLOWED_PROMPTS", "").split(",")
            if name.strip()
        }
        asyncio.run(
            run(
                Server(connection, allowed, resources=resources, prompts=prompts),
                sys.stdin.buffer,
                sys.stdout,
            )
        )
    except (ValueError, OSError, httpx.HTTPError):
        print("MCP bridge unavailable; check approved local configuration", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
