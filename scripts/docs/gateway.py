"""Serve classified builds; delegate identity/authorization to the existing Onesa API."""

import json
import os
import re
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

ROOT = Path(__file__).resolve().parents[2]


def create_gateway(scope=None, client=None, build=None):
    scope = scope or os.environ.get("ONESA_DOCS_SCOPE", "public")
    if scope not in {"public", "internal"}:
        raise ValueError("Invalid documentation scope")
    assets = Path(
        build or ROOT / f"onesa-ai-platform-frontend/apps/docs/build-{scope}"
    ).resolve()
    api = os.environ.get("ONESA_DOCS_UPSTREAM", "http://localhost:3100")
    upstream_origin = os.environ.get(
        "ONESA_DOCS_APPLICATION_ORIGIN", "http://localhost:3100"
    )
    own_origin = os.environ.get(
        "ONESA_DOCS_ORIGIN", f"http://localhost:{3200 if scope == 'public' else 3201}"
    )
    service = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    async def exchange(request, path, method="GET", body=None):
        headers = {
            "Cookie": request.headers.get("cookie", ""),
            "Origin": upstream_origin,
            "X-CSRF-Token": request.headers.get("x-csrf-token", ""),
        }
        try:
            if client is not None:
                return await client.request(
                    method, api + path, headers=headers, json=body
                )
            async with httpx.AsyncClient(
                timeout=75, follow_redirects=False
            ) as connection:
                return await connection.request(
                    method, api + path, headers=headers, json=body
                )
        except httpx.HTTPError:
            return httpx.Response(503, json={"error": {"code": "identity_unavailable"}})

    @service.middleware("http")
    async def guard(request: Request, call_next):
        if scope == "internal":
            permission = await exchange(request, "/api/v1/documentation/access")
            if permission.status_code != 200 or not permission.json().get(
                "engineering"
            ):
                status = (
                    401
                    if permission.status_code == 401
                    else 503
                    if permission.status_code >= 500
                    else 403
                )
                return HTMLResponse(
                    "<h1>Engineering access required</h1><p>Sign in to Onesa AI using an authorized engineering account. Every internal page and asset is protected.</p>",
                    status_code=status,
                    headers={
                        "Cache-Control": "no-store",
                        "X-Content-Type-Options": "nosniff",
                    },
                )
        result = await call_next(request)
        result.headers["X-Content-Type-Options"] = "nosniff"
        result.headers["Referrer-Policy"] = "same-origin"
        result.headers["Cache-Control"] = (
            "private, no-store" if scope == "internal" else "no-cache"
        )
        return result

    @service.post("/assistant")
    async def assistant(request: Request):
        if request.headers.get("origin") != own_origin:
            return JSONResponse({"error": "Origin rejected"}, status_code=403)
        raw = b""
        async for part in request.stream():
            raw += part
            if len(raw) > 16384:
                return JSONResponse({"error": "Question too large"}, status_code=413)
        try:
            body = json.loads(raw)
            if set(body) != {"query"} or not isinstance(body["query"], str):
                raise ValueError
        except (ValueError, TypeError):
            return JSONResponse({"error": "Invalid question"}, status_code=422)
        response = await exchange(
            request,
            "/api/v1/documentation/answer",
            "POST",
            {"query": body["query"], "scope": scope},
        )
        return JSONResponse(response.json(), status_code=response.status_code)

    @service.api_route(
        "/playground/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"]
    )
    async def playground(path: str, request: Request):
        target = os.environ.get("ONESA_DOCS_API_URL", "")
        if not re.fullmatch(r"http://(localhost|127\.0\.0\.1)(:\d+)?", target):
            return JSONResponse({"error": "Playground disabled"}, status_code=403)
        if request.method != "GET" and request.headers.get("origin") != own_origin:
            return JSONResponse({"error": "Origin rejected"}, status_code=403)
        schema = json.loads((assets / "generated/openapi.json").read_text())
        route = "/" + path
        permitted = any(
            request.method.lower() in methods
            and re.fullmatch(re.sub(r"\{[^}]+\}", "[^/]+", contract), route)
            for contract, methods in schema["paths"].items()
        )
        if not permitted or route.startswith("/api/v1/documentation/"):
            return JSONResponse({"error": "Endpoint not approved"}, status_code=403)
        raw = b""
        async for part in request.stream():
            raw += part
            if len(raw) > 16384:
                return JSONResponse(
                    {"error": "Request exceeds playground bound"}, status_code=413
                )
        headers = {
            "Cookie": request.headers.get("cookie", ""),
            "Origin": upstream_origin,
            "X-CSRF-Token": request.headers.get("x-csrf-token", ""),
            "Content-Type": request.headers.get("content-type", "application/json"),
        }
        try:
            async with httpx.AsyncClient(
                timeout=75, follow_redirects=False
            ) as connection:
                response = await connection.request(
                    request.method,
                    target + route,
                    params=request.query_params,
                    headers=headers,
                    content=raw,
                )
            result = HTMLResponse(
                response.content,
                status_code=response.status_code,
                media_type=response.headers.get("content-type", "application/json"),
            )
            for cookie in response.headers.get_list("set-cookie"):
                result.headers.append("set-cookie", cookie)
            return result
        except httpx.HTTPError:
            return JSONResponse(
                {"error": "Development API unavailable"}, status_code=503
            )

    @service.get("/{path:path}")
    async def static(path: str):
        requested = (assets / path).resolve()
        if not requested.is_relative_to(assets):
            return JSONResponse({"error": "Not found"}, status_code=404)
        candidates = (
            [requested / "index.html"]
            if requested.is_dir()
            else [requested, requested.with_suffix(".html")]
        )
        for candidate in candidates:
            if candidate.is_file() and candidate.resolve().is_relative_to(assets):
                return FileResponse(candidate)
        return JSONResponse({"error": "Not found"}, status_code=404)

    return service


if __name__ == "__main__":
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scope",
        choices=["public", "internal"],
        default=os.environ.get("ONESA_DOCS_SCOPE", "public"),
    )
    selected = parser.parse_args().scope
    uvicorn.run(
        create_gateway(selected),
        host="127.0.0.1",
        port=3200 if selected == "public" else 3201,
        access_log=False,
    )
