import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.main import create_app
from app.models import BoundedUpload, Document, UploadChunk, now
from tests.conftest import signup


def pdf(size):
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 10 100 Td (Private bounded fixture) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    padding = size - 2000
    for _ in range(4):
        writer.add_metadata({"/SyntheticPadding": "x" * padding})
        output = BytesIO()
        writer.write(output)
        data = output.getvalue()
        if len(data) == size:
            return data
        padding += size - len(data)
    raise AssertionError("Could not create exact-size valid PDF fixture")


def start(api, data, filename="fixture.txt", media="text/plain"):
    response = api.post(
        "/api/v1/knowledge/uploads",
        json={
            "filename": filename,
            "media_type": media,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def fill(api, identifier, data):
    for sequence, offset in enumerate(range(0, len(data), 512 * 1024)):
        response = api.post(
            f"/api/v1/knowledge/uploads/{identifier}/chunks",
            json={
                "sequence": sequence,
                "base64": base64.b64encode(data[offset : offset + 512 * 1024]).decode(),
            },
        )
        assert response.status_code == 200


@pytest.mark.parametrize("size", [5 * 1024 * 1024 - 1, 5 * 1024 * 1024])
def test_bounded_document_below_and_at_limit_preserves_parser_and_deletion(api, pg, size):
    signup(api)
    data = pdf(size)
    identifier = start(api, data, "fixture.pdf", "application/pdf")
    fill(api, identifier, data)
    result = api.post(f"/api/v1/knowledge/uploads/{identifier}/complete")
    assert result.status_code == 200
    assert api.post(f"/api/v1/knowledge/uploads/{identifier}/complete").json() == result.json()
    document_id = result.json()["id"]
    assert (
        "Private bounded fixture"
        in api.get(f"/api/v1/knowledge/documents/{document_id}").json()["text"]
    )
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(UploadChunk)) == 0
        assert db.scalar(select(func.count()).select_from(Document)) == 1
    assert api.delete(f"/api/v1/knowledge/documents/{document_id}").status_code == 204
    assert api.post(f"/api/v1/knowledge/uploads/{identifier}/complete").status_code == 404


def test_bounded_upload_over_limit_and_malformed_input(api):
    signup(api)
    assert (
        api.post(
            "/api/v1/knowledge/uploads",
            json={
                "filename": "oversize.txt",
                "media_type": "text/plain",
                "size": 5242881,
                "sha256": "0" * 64,
            },
        ).status_code
        == 422
    )
    for filename, media in [("../../evil.txt", "text/plain"), ("file.html", "text/html")]:
        assert (
            api.post(
                "/api/v1/knowledge/uploads",
                json={"filename": filename, "media_type": media, "size": 1, "sha256": "0" * 64},
            ).status_code
            == 422
        )
    identifier = start(api, b"text")
    assert (
        api.post(
            f"/api/v1/knowledge/uploads/{identifier}/chunks", json={"sequence": 0, "base64": "!!!!"}
        ).status_code
        == 400
    )
    assert (
        api.post(
            f"/api/v1/knowledge/uploads/{identifier}/chunks",
            json={"sequence": 0, "base64": base64.b64encode(b"evil").decode()},
        ).status_code
        == 200
    )
    assert api.post(f"/api/v1/knowledge/uploads/{identifier}/complete").status_code == 400


def test_isolation_quota_expiry_cancellation_and_incomplete_upload(api, pg):
    signup(api)
    first, second = start(api, b"first"), start(api, b"second")
    assert (
        api.post(
            "/api/v1/knowledge/uploads",
            json={
                "filename": "third.txt",
                "media_type": "text/plain",
                "size": 1,
                "sha256": "0" * 64,
            },
        ).status_code
        == 429
    )
    assert api.post(f"/api/v1/knowledge/uploads/{first}/complete").status_code == 409
    assert api.delete(f"/api/v1/knowledge/uploads/{second}").status_code == 204
    signup(api, "other@example.com")
    assert api.delete(f"/api/v1/knowledge/uploads/{first}").status_code == 404
    assert api.post(f"/api/v1/knowledge/uploads/{first}/complete").status_code == 404
    with Session(pg) as db:
        db.get(BoundedUpload, UUID(first)).expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert api.post(f"/api/v1/knowledge/uploads/{first}/complete").status_code == 404


def test_chunk_replay_and_concurrent_finalize_create_one_document(api, pg):
    signup(api)
    data = b"Atomic ingestion and durable storage fixture"
    identifier = start(api, data)
    body = {"sequence": 0, "base64": base64.b64encode(data).decode()}
    first = api.post(f"/api/v1/knowledge/uploads/{identifier}/chunks", json=body)
    assert (
        api.post(f"/api/v1/knowledge/uploads/{identifier}/chunks", json=body).json() == first.json()
    )
    token, csrf = api.cookies["onesa_session"], api.cookies["onesa_csrf"]

    def finalize(_):
        with TestClient(create_app(api.app.state.settings)) as client:
            client.headers.update(
                {
                    "Origin": api.app.state.settings.public_origin,
                    "Cookie": f"onesa_session={token}",
                    "X-CSRF-Token": csrf,
                }
            )
            response = client.post(f"/api/v1/knowledge/uploads/{identifier}/complete")
            assert response.status_code == 200
            return response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(finalize, range(2)))
    assert results[0] == results[1]
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(Document)) == 1
